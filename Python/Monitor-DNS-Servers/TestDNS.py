#!/bin/python3

# Import statements
import os
import sys
import json
import socket
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
import argparse
from datetime import datetime
import sqlite3
from datetime import timedelta

# A function to write a log file
def Log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"

    # Print Log to Console
    print(line)

    # Try to write log to file
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception as ex:
        print(f"[{timestamp}] Failed to write log to {LOG_PATH}: {ex}")

# A function to initialize database
def InitDB():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            fqdn TEXT NOT NULL,
            nameserver TEXT NOT NULL,
            result TEXT NOT NULL,
            perf REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        )
    """)

    conn.commit()
    conn.close()

# A function to log a new run
def StartRun():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Update any existing runs with status 'START' or unfinished status to 'INCOMPLETE'
    c.execute("UPDATE runs SET status = 'INCOMPLETE' WHERE status = 'START'")

    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO runs (timestamp, status) VALUES (?, ?)", (timestamp, "START"))
    run_id = c.lastrowid

    conn.commit()
    conn.close()

    return run_id

# A function to save the results
def SaveResult(run_id, fqdn, nameserver, result, perf):
    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute(
        "INSERT INTO results (run_id, fqdn, nameserver, result, perf) VALUES (?, ?, ?, ?, ?)",
        (run_id, fqdn, nameserver, result, perf)
    )

    conn.commit()
    conn.close()

# A function to finalize the run with the overall status
def FinalizeRun(run_id, status):
    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute("UPDATE runs SET status = ? WHERE id = ?", (status, run_id))

    conn.commit()
    conn.close()

# A function to read JSON File
# Return List of Nameservers, List of Domains to Check, and Email Settings
def ReadJson(filepath="config.json"):
    if not os.path.exists(filepath):
        Log(f"JSON file '{filepath}' not found.")
        return [], [], {}

    Log(f"Reading JSON file - {filepath}")

    with open(filepath, "r") as f:
        try:
            data = json.load(f)
            Log(f"Loaded JSON file")
        except Exception as e:
            Log(f"Error reading JSON: {e}")
            return [], [], {}

    nameservers = data.get("nameservers", [])
    domains = data.get("domains", [])
    email = data.get("email", {})
    
    # General Options
    settings = data.get("general", {})

    return nameservers, domains, email, settings

# A function that will test if a DNS Server is properly working
# Return non-negative for no errors
def TestDNS(nameserver, fqdn):
    try:
        family = socket.AF_INET6 if ':' in nameserver else socket.AF_INET

        with socket.socket(family, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.connect((nameserver, 53))

        start = datetime.now()
        socket.getaddrinfo(fqdn, None, family)
        end = datetime.now()
        duration = round((end - start).total_seconds() * 1000, 3)

        Log(f"Successfully queried {fqdn} with server {nameserver} in {duration} ms")

        return duration
    except Exception as ex:
        Log(f"Failed to query {fqdn} with server {nameserver}")
        return 0.0

def SendEmail(email, subject, body):
    try:
        sender_name = email.get("from_name", "")
        senderFrom = email.get("from")
        recipientTo = email.get("to")
        host = email.get("host")
        port = email.get("port")
        useSsl = email.get("ssl", False)
        username = email.get("username", "") or ""
        password = email.get("password", "") or ""

        msg = EmailMessage()
        # attach display name if provided
        if sender_name:
            msg["From"] = formataddr((sender_name, senderFrom))
        else:
            msg["From"] = senderFrom

        msg["To"] = recipientTo
        msg["Subject"] = subject
        msg.set_content(body, subtype="html")

        if useSsl:
            with smtplib.SMTP_SSL(host, port) as server:
                if username or password:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                if username or password:
                    server.login(username, password)
                server.send_message(msg)

        return False
    except Exception as ex:
        Log(f"Error sending email - {ex}")
        return True

# Function to prep a digest summary
def SendDigestSummary(db_path, email, company, digest_minutes):
    if digest_minutes <= 0:
        return True

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Select runs from within the digest window
    window = datetime.now() - timedelta(minutes=digest_minutes)
    c.execute("SELECT id, timestamp, status FROM runs WHERE timestamp >= ?", (window.isoformat(),))
    runs = c.fetchall()
    if not runs:
        Log("No recent runs found for digest window.")
        return

    run_ids = [r[0] for r in runs]
    placeholders = ",".join("?" * len(run_ids))

    # Run statistics
    total_runs = len(runs)
    pass_count = sum(1 for r in runs if r[2] == "PASS")
    fail_count = total_runs - pass_count

    c.execute(f"SELECT COUNT(*) FROM results WHERE run_id IN ({placeholders})", run_ids)
    total_queries = c.fetchone()[0]

    c.execute(f"SELECT COUNT(*) FROM results WHERE run_id IN ({placeholders}) AND result = 'FAIL'", run_ids)
    total_failures = c.fetchone()[0]

    # Overall average resolution time
    c.execute(f"SELECT ROUND(AVG(perf), 2) FROM results WHERE run_id IN ({placeholders}) AND perf > 0", run_ids)
    avg_perf = c.fetchone()[0] or 0.0

    c.execute(f"""
        SELECT fqdn, 
               SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) AS pass_count,
               SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END) AS fail_count
        FROM results
        WHERE run_id IN ({placeholders})
        GROUP BY fqdn
        ORDER BY fail_count DESC
        LIMIT 10
    """, run_ids)
    fqdn_rows = c.fetchall()

    c.execute(f"""
        SELECT fqdn, ROUND(AVG(perf), 2) as avg_perf
        FROM results
        WHERE run_id IN ({placeholders}) AND perf > 0
        GROUP BY fqdn
        ORDER BY avg_perf DESC
    """, run_ids)
    perf_fqdn_rows = c.fetchall()

    c.execute(f"""
        SELECT nameserver, ROUND(AVG(perf), 2) as avg_perf
        FROM results
        WHERE run_id IN ({placeholders}) AND perf > 0
        GROUP BY nameserver
        ORDER BY avg_perf DESC
    """, run_ids)
    perf_ns_rows = c.fetchall()

    conn.close()

    digest_unit = "minutes"
    digest_value = digest_minutes
    if (digest_value >= 60):
        digest_value = digest_value / 60
        digest_unit = "hours"
    
    if (digest_value >= 24):
        digest_value = digest_value / 24
        digest_unit = "days"

    digest_value = round(digest_value, 2)
    if digest_value.is_integer():
        digest_value = int(digest_value)

    if (digest_value <= 1):
        digest_unit = digest_unit[:-1]

    # Build digest HTML
    html = "<html><body>"
    html += f"<h2>DNS Digest Summary (Last {digest_value} {digest_unit})</h2>"
    html += f"<h3>{company}</h3>"
    html += "<ul>"
    html += f"<li>Total Runs: {total_runs}</li>"
    html += f"<li>Successful Runs: {pass_count}</li>"
    html += f"<li>Failed Runs: {fail_count}</li>"
    html += f"<li>Total Queries: {total_queries}</li>"
    html += f"<li>Failures Detected: {total_failures}</li>"
    html += f"<li>Average Resolution Time: {avg_perf} ms</li>"
    html += "</ul>"

    # Quantitative Measurements of pass/fail
    html += "<h3>Top Failing Domains</h3>"
    html += "<table border='1' cellpadding='5' cellspacing='0'><tr><th>FQDN</th><th>Passes</th><th>Fails</th></tr>"
    for fqdn, passes, fails in fqdn_rows:
        html += f"<tr><td>{fqdn}</td><td>{passes}</td><td>{fails}</td></tr>"
    html += "</table></body></html>"

    # Average performance per FQDN
    html += "<h3>Average Resolution Time per FQDN</h3>"
    html += "<table border='1' cellpadding='5' cellspacing='0'><tr><th>FQDN</th><th>Avg Time (ms)</th></tr>"
    for fqdn, avg in perf_fqdn_rows:
        html += f"<tr><td>{fqdn}</td><td>{avg}</td></tr>"
    html += "</table>"

    # Average performance per Nameserver
    html += "<h3>Average Resolution Time per Nameserver</h3>"
    html += "<table border='1' cellpadding='5' cellspacing='0'><tr><th>Nameserver</th><th>Avg Time (ms)</th></tr>"
    for ns, avg in perf_ns_rows:
        html += f"<tr><td>{ns}</td><td>{avg}</td></tr>"
    html += "</table>"


    subject = f"[Digest] DNS Summary - {company} - Last {digest_value} {digest_unit}"

    Log("Sending digest summary email...")

    return SendEmail(email, subject, html)

# The main function as script is to be ran as a program
# Return False/0 for successful run
def main():
    nameservers, fqdns, email, settings = ReadJson(JSON_PATH)

    # Initialize the database
    InitDB()
    run_id = StartRun()

    company = email.get("from_name", "")

    if company in (None, ""):
        subject = "[SUCCESS] - DNS Server Check"
    else:
        subject = f"[SUCCESS] - {company} - DNS Server Check"

    if nameservers in (None, [], {}):
        Log("No nameservers found in configuration.")
        return True
    
    if fqdns in (None, [], {}):
        Log("No domains found in configuration.")
        return True
    
    results = []
    fail = False

    for fqdn in fqdns:
        result = {
            "name": fqdn,
            "overall": "PASS"
        }

        for nameserver in nameservers:
            result[nameserver] = TestDNS(nameserver, fqdn)

            if result[nameserver] <= 0:
                SaveResult(run_id, fqdn, nameserver, "FAIL", 0)
                fail = True
                result["overall"] = "FAIL"
                result[nameserver] = 0.0
            else:
                SaveResult(run_id, fqdn, nameserver, "PASS", result[nameserver])
        
        results.append(result)
    
    # Save the results to the SQLite Datbase
    if fail:
        # Finalize the run with a fail
        Log("Finalizing the failed run in database")
        FinalizeRun(run_id, "FAIL")
        # Change the subject for the email
        subject = f"[FAIL] - {company} - DNS Server Check"
    else:
        # Finalize the run with a pass
        Log("Finalizing the successful run in database")
        FinalizeRun(run_id, "PASS")

    # Check if it is time to process a digest

    # Build styled HTML table summarizing DNS check results
    html = """<html><body><table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;"><tr><th>FQDN</th><th>Overall</th>"""

    for nameserver in nameservers:
        html += f"<th>{nameserver}</th>"

    html += "</tr>"

    for result in results:
        overall_color = "#ccffcc" if result['overall'] == "PASS" else "#ffcccc"
        html += f"<tr><td>{result['name']}</td><td style='background-color:{overall_color}'>{result['overall']}</td>"

        for nameserver in nameservers:
            status = result.get(nameserver, 0)
            color = "#ccffcc" if status > 0 else "#ffcccc"
            html += f"<td style='background-color:{color}'>{status} ms</td>"

        html += "</tr>"

    html += "</table></body></html>"

    if DIGEST:
        Log("Requested a digest")
        SendDigestSummary(DB_PATH, email, company, settings.get("digest_minutes", 60))
    else:
        Log("Skipping digest")

    # Check if the results failed
    if fail:
        # If Failed check if not sending fail emails
        if not settings.get("send_fail", True):
            Log("Skip sending a fail email")
            # Exit with 0
            return False

    # Check if results passed
    if not fail: 
        if not settings.get("send_pass", True):
            Log("Skip sending a pass email")
            return False

    # Send the HTML table via email
    Log("Sending an email")
    if SendEmail(email, subject, html):
        Log("Failed to send an email")
        return True
    
    return False

# Bootstrap into the main function
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor DNS Servers")
    parser.add_argument("--log-path", type=str, default="dns.log", help="Path to log file")
    parser.add_argument("--db-path", type=str, default="dns.db", help="Path to SQLite3 database file")
    parser.add_argument("--config", type=str, default="config.json", help="Path to JSON config file")
    parser.add_argument("--digest", action="store_true", default=False, help="Whether or not to calculate digest")
    args = parser.parse_args()

    LOG_PATH = args.log_path
    JSON_PATH = args.config
    DB_PATH = args.db_path
    DIGEST = args.digest

    if main():
        Log("Exit with errors")
        sys.exit(1)
    else:
        Log("Exit with no errors")
        sys.exit(0)