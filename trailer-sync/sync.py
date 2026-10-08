"""Sync a YouTube trailer playlist (RSS) into the Seerr watchlist.

Usage: sync.py [--once] [--dry-run] [--import yt-dlp.json]
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SEERR_URL = os.environ.get("SEERR_URL", "http://seerr:5055").rstrip("/")
PLAYLIST_ID = os.environ.get("PLAYLIST_ID", "")
INTERVAL = int(os.environ.get("TRAILER_SYNC_INTERVAL", "1800"))
STATE_FILE = os.environ.get("STATE_FILE", "/data/state.json")
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

# adjectives and numbers only count as noise next to "trailer": "Final Destination", "28 Years Later" stay
NOISE = re.compile(
    r"\b(?:(?:final|new|main|international|extended|first|second|third|1st|2nd|3rd|\d+th)\s+)*"
    r"(?:official\s+|officiel(?:le)?\s+)?(?:trailer|teaser|bande[- ]annonce)(?:\s+officiel(?:le)?)?(?:\s*#?\d+)?\b"
    r"|\b(?:official|officiel(?:le)?|red band|vf|vost(?:fr)?|4k|uhd|hd|imax|coming soon)\b"
    r"|\b(?:only |now |exclusively )?(?:in theaters|in cinemas|au cinema|now streaming)\b.*"
    r"|#\d+",
    re.I,
)
TV_HINT = re.compile(r"\b(?:season|saison|series|serie|s\d{1,2}|limited series|miniseries)\b", re.I)
SEASON = re.compile(r"\b(?:the final |final )?(?:season|saison)\s*\d*\b|\bs\d{1,2}\b|\b(?:limited |mini)?series\b", re.I)
SEASON_NUM = re.compile(r"\s+\d{1,2}$")
YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
NETWORKS = {
    "netflix", "hbo", "hbo max", "max", "prime video", "amazon prime video", "apple tv", "apple tv+",
    "disney", "disney+", "disney plus", "hulu", "fx", "fx networks", "a24", "peacock", "paramount",
    "paramount+", "paramount pictures", "canal+", "sony pictures", "warner bros", "warner bros pictures",
    "universal pictures", "marvel entertainment", "lionsgate", "neon", "focus features", "starz",
    "showtime", "amc", "bbc", "itv", "mubi", "searchlight pictures", "20th century studios",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"['’`]", "", s).replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parse(title, author="", description=""):
    """Return (queries, year, tv_hint) from a trailer title."""
    years = YEAR.findall(title)
    year = int(years[-1]) if years else None
    tv = bool(TV_HINT.search(title))
    queries = []
    for seg in re.split(r"\s+[|\-–—]\s+|\|", title):
        seg = re.sub(r"[()\[\]{}]", " ", seg)
        seg = YEAR.sub(" ", SEASON.sub(" ", seg))
        seg = re.sub(r"\s+", " ", NOISE.sub(" ", seg)).strip(" :,-.!")
        if not norm(seg) or norm(seg) in NETWORKS or norm(seg) == norm(author):
            continue
        queries.append(seg)
    queries.sort(key=len, reverse=True)
    # "Dune: Part Two" first, "Dune" last: the bare prefix still needs an exact title + year match
    queries += [q.split(":")[0].strip() for q in queries if ":" in q]
    # "Stranger Things 5" = season 5; tried after "Toy Story 5" style exact titles
    queries += [SEASON_NUM.sub("", q) for q in queries if SEASON_NUM.search(q)]
    first = (description or "").strip().split("\n")[0].strip()
    if first and len(first) <= 60 and not first.startswith("#"):
        queries.append(first)
    seen, out = set(), []
    for q in queries:
        if norm(q) and norm(q) not in seen:
            seen.add(norm(q))
            out.append(q)
    return out, year, tv


def _year(c):
    d = c.get("releaseDate") or c.get("firstAirDate") or ""
    return int(d[:4]) if d[:4].isdigit() else None


def _year_ok(c, year):
    cy = _year(c)
    if not year or not cy:
        return True
    # a show's trailer year is the season's year, so the show may have started earlier
    return cy <= year + 1 if c["mediaType"] == "tv" else abs(cy - year) <= 1


def match(video, search, details, max_details=8):
    """Return (tmdbId, mediaType, title, reason) or None.

    search(query) -> Seerr search results; details(mediaType, id) -> Seerr movie/tv details.
    """
    queries, year, tv = parse(video["title"], video.get("author", ""), video.get("description", ""))
    candidates, exact = {}, []
    for q in queries:
        for c in [r for r in search(q) if r.get("mediaType") in ("movie", "tv")][:5]:
            key = (c["mediaType"], c["id"])
            candidates.setdefault(key, c)
            names = {norm(c.get(k)) for k in ("title", "originalTitle", "name", "originalName")} - {""}
            # queries are ordered by preference: only the first query with exact hits counts
            if norm(q) in names and _year_ok(c, year) and (not exact or exact[0]["_q"] == q):
                exact.append({**c, "_q": q})

    def found(c, reason):
        return c["id"], c["mediaType"], c.get("title") or c.get("name"), reason

    for c in list(candidates.values())[:max_details]:
        vids = details(c["mediaType"], c["id"]).get("relatedVideos") or []
        if any(v.get("key") == video["id"] for v in vids):
            return found(c, "trailer-id")
    seasons = {SEASON_NUM.sub("", q) for q in queries if SEASON_NUM.search(q)}
    hinted = "tv" if tv or exact and exact[0]["_q"] in seasons else "movie"
    if any(c["mediaType"] == hinted for c in exact):
        exact = [c for c in exact if c["mediaType"] == hinted]
    if not exact:
        return None
    if year:
        exact.sort(key=lambda c: abs((_year(c) or year) - year))
    else:
        # no year in the title: trailers are for new releases, so prefer the newest
        exact.sort(key=lambda c: _year(c) or 0, reverse=True)
    return found(exact[0], "title")


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "trailer-sync", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


class Seerr:
    def __init__(self, key):
        self.h = {"X-Api-Key": key, "Content-Type": "application/json"}

    def get(self, path):
        return json.loads(http(SEERR_URL + path, headers=self.h)[1])

    def search(self, q):
        return self.get("/api/v1/search?page=1&query=" + urllib.parse.quote(q, safe="")).get("results", [])

    def details(self, media_type, tmdb_id):
        return self.get(f"/api/v1/{media_type}/{tmdb_id}")

    def watchlist(self, tmdb_id, media_type, title):
        body = json.dumps({"tmdbId": tmdb_id, "mediaType": media_type, "title": title}).encode()
        try:
            return http(SEERR_URL + "/api/v1/watchlist", body, self.h)[0]
        except urllib.error.HTTPError as e:
            return e.code


def fetch_rss(playlist_id):
    # shortcut: RSS shows only the 15 newest items; use --import for older ones
    url = "https://www.youtube.com/feeds/videos.xml?playlist_id=" + urllib.parse.quote(playlist_id)
    root = ET.fromstring(http(url)[1])
    return [
        {
            "id": e.findtext("yt:videoId", "", NS),
            "title": e.findtext("a:title", "", NS),
            "author": e.findtext("a:author/a:name", "", NS),
            "description": e.findtext("media:group/media:description", "", NS),
        }
        for e in root.findall("a:entry", NS)
    ]


def load_import(path):
    with open(path) as f:
        entries = json.load(f).get("entries", [])
    return [
        {"id": e["id"], "title": e.get("title") or "", "author": e.get("channel") or e.get("uploader") or "",
         "description": e.get("description") or ""}
        for e in entries if e.get("id")
    ]


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_FILE)


def run(seerr, videos, dry_run):
    state = load_state()
    for v in videos:
        if not v["id"] or v["id"] in state or v["title"] in ("Private video", "Deleted video"):
            continue
        try:
            m = match(v, seerr.search, seerr.details)
            if not m:
                print(f'UNMATCHED {v["id"]} "{v["title"]}" queries={parse(v["title"], v["author"])[0]}')
                continue
            tmdb_id, media_type, title, reason = m
            if dry_run:
                print(f'DRY {v["id"]} "{v["title"]}" -> {media_type}/{tmdb_id} "{title}" ({reason})')
                continue
            status = seerr.watchlist(tmdb_id, media_type, title)
            if status not in (200, 201, 409):
                print(f'ERROR {v["id"]} watchlist POST {media_type}/{tmdb_id} -> HTTP {status}')
                continue
            print(f'ADDED {v["id"]} "{v["title"]}" -> {media_type}/{tmdb_id} "{title}" ({reason}, HTTP {status})')
            state[v["id"]] = {"tmdbId": tmdb_id, "mediaType": media_type, "title": title}
            save_state(state)
        except Exception as e:  # one bad video or network blip must not stop the loop
            print(f'ERROR {v["id"]} "{v["title"]}": {e!r}')


def main(argv):
    once, dry_run = "--once" in argv, "--dry-run" in argv
    imp = argv[argv.index("--import") + 1] if "--import" in argv else None
    key = os.environ.get("SEERR_API_KEY") or open("/run/secrets/seerr_api_key").read().strip()
    seerr = Seerr(key)
    while True:
        try:
            run(seerr, load_import(imp) if imp else fetch_rss(PLAYLIST_ID), dry_run)
        except Exception as e:
            print(f"ERROR run: {e!r}")
        if once or imp:
            return
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main(sys.argv[1:])
