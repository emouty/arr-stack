# Configuration

This guide explains how to configure the project using Docker secrets for sensitive data and environment variables for general configuration. This project is based on [mediastack](https://github.com/geekau/mediastack/tree/master).

## File Structure

```
├── .env                   # Environment variables
├── docker-compose.yaml    # Docker services configuration
└── secret.d/              # Directory containing secrets
    ├── cloudflared_apikey # Cloudflare Tunnel API token
    ├── mail_password      # SMTP password (optional)
    ├── plex_claim         # Plex claim token
    ├── vpn_password       # VPN password
    └── vpn_username       # VPN username
```

## Setting Up Secrets

Secrets are stored as plain text files in the `secret.d` directory. Here's how to configure them:

1. **Create the secrets directory** (if it doesn't exist already):
   ```bash
   mkdir -p secret.d
   ```

2. **Create/modify each secret file** (one per line, no extra spaces):
    If you intend to use Plex as your Media Server, then enter your Plex Claim information in a secret named `plex_claim`, to link this Plex Media Server to your Plex account


   ```bash
   echo "your_vpn_username" > secret.d/vpn_username
   echo "your_vpn_password" > secret.d/vpn_password
   echo "your_plex_token" > secret.d/plex_claim
   echo "your_email_password" > secret.d/mail_password
   echo "your_cloudflared_token" > secret.d/cloudflared_apikey
   ```

3. **Set restrictive permissions**:
   ```bash
   chmod 600 secret.d/*
   ```

## Configuring the `.env` File

Rename .env file to

Ensure essential environment variables are properly configured in your `.env` file:

```ini
SERVER_HOSTNAME=<hostname>
# Folder paths
FOLDER_FOR_MEDIA=<path_to_media_folder>
FOLDER_FOR_DATA=<path_to_config_folder>

# VPN configuration
VPN_TYPE=openvpn
VPN_SERVICE_PROVIDER=<vpn_provider>
SERVER_COUNTRIES=<vpn_countries>
SERVER_REGIONS=<vpn_region>

# Email (for Watchtower. Optional)
MAIL_FROM=your_email@example.com
MAIL_HOST=smtp.yourservice.com
MAIL_PORT=465
MAIL_USERNAME=your_username
```

## Starting the Stack

Once configuration is complete, launch the stack with:

```bash
docker compose up -d
```

## Verifying Status

Check that all containers are running properly:

```bash
docker compose ps
```

## Troubleshooting

If you encounter issues:

1. Check logs: `docker compose logs [service]`
2. Ensure secret files exist and are accessible
3. Verify secret files permissions
4. Make sure paths in the `.env` file are correct
5. Check for any errors in the Docker engine: `docker system info`

## Maintaining Secrets

To update a secret:

1. Modify the corresponding file in `secret.d`
2. Restart the affected service: `docker compose restart [service]`

For example, to update the VPN password:
```bash
echo "new_vpn_password" > secret.d/vpn_password
docker compose restart gluetun
```

## Service Access

After successful deployment, services will be available at:

- Traefik Dashboard: `http://traefik.<my_host>.local`
- Plex: `http://plex.<my_host>.local`
- Radarr: `http://radarr.<my_host>.local`
- Sonarr: `http://sonarr.<my_host>.local`
- qBittorrent: `http://qbittorrent.<my_host>.local`
- Jellyfin: `http://jellyfin.<my_host>.local`
- Overseerr: `http://overseerr.<my_host>.local`
- Jellyseerr: `http://jellyseerr.<my_host>.local`
- Homarr: `http://homarr.<my_host>.local`
- Prowlarr: `http://prowlarr.<my_host>.local`
- Bazarr: `http://bazarr.<my_host>.local`
- SuggestArr: `http://suggestarr.<my_host>.local`
