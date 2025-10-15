#!/bin/python3

import argparse
from datetime import datetime
import os
import sqlite3
import sys
import json
import ipaddress
import requests

# Function to log messages to a file with timestamp
def Log(message, tee=True):
    # Generate the timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate the message line
    line = f"[{timestamp}] {message}"

    # Check if need to tee the log to console
    if (tee):
        # Print the console
        print(line)

    # Try to write the log to file
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"{line}\n")
    except Exception as ex:
        print(f"[{timestamp}] Failed to write log to {LOG_PATH}: {ex}")

# Function to read configuration from a JSON file
def ReadConfig(filepath="config.json"):
    Log(f"Reading config from {filepath}")
    if not os.path.isfile(filepath):
        Log(f"Config file {filepath} does not exist!")
        return None, None
    Log(f"Config file {filepath} loaded")

    try:
        with open(filepath, "r") as f:
            config = json.load(f)

            general = config.get("general", {})
            maxmind = config.get("maxmind", {})
    except Exception as ex:
        Log(f"Failed to read config file {filepath}: {ex}")
        return None, None

    return general, maxmind

# Function to initialize the SQLite database
def InitDatabase(filepath="geo.db"):
    Log(f"Initializing database at {filepath}")
    conn = sqlite3.connect(filepath)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geoip (
            ip_address TEXT PRIMARY KEY,
            network TEXT,  
            city_name TEXT,
            continent_code TEXT,
            continent_name TEXT,
            country_iso_code TEXT,
            country_name TEXT,
            accuracy_radius INTEGER,
            latitude REAL,
            longitude REAL,
            time_zone TEXT,
            postal_code TEXT,
            subdivisions TEXT,
            static_ip_score INTEGER,
            user_type TEXT,
            asn INTEGER,
            asn_org TEXT,
            connection_type TEXT,
            isp TEXT,
            organization TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

    return False

# Function to save IP information to the database
def SaveIPInfo(filepath="geo.db", ipinfo=None):
    if ipinfo in [None, {}]:
        Log(f"No IP info to save")
        return True
    
    # Check if database exists
    if not os.path.isfile(filepath):
        Log(f"Database file {filepath} does not exist!")
        return True
    
    # Check if database is initialized
    conn = sqlite3.connect(filepath)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='geoip';")
    if cursor.fetchone() is None:
        Log(f"Database file {filepath} is not initialized!")
        conn.close()
        return True
    
    Log(f"Saving IP info: {ipinfo}")

    # Check if record already exists and temporarily store the created_at timestamp
    cursor.execute("SELECT created_at FROM geoip WHERE ip_address = ?", (ipinfo.get("ip_address"),))
    row = cursor.fetchone()
    if row:
        created_at = row[0]
        ipinfo["created_at"] = created_at

    # Prepare the insert or replace statement
    columns = ', '.join(ipinfo.keys())
    placeholders = ', '.join('?' * len(ipinfo))
    # Insert or update the record
    sql = f'''INSERT OR REPLACE INTO geoip ({columns}, updated_at) 
              VALUES ({placeholders}, CURRENT_TIMESTAMP)'''
    values = tuple(ipinfo.values())
    cursor.execute(sql, values)
    conn.commit()

    conn.close()

    return False

# Function to check if IP information is already in the database and see if still valid
def CheckIPInfo(ip, ttl=7):
    # Check if IP is "me", if so return None
    if ip == "me":
        Log(f"IP is 'me', skipping database check")
        return None

    # Placeholder function to check IP information in the database
    Log(f"Checking IP info for: {ip}")

    # Open the database connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Query the database for the IP address
    cursor.execute("SELECT * FROM geoip WHERE ip_address = ?", (ip,))
    row = cursor.fetchone()

    # Close the database connection
    conn.close()

    # Check if the row is found
    if row:
        # Convert the row to a dictionary
        columns = [column[0] for column in cursor.description]
        ipinfo = dict(zip(columns, row))

        # Check if the record is still valid based on TTL and the record updated_at timetamp
        updated_at = datetime.strptime(ipinfo["updated_at"], "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - updated_at).days <= ttl:
            Log(f"IP info is still valid (TTL: {ttl} days): {ipinfo}")
            return ipinfo

    Log(f"No valid IP info found for: {ip}")
    return None

# Function to geolocate an IP address using MaxMind
def GeolocateIP(ip, maxmind_config=None):
    # Check if MaxMind config is provided
    if maxmind_config is None:
        Log("MaxMind configuration is missing!")
        return None
    
    # Check if config has account and key
    account = maxmind_config.get("account", "")
    key = maxmind_config.get("key", "")
    pretty = maxmind_config.get("pretty", False)
    edition = maxmind_config.get("edition", "")
    editions = maxmind_config.get("editions", {})

    if not account or not key or not edition or edition not in editions:
        Log("MaxMind configuration is incomplete or invalid!")
        return None 
    
    Log(f"Geolocating IP: {ip}")
    Log(f"Using MaxMind edition: {edition}")
    Log(f"MaxMind edition URL: {editions[edition]}")

    # Create Auth pair as Maxmind uses basic authentication with account and key
    auth = (account, key)

    # Create URI for the GET request
    uri = f"{editions[edition]}{ip}"

    if pretty:
        uri += "?pretty"

    Log(f"MaxMind URI: {uri}")

    # Make a GET request to MaxMind and save the JSON response
    raw_response = requests.get(uri, auth=auth)
    raw_json = raw_response.json()

    # Get city from raw JSON
    city = raw_json.get("city", {})
    # Get continent from raw JSON
    continent = raw_json.get("continent", {})
    # Get country from raw JSON
    country = raw_json.get("country", {})
    # Get location from raw JSON
    location = raw_json.get("location", {})
    # Get postal from raw JSON
    postal = raw_json.get("postal", {})
    # Get registered_country from raw JSON
    registered_country = raw_json.get("registered_country", {})
    # Get represented_country from raw JSON
    represented_country = raw_json.get("represented_country", {})
    # Get subdivisions from raw JSON
    subdivisions = raw_json.get("subdivisions", [])
    # Get traits from raw JSON
    traits = raw_json.get("traits", {})
    # Get maxmind from raw JSON
    maxmind = raw_json.get("maxmind", {})

    # Get City Name
    city_name = city.get("names", {}).get("en", "")
    # Get Continent Code and Name
    continent_code = continent.get("code", "")
    continent_name = continent.get("names", {}).get("en", "")
    # Get Country ISO Code and Name
    country_iso_code = country.get("iso_code", "")
    country_name = country.get("names", {}).get("en", "")
    # Get Location accuracy radius, latitude, longitude, time_zone
    accuracy_radius = location.get("accuracy_radius", 0)
    latitude = location.get("latitude", 0.0)
    longitude = location.get("longitude", 0.0)
    time_zone = location.get("time_zone", "")
    # Get Postal Code
    postal_code = postal.get("code", "")
    # Get ISO Code and Names from Subdivisions
    subdivisions_list = []
    for subdivision in subdivisions:
        iso_code = subdivision.get("iso_code", "")
        name = subdivision.get("names", {}).get("en", "")
        subdivisions_list.append({"iso_code": iso_code, "name": name})
    subdivisions_str = json.dumps(subdivisions_list)
    # Get most data from traits
    static_ip_score = traits.get("static_ip_score", 0)
    user_type = traits.get("user_type", "")
    autonomous_system_number = traits.get("autonomous_system_number", 0)
    autonomous_system_organization = traits.get("autonomous_system_organization", "")
    connection_type = traits.get("connection_type", "")
    isp = traits.get("isp", "")
    organization = traits.get("organization", "")
    ip_address = traits.get("ip_address", "")
    network = traits.get("network", "")

    # Take all the data and create a single dictionary
    ipinfo = {
        "city_name": city_name,
        "continent_code": continent_code,
        "continent_name": continent_name,
        "country_iso_code": country_iso_code,
        "country_name": country_name,
        "accuracy_radius": accuracy_radius,
        "latitude": latitude,
        "longitude": longitude,
        "time_zone": time_zone,
        "postal_code": postal_code,
        "subdivisions": subdivisions_str,
        "static_ip_score": static_ip_score,
        "user_type": user_type,
        "asn": autonomous_system_number,
        "asn_org": autonomous_system_organization,
        "connection_type": connection_type,
        "isp": isp,
        "organization": organization,
        "ip_address": ip_address,
        "network": network
    }

    Log(f"MaxMind response: {ipinfo}")
    
    # Log the remaining queries available
    Log(f"MaxMind remaining queries: {maxmind.get('queries_remaining', 'N/A')}")

    return ipinfo

# Main function
def main():
    # Read the configuration
    general, maxmind = ReadConfig(CONFIG_PATH)

    if general is None or maxmind is None:
        Log("Failed to read configuration. Exiting.")
        return 1
    
    # Temporary print the maxmind config for debugging
    Log(f"General Config: {general}")
    Log(f"MaxMind Config: {maxmind}")

    # Check if the edition in the config exist in the editions list
    edition = maxmind.get("edition")
    editions = maxmind.get("editions", {})

    if edition not in editions:
        Log(f"Invalid MaxMind edition: {edition}")
        return 1
    
    Log(f"Using MaxMind edition: {edition}")
    Log(f"MaxMind edition URL: {editions[edition]}")

    # Initialize the database using the IP info data for the columns
    if InitDatabase(DB_PATH):
        Log(f"Database failed to initialize, exiting")
        return 1

    parser = argparse.ArgumentParser(description="Geolocate IP addresses using MaxMind database.")
    parser.add_argument("--ip", type=str, default="me", help="IP address to geolocate")
    # Check if user wants to force refresh the IP info from MaxMind
    parser.add_argument("--force", action="store_true", help="Force refresh the IP info from MaxMind")
    args = parser.parse_args()

    ip = args.ip
    force = args.force

    # Check if the IP is either Me, valid IPv4, or valid IPv6
    if ip != "me":
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            Log(f"Invalid IP address: {ip}")
            return 1
    
    # Check if the IP info is already in the database
    ipinfo = CheckIPInfo(ip, general.get("ttl", 7))
    updated = False

    # If force is set, ignore the database and geolocate the IP again
    if force:
        Log(f"Force flag is set, ignoring database and geolocating IP: {ip}")
        ipinfo = None
        updated = True

    # Check if ipinfo was returned none
    if ipinfo in [None, {}]:    
        # Geolocate the IP address using Maxmind
        Log(f"IP info not found in database or expired, geolocating IP: {ip}")
        ipinfo = GeolocateIP(ip, maxmind)
        updated = True

        if ipinfo is None:
            Log(f"Failed to geolocate IP address: {ip}")
            return 1

    # Save the IP info to the database
    if updated:
        Log(f"Saving new/updated IP info to database: {ipinfo}")
        if SaveIPInfo(DB_PATH, ipinfo):
            Log(f"Failed to save IP info to database")
            return 1
        
    return 0

# Entry point of the script
if __name__ == "__main__":
    # Global variables
    LOG_PATH = "geo.log"
    CONFIG_PATH = "config.json"
    DB_PATH = "geo.db"

    exitcode = main()

    sys.exit(exitcode)