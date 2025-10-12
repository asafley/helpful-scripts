TestDNS.py — Monitor DNS Servers

- Purpose: Periodically test DNS resolution for a list of FQDNs against one or more nameservers, record results to SQLite, log activity, and optionally email a summary and/or periodic digest.
- Script: `Python/Monitor-DNS-Servers/TestDNS.py`

Features

- Tests multiple FQDNs against multiple IPv4/IPv6 nameservers using `socket.getaddrinfo`.
- Measures resolution time per query and marks failures when resolution or connectivity fails.
- Persists each run and per-query results in a local SQLite database.
- Produces an HTML email with a pass/fail table and timings; optional periodic digest with aggregate stats.
- Simple logging to a file and exit codes suitable for monitoring/cron.

Quick Start

- Copy `Python/Monitor-DNS-Servers/config.json.ex` to `config.json` and edit values.
- Run: `python3 Python/Monitor-DNS-Servers/TestDNS.py --config config.json`

Configuration (config.json)

- Top-level keys
  - `nameservers`: Array of DNS server IPs. IPv4 or IPv6 supported, e.g. `["1.1.1.1", "8.8.8.8", "2606:4700:4700::1111"]`.
  - `domains`: Array of FQDNs to query, e.g. `["example.com", "google.com"]`.
  - `email`: SMTP and recipient settings for notifications
    - `host` (string): SMTP host
    - `port` (number): SMTP port (e.g., 587 or 465)
    - `ssl` (bool): Use SMTP over SSL (`true`) or STARTTLS (`false`)
    - `username` (string): SMTP username (optional)
    - `password` (string): SMTP password (optional)
    - `from` (string): Sender email address
    - `to` (string): Recipient email address
    - `from_name` (string, optional): Display name for sender; also used in email subjects
  - `general`: notification behavior
    - `send_pass` (bool): Send email when all checks pass (default true)
    - `send_fail` (bool): Send email when any check fails (default true)
    - `digest_minutes` (number): Lookback window for digest aggregation. Used only when `--digest` is passed.

Example

```
{
  "nameservers": ["1.1.1.1", "8.8.8.8"],
  "domains": ["example.com", "google.com"],
  "email": {
    "host": "smtp.example.com",
    "port": 587,
    "ssl": false,
    "username": "",
    "password": "",
    "from": "dnscheck@example.com",
    "to": "ops@example.com",
    "from_name": "Acme Corp"
  },
  "general": {
    "send_pass": true,
    "send_fail": true,
    "digest_minutes": 60
  }
}
```

CLI Usage

- `--config` Path to JSON config file. Default `config.json`.
- `--log-path` Path to log file. Default `dns.log`.
- `--db-path` Path to SQLite DB file. Default `dns.db`.
- `--digest` When present, compute and email a digest summary covering the last `general.digest_minutes` minutes/hours/days.

Examples

- Basic run with defaults in CWD:
  - `python3 Python/Monitor-DNS-Servers/TestDNS.py`
- Custom locations:
  - `python3 Python/Monitor-DNS-Servers/TestDNS.py --config /etc/dns-check.json --log-path /var/log/dns-check.log --db-path /var/lib/dns-check.db`
- Send a digest instead of the per-run table:
  - `python3 Python/Monitor-DNS-Servers/TestDNS.py --config config.json --digest`

What It Does

- Connectivity check: Opens UDP to each nameserver on port 53; uses IPv6 when the IP contains `:` otherwise IPv4.
- Resolution: Calls `socket.getaddrinfo(fqdn, None, family)` and times it. Success returns duration in ms; failure records `0.0`.
- Results:
  - If any query fails for an FQDN on any nameserver, that row is marked FAIL and the overall run may be considered FAIL.
  - HTML email includes a grid of FQDN × nameserver with timing or failure per cell; overall PASS/FAIL per FQDN.
- Digest (with `--digest`): Sends an aggregate email covering recent runs within the `digest_minutes` window:
  - Total runs, pass/fail counts, total queries, failures
  - Average resolution time overall, by FQDN, and by nameserver
  - Top failing domains

Database

- SQLite DB path is set by `--db-path` (default `dns.db`). Tables are created automatically:
  - `runs (id, timestamp, status)` with status in {`START`, `PASS`, `FAIL`, `INCOMPLETE`}
  - `results (id, run_id, fqdn, nameserver, result, perf)` where `result` in {`PASS`, `FAIL`} and `perf` is ms (0 when failed)
- Each invocation inserts one row in `runs` and one row per FQDN×nameserver in `results`.

Logging & Exit Codes

- Logs to console and to `--log-path` (default `dns.log`).
- Exit code 0 on success; 1 when the script reports errors (e.g., no config, email failure, etc.).

Scheduling

- Cron example (every 5 minutes, normal run):
  - `*/5 * * * * /usr/bin/python3 /path/Python/Monitor-DNS-Servers/TestDNS.py --config /path/config.json --log-path /var/log/dns-check.log --db-path /var/lib/dns-check.db`
- Cron example (hourly digest):
  - `0 * * * * /usr/bin/python3 /path/Python/Monitor-DNS-Servers/TestDNS.py --config /path/config.json --digest`

Security Notes

- If SMTP auth is required, set `username` and `password`. Prefer storing config with appropriate file permissions.
- Would recommend using SMTP Relay when working with Google Workspace or Microsoft 365/Exchange Online
- When `ssl` is false, STARTTLS is used. Ensure your SMTP server supports it.

Troubleshooting

- No emails: Verify SMTP `host`, `port`, and `ssl` settings; check credentials if set. Review `--log-path`.
- All queries fail: Confirm nameserver reachability on UDP/53 and that the host can resolve via those servers.
- Empty reports: Ensure `domains` and `nameservers` arrays are populated and valid in `config.json`.
- Digest empty: Digest only includes runs within the last `general.digest_minutes` window and requires `--digest`.
