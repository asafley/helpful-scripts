#!/bin/python3

# Import statements
import os
import sys
import json
import socket
import smtplib
from email.message import EmailMessage

# A function to read JSON File
# Return List of Nameservers, List of Domains to Check, and Email Settings
def ReadJson(filepath="config.json"):
    if not os.path.exists(filepath):
        print(f"JSON file '{filepath}' not found.")
        return [], [], {}

    with open(filepath, "r") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return [], [], {}

    nameservers = data.get("nameservers", [])
    domains = data.get("domains", [])
    email = data.get("email", {})

    return nameservers, domains, email

# A function that will test if a DNS Server is properly working
# Return False for no errors
def TestDNS(nameserver, fqdn):
    try:
        family = socket.AF_INET6 if ':' in nameserver else socket.AF_INET

        with socket.socket(family, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.connect((nameserver, 53))

        socket.getaddrinfo(fqdn, None, family)

        return False
    except Exception:
        return True

def SendEmail(email, subject, body):
    try:
        senderFrom = email.get("from")
        recipientTo = email.get("to")
        host = email.get("host")
        port = email.get("port")
        useSsl = email.get("ssl", False)
        username = email.get("username", "") or ""
        password = email.get("password", "") or ""

        msg = EmailMessage()
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
        print(f"Error sending email - {ex}")
        return True

# The main function as script is to be ran as a program
# Return False/0 for successful run
def main():
    nameservers, fqdns, email = ReadJson()

    company = "Example"
    subject = f"[SUCCESS] - {company} - DNS Server Check Pass"

    if nameservers in (None, [], {}):
        return True
    
    if fqdns in (None, [], {}):
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
                fail = True
                result["overall"] = "FAIL"
                result[nameserver] = "FAIL"
        
        results.append(result)
    
    if fail:
        subject = f"[FAIL] - {company} - DNS Server Check Failed for one or more tests"

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

    # Send the HTML table via email
    if SendEmail(email, subject, html):
        return True
    
    return False

# Bootstrap into the main function
if __name__ == "__main__":
    if main():
        print("Exit with errors")
        sys.exit(1)
    else:
        print("Exit with no errors")
        sys.exit(0)