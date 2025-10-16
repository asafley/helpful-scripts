VisualizeIP.py — Visualize CSV IP activity with geolocation

- Purpose: Ingest a CSV of sign-ins/activity, geolocate each IP using MaxMind via GeolocateIP.py, persist results, and generate charts/maps.
- Script: Python/Visualize-IP/VisualizeIP.py (depends on Python/Visualize-IP/GeolocateIP.py and config.json)

Features

- Reads a CSV, normalizes headers (lowercase, spaces and symbols -> underscores), infers column types, and writes a per-run SQLite DB (data_YYYYmmdd_HHMMSS.db).
- Geolocates each ip_address via GeolocateIP.get_ip_info() with caching in geo.db (TTL from config.json).
- Persists enriched IP details into ip_info table and creates visualizations:
  - country_counts_YYYYmmdd_HHMMSS.png
  - us_state_counts_YYYYmmdd_HHMMSS.png
  - ip_geolocation_map_YYYYmmdd_HHMMSS.png (world)
  - us_ip_geolocation_map_YYYYmmdd_HHMMSS.png
- Logs to Visualize-IP_YYYYmmdd_HHMMSS.log.

Basic CSV requirements

- Header row required.
- Required column: ip_address (case-insensitive; e.g., "IP Address" becomes ip_address after normalization).
- Optional columns: date (ISO 8601, e.g., 2025-10-15T08:13:39-06:00), user. Extra columns are allowed.
- Comma-separated, UTF-8. Quote fields that contain commas. Avoid mixed types in the same column (first data row drives type inference).

Quick start

- Ensure config.json has valid MaxMind credentials (see below).
- Install deps: pip install requests matplotlib cartopy
  - macOS: brew install geos proj; then pip install cartopy
- Run: python3 Python/Visualize-IP/VisualizeIP.py --input Python/Visualize-IP/Aspen_User_Logins_Updated_091525-101525.csv

Outputs per run

- SQLite: data_YYYYmmdd_HHMMSS.db with tables:
  - data: your CSV content (schema inferred from first row).
  - ip_info: ip_address, date, user, city, state/state_code, country/country_code, continent/continent_code, postal_code, latitude, longitude.
- Images: country, US state bar charts; world and US maps as listed above.
- Log: Visualize-IP_YYYYmmdd_HHMMSS.log.

Dependency: GeolocateIP.py and config.json

- VisualizeIP imports GeolocateIP.get_ip_info(). That module:
  - Reads config.json to call MaxMind web services and caches results in geo.db with TTL.
  - Creates geo.db table geoip with rich fields (city/country/lat/lon/time zone/subdivisions/ASN/ISP/etc.).
- Minimal config.json keys:
  - general.ttl: integer days to reuse cached lookups (default 7).
  - maxmind.account: your MaxMind Account ID.
  - maxmind.key: your MaxMind License Key.
  - maxmind.edition: key present in maxmind.editions mapping (e.g., geolite-country, geolite-city, geoip-insights).
  - maxmind.editions: map of edition name -> base URL.
- To force-refresh specific IPs in the cache: python3 Python/Visualize-IP/GeolocateIP.py --ip 8.8.8.8 --force

CLI usage

- python3 Python/Visualize-IP/VisualizeIP.py --input /path/to/file.csv

What it does

- Reads CSV and builds data_YYYYmmdd_HHMMSS.db schema based on row 1 types.
- For each row with ip_address:
  - Calls get_ip_info(ip) which consults geo.db cache (TTL) or fetches from MaxMind.
  - Saves an enriched, simplified record into ip_info in data_....db.
- Generates charts and maps with matplotlib and cartopy.

Troubleshooting

- "No 'ip_address' column": ensure the CSV header contains it (case-insensitive; normalization applies).
- cartopy import errors: install geos/proj (brew install geos proj) before pip install cartopy.
- MaxMind errors: verify config.json, edition key exists in editions, and credentials are valid.
- Empty maps: no latitude/longitude returned for rows; verify IPs and that lookups succeed.

Security notes

- Keep config.json secret. Do not commit MaxMind credentials.
- Prefer a least-privilege MaxMind license key and rotate regularly.
