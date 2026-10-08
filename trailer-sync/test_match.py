import unittest

from sync import match, parse


def movie(i, title, date, original=None, videos=()):
    return {"mediaType": "movie", "id": i, "title": title, "originalTitle": original or title,
            "releaseDate": date, "relatedVideos": [{"key": k} for k in videos]}


def tv(i, name, date, videos=()):
    return {"mediaType": "tv", "id": i, "name": name, "originalName": name, "firstAirDate": date,
            "relatedVideos": [{"key": k} for k in videos]}


def run(title, results, vid="vid", author="", description=""):
    by_id = {(r["mediaType"], r["id"]): r for r in results}
    return match({"id": vid, "title": title, "author": author, "description": description},
                 lambda q: results, lambda t, i: by_id[(t, i)])


class Parse(unittest.TestCase):
    def test_strip_noise_keep_numbers(self):
        self.assertEqual(parse("28 Years Later | Official Trailer 2 (2025)")[0:2], (["28 Years Later"], 2025))
        self.assertEqual(parse("Final Destination Bloodlines - Final Trailer")[0], ["Final Destination Bloodlines"])

    def test_drop_network_and_channel(self):
        q, year, is_tv = parse("THE BEAR | Season 4 Official Trailer | FX")
        self.assertEqual((q, year, is_tv), (["THE BEAR"], None, True))
        self.assertEqual(parse("Dune | Trailer | JoBlo Movie Network", "JoBlo Movie Network")[0], ["Dune"])

    def test_french(self):
        self.assertEqual(parse("Le Comte de Monte-Cristo - Bande-annonce officielle VF")[0],
                         ["Le Comte de Monte-Cristo"])

    def test_colon_prefix_last(self):
        self.assertEqual(parse("Dune: Part Two | Official Trailer 3")[0], ["Dune: Part Two", "Dune"])


class Match(unittest.TestCase):
    def test_trailer_id_beats_title(self):
        res = [movie(841, "Dune", "1984-12-14"), movie(693134, "Dune: Part Two", "2024-02-27", videos=["vid"])]
        self.assertEqual(run("Dune: Part Two | Official Trailer 3", res)[::3], (693134, "trailer-id"))

    def test_original_title(self):
        res = [movie(1, "The Count of Monte Cristo", "2024-06-28", "Le Comte de Monte-Cristo"),
               movie(2, "The Count of Monte Cristo", "1954-11-24", "Le Comte de Monte-Cristo")]
        self.assertEqual(run("Le Comte de Monte-Cristo - Bande-annonce officielle VF", res)[:2], (1, "movie"))

    def test_tv_hint(self):
        res = [movie(9, "The Bear", "1988-10-19"), tv(136315, "The Bear", "2022-06-23")]
        self.assertEqual(run("THE BEAR | Season 4 Official Trailer | FX", res)[:2], (136315, "tv"))

    def test_remake_year(self):
        res = [movie(37136, "The Naked Gun", "1988-12-02"), movie(1035259, "The Naked Gun", "2025-08-01")]
        self.assertEqual(run("THE NAKED GUN (1988) Trailer", res)[0], 37136)
        self.assertEqual(run("The Naked Gun (2025) - Official Trailer", res)[0], 1035259)

    def test_year_conflict_rejects(self):
        self.assertIsNone(run("Dune (2027) Trailer", [movie(841, "Dune", "1984-12-14")]))

    def test_apostrophe(self):
        res = [movie(5, "Let's Have Kids", "2026-11-06")]
        self.assertEqual(run("LET'S HAVE KIDS | Official Trailer (2026) 4K", res, author="JoBlo Movie Network")[0], 5)

    def test_movie_preferred_without_tv_hint(self):
        res = [tv(240456, "Le Comte de Monte-Cristo", "2026-01-01"),
               movie(1, "The Count of Monte Cristo", "2024-06-28", "Le Comte de Monte-Cristo")]
        self.assertEqual(run("Le Comte de Monte-Cristo - Bande-annonce officielle VF", res)[:2], (1, "movie"))

    def test_trailing_season_number(self):
        self.assertEqual(run("Stranger Things 5 | Official Trailer | Netflix",
                             [movie(182026, "Stranger Things", "2010-01-01"),
                              tv(66732, "Stranger Things", "2016-07-15")])[:2], (66732, "tv"))
        res = [movie(10193, "Toy Story 3", "2010-06-16"), movie(862, "Toy Story", "1995-10-30"),
               movie(1084244, "Toy Story 5", "2026-06-19")]
        self.assertEqual(run("Toy Story 5 | Official Trailer", res)[0], 1084244)

    def test_no_match(self):
        self.assertIsNone(run("Top 10 Movies of 2026", [movie(1, "Top Gun", "1986-05-16")]))


if __name__ == "__main__":
    unittest.main()
