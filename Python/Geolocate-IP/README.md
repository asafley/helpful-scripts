Geolocate-IP.py — Geolocate IP addresses with MaxMind

- Purpose: Look up geolocation and network details for an IP using MaxMind’s web services, cache results in SQLite with a TTL, and log activity.
- Script: `Python/Geolocate-IP/Geolocate-IP.py`

Features

- Supports explicit IPv4/IPv6 or "me" to use the caller’s public IP via MaxMind.
- Queries MaxMind GeoIP editions (GeoIP2 and GeoLite) over HTTPS with Basic Auth.
- Caches results in SQLite (geo.db) with created_at/updated_at and TTL-based reuse; use --force to bypass cache.
- Stores rich fields (city, country, continent, lat/lon, time zone, postal, subdivisions, ASN/ISP/Org, connection type, static_ip_score, user_type, network, ip_address).
- Simple logging to geo.log and exit codes suitable for cron/automation.

Quick Start

- Copy `Python/Geolocate-IP/config.json.ex` to `config.json` and set your MaxMind Account ID and License Key.
- Run: `python3 Python/Geolocate-IP/Geolocate-IP.py` (uses "me" by default)

Configuration (config.json)

- Top-level keys
  - `general`
    - `ttl` (number): Cache TTL in days for a saved IP before refreshing (default 7).
  - `maxmind`
    - `account` (string): MaxMind Account ID.
    - `key` (string): MaxMind License Key.
    - `pretty` (bool, optional): Append `?pretty` to responses (cosmetic).
    - `edition` (string): One of the keys in `editions` below.
    - `editions` (object): Map of edition name to base URL. Provided defaults include:
      - `geoip-country`: https://geoip.maxmind.com/geoip/v2.1/country/
      - `geoip-cityplus`: https://geoip.maxmind.com/geoip/v2.1/city/
      - `geoip-insights`: https://geoip.maxmind.com/geoip/v2.1/insights/
      - `geolite-country`: https://geolite.info/geoip/v2.1/country/
      - `geolite-city`: https://geolite.info/geoip/v2.1/city/

Example

```
{
  "general": { "ttl": 7 },
  "maxmind": {
    "account": "MAXMIND_ID",
    "key": "MAXMIND_KEY",
    "pretty": true,
    "edition": "geolite-country",
    "editions": {
      "geoip-country": "https://geoip.maxmind.com/geoip/v2.1/country/",
      "geoip-cityplus": "https://geoip.maxmind.com/geoip/v2.1/city/",
      "geoip-insights": "https://geoip.maxmind.com/geoip/v2.1/insights/",
      "geolite-country": "https://geolite.info/geoip/v2.1/country/",
      "geolite-city": "https://geolite.info/geoip/v2.1/city/"
    }
  }
}
```

CLI Usage

- `--ip` IP address to geolocate. Default `me`.
- `--force` Force refresh from MaxMind, ignoring cached value.

Examples

- Basic run (your public IP):
  - `python3 Python/Geolocate-IP/Geolocate-IP.py`
- Specific IP (IPv4/IPv6):
  - `python3 Python/Geolocate-IP/Geolocate-IP.py --ip 8.8.8.8`
- Force refresh:
  - `python3 Python/Geolocate-IP/Geolocate-IP.py --ip 8.8.8.8 --force`

What It Does

- Loads config, validates selected `edition`, initializes SQLite if needed.
- If `--ip me`, queries MaxMind for the caller’s IP; otherwise validates and uses the provided IP.
- Checks cache by IP (except for `me`) and returns cached data if not expired (`ttl` days).
- When fetching, performs HTTPS GET to `${editions[edition]}{ip}` with Basic Auth and optional `?pretty`.
- Extracts and saves fields, logs remaining queries (if present), and upserts into `geoip` table.

Database

- SQLite DB path: `geo.db` in the working directory.
- Table `geoip` (created automatically):
  - `ip_address` (PRIMARY KEY), `network`, `city_name`, `continent_code`, `continent_name`,
    `country_iso_code`, `country_name`, `accuracy_radius`, `latitude`, `longitude`, `time_zone`,
    `postal_code`, `subdivisions` (JSON), `static_ip_score`, `user_type`, `asn`, `asn_org`,
    `connection_type`, `isp`, `organization`, `updated_at`, `created_at`.
- Cache behavior: entries are reused until `ttl` days since `updated_at`; use `--force` to refresh.

Logging & Exit Codes

- Logs to console and `geo.log` in the working directory.
- Exit code 0 on success; 1 on errors (e.g., config missing/invalid, bad IP, DB issues, HTTP failures).

Scheduling

- Cron example (refresh public IP hourly):
  - `0 * * * * /usr/bin/python3 /path/Python/Geolocate-IP/Geolocate-IP.py`
- Cron example (refresh a specific IP daily, forcing update):
  - `5 0 * * * /usr/bin/python3 /path/Python/Geolocate-IP/Geolocate-IP.py --ip 8.8.8.8 --force`

Security Notes

- Keep `config.json` secure; do not commit your Account ID or License Key.
- Use a least-privilege MaxMind key and rotate regularly.

Troubleshooting

- Invalid edition: Ensure `maxmind.edition` matches a key in `maxmind.editions`.
- Auth errors: Verify `account` and `key` and that your key allows the chosen edition.
- No cache hit: Entry may be expired; use `--force` to fetch fresh data.
- SSL/network issues: Confirm outbound HTTPS to MaxMind endpoints is allowed.
