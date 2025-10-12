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
def SaveResult(run_id, fqdn, nameserver, result):
    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute(
        "INSERT INTO results (run_id, fqdn, nameserver, result) VALUES (?, ?, ?, ?)",
        (run_id, fqdn, nameserver, result)
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
# Return False for no errors
def TestDNS(nameserver, fqdn):
    try:
        family = socket.AF_INET6 if ':' in nameserver else socket.AF_INET

        with socket.socket(family, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.connect((nameserver, 53))

        socket.getaddrinfo(fqdn, None, family)

        Log(f"Successfully query {fqdn} with server {nameserver}")

        return False
    except Exception as ex:
        Log(f"Failed to query {fqdn} with server {nameserver}")
        return True

def SendEmail(email, subject, body):
    try:
        sender_name = email.get("from_name", "")  # optional display name
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
            result[nameserver] = "PASS"

            if TestDNS(nameserver, fqdn):
                SaveResult(run_id, fqdn, nameserver, "FAIL")
                fail = True
                result["overall"] = "FAIL"
                result[nameserver] = "FAIL"
            else:
                SaveResult(run_id, fqdn, nameserver, "PASS")
        
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

    # Build styled HTML table summarizing DNS check results
    html = """<html><body><table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;"><tr><th>FQDN</th><th>Overall</th>"""

    for nameserver in nameservers:
        html += f"<th>{nameserver}</th>"

    html += "</tr>"

    for result in results:
        overall_color = "#ccffcc" if result['overall'] == "PASS" else "#ffcccc"
        html += f"<tr><td>{result['name']}</td><td style='background-color:{overall_color}'>{result['overall']}</td>"

        for nameserver in nameservers:
            status = result.get(nameserver, "")
            color = "#ccffcc" if status == "PASS" else "#ffcccc"
            html += f"<td style='background-color:{color}'>{status}</td>"

        html += "</tr>"

    html += "</table></body></html>"

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
    args = parser.parse_args()

    LOG_PATH = args.log_path
    JSON_PATH = args.config
    DB_PATH = args.db_path

    if main():
        Log("Exit with errors")
        sys.exit(1)
    else:
        Log("Exit with no errors")
        sys.exit(0)