#!/bin/python3

import json
import csv
import sys
import argparse
import sqlite3
import os
from datetime import datetime
from GeolocateIP import get_ip_info
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# A function to write a log file
def Log(message, tee=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"

    # Print Log to Console
    if tee:
        print(line)

    # Try to write log to file
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception as ex:
        print(f"[{timestamp}] Failed to write log to {LOG_PATH}: {ex}")

# Function to read CSV file and return data as a list of dictionaries
def ReadCSV(file_path="data.csv"):
    # Check if the file exists
    try:
        data = []
        with open(file_path, mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                data.append(row)
        return data
    except FileNotFoundError:
        Log(f"Error: The file {file_path} does not exist.")

    return []

# Function to create a sqlite database from CSV data
def InitDB(columns, db_file="data.db"):
    # Check if the file exists and return True if it does
    if os.path.isfile(db_file):
        return True
    
    # Create a new database
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Create table with dynamic columns
        columns_with_types = ", ".join([f"{col} {col_type}" for col, col_type in columns.items()])
        create_table_query = f"CREATE TABLE data ({columns_with_types});"
        cursor.execute(create_table_query)

        # Create table that stores IP address lookups
        # Primary Key - IP Address
        # Columns - City, State, Country, Continent, Latitude, Longitude
        create_ip_table_query = """CREATE TABLE ip_info (
            ip_address TEXT PRIMARY KEY,
            date TIMESTAMP,
            user TEXT,
            city TEXT,
            state TEXT,
            state_code TEXT,
            country TEXT,
            country_code TEXT,
            continent TEXT,
            continent_code TEXT,
            postal_code TEXT,
            latitude REAL,
            longitude REAL
        );"""
        cursor.execute(create_ip_table_query)

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        Log(f"Error creating database: {e}")
        return True
    
    return False

# Function to save data to the database
def SaveCsvToDB(data, db_file="data.db"):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Prepare insert query
        placeholders = ", ".join(["?" for _ in data[0]])
        insert_query = f"INSERT INTO data VALUES ({placeholders});"

        # Insert each row
        for row in data:
            cursor.execute(insert_query, tuple(row.values()))

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        Log(f"Error saving to database: {e}")
        return True
    
    return False

# Function to save IP info to the database
def SaveIPInfoToDB(ip_info, db_file="data.db"):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Prepare insert query with ON CONFLICT clause to ignore duplicates
        insert_query = """INSERT INTO ip_info (ip_address, date, user, city, state, state_code, country, country_code, continent, continent_code, postal_code, latitude, longitude)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT(ip_address) DO NOTHING;"""

        # Insert each IP info
        for ip, info in ip_info.items():
            cursor.execute(insert_query, (
                ip,
                info.get("date"),
                info.get("user"),
                info.get("city"),
                info.get("state"),
                info.get("state_code"),
                info.get("country"),
                info.get("country_code"),
                info.get("continent"),
                info.get("continent_code"),
                info.get("postal_code"),
                info.get("latitude"),
                info.get("longitude")
            ))

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        Log(f"Error saving IP info to database: {e}")
        return True
    
    return False

# Function to get occurrence count where same city, state, country, continent appear
def GetCityCount(db_file="data.db"):
    city_count = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get city, state, country, continent counts
        query = """SELECT city, state_code, country_code, continent_code, COUNT(*) as count
                   FROM ip_info
                   GROUP BY city, state_code, country_code, continent_code;"""
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            city, state, country, continent, count = row
            key = f"{city}, {state}, {country}, {continent}"
            city_count[key] = count

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving city counts: {e}")
        return {}

    return city_count

# Function to get occurence count where same state, country, continent appear
def GetStateCount(db_file="data.db"):
    state_count = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get state, country, continent counts
        query = """SELECT state, country_code, continent_code, COUNT(*) as count
                   FROM ip_info
                   GROUP BY state, country_code, continent_code;"""
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            state, country, continent, count = row
            key = f"{state}, {country}, {continent}"
            state_count[key] = count

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving state counts: {e}")
        return {}

    return state_count

# Function to get occurence count where same state filtered by country or country_code
def GetStateByCountryCount(country_filter, db_file="data.db"):
    state_count = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get state counts filtered by country or country_code
        query = """SELECT state, COUNT(*) as count
                   FROM ip_info
                   WHERE country = ? OR country_code = ?
                   GROUP BY state;"""
        cursor.execute(query, (country_filter, country_filter))
        rows = cursor.fetchall()

        for row in rows:
            state, count = row
            key = f"{state}"
            state_count[key] = count

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving state by country counts: {e}")
        return {}

    return state_count

# Function to get occurrence count where same country, continent appear
def GetCountryCount(db_file="data.db"):
    country_count = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get country, continent counts
        query = """SELECT country, continent_code, COUNT(*) as count
                   FROM ip_info
                   GROUP BY country, continent_code;"""
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            country, continent, count = row
            key = f"{country}, {continent}"
            country_count[key] = count

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving country counts: {e}")
        return {}

    return country_count

# Function to get occurrence count where same continent appears
def GetContinentCount(db_file="data.db"):
    continent_count = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get continent counts
        query = """SELECT continent, COUNT(*) as count
                   FROM ip_info
                   GROUP BY continent;"""
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            continent, count = row
            key = f"{continent}"
            continent_count[key] = count

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving continent counts: {e}")
        return {}

    return continent_count

# Function to get Latitude and Longitude for mapping
def GetLatLong(db_file="data.db"):
    lat_long = []
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get latitude and longitude
        query = """SELECT latitude, longitude
                   FROM ip_info
                   WHERE latitude IS NOT NULL AND longitude IS NOT NULL;"""
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            lat, lon = row
            if lat is not None and lon is not None:
                lat_long.append((lat, lon))

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving latitude and longitude: {e}")
        return []

    return lat_long

# Function to get Latitude and Longitude for mapping, filtered by country or country_code
def GetLatLongByCountry(country_filter, db_file="data.db"):
    lat_long = []
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query to get latitude and longitude filtered by country or country_code
        query = """SELECT latitude, longitude
                   FROM ip_info
                   WHERE (country = ? OR country_code = ?)
                     AND latitude IS NOT NULL AND longitude IS NOT NULL;"""
        cursor.execute(query, (country_filter, country_filter))
        rows = cursor.fetchall()

        for row in rows:
            lat, lon = row
            if lat is not None and lon is not None:
                lat_long.append((lat, lon))

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving latitude and longitude by country: {e}")
        return []

    return lat_long

# Function that takes unique values from all columns and returns an occurrence count
def GetUniqueValues(db_file="data.db"):
    unique_values = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Get column names
        cursor.execute("PRAGMA table_info(data);")
        columns = [info[1] for info in cursor.fetchall()]

        # For each column, get unique values and their counts
        for col in columns:
            cursor.execute(f"SELECT {col}, COUNT(*) FROM data GROUP BY {col};")
            unique_values[col] = cursor.fetchall()

        conn.close()
    except sqlite3.Error as e:
        Log(f"Error retrieving unique values: {e}")
        return {}

    return unique_values

def main():
    # Parse Arguments
    parser = argparse.ArgumentParser(description="Convert CSV to JSON")
    parser.add_argument("--input", type=str, default="data.csv", help="Input CSV file path")
    args = parser.parse_args()
    Log(f"Input file: {args.input}")

    rows = ReadCSV(args.input)
    Log(f"Read {len(rows)} rows from {args.input}.")

    # Check if there is data to convert
    if rows in [None, []]:
        Log("No data found.")
        return 1
    
    # Try to associate keys/Values to a SQLite data type
    keys = {}
    if rows[0]:
        for key, value in rows[0].items():
            # Clean up the key for database
            Log(f"Processing key: '{key}' with sample value: '{value}'")
            key = key.lower()
            Log(f"Normalized key to lowercase: '{key}'")
            key = key.strip().replace(" ", "_").replace("-", "_").replace("/", "_").replace("\\", "_")
            Log(f"Sanitized key for database: '{key}'")

            # Check if value is int, float, bool, date or string

            # Int check
            try:
                int(value)
                keys[key] = "INTEGER"
                Log(f"Key '{key}' detected as INTEGER.")
                continue
            except ValueError:
                pass
            
            # Float check
            try:
                float(value)
                keys[key] = "REAL"
                Log(f"Key '{key}' detected as REAL.")
                continue
            except ValueError:
                pass
            
            # Date check (2025-10-15T08:13:39-06:00)
            try:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
                keys[key] = "DATE"
                Log(f"Key '{key}' detected as DATE.")
                continue
            except ValueError:
                pass    

            # Bool check
            if value.lower() in ["true", "false"]:
                keys[key] = "BOOLEAN"
                Log(f"Key '{key}' detected as BOOLEAN.")
                continue

            # If we reach here, it's a string
            keys[key] = "TEXT"
            Log(f"Key '{key}' detected as TEXT.")

    # Append data.db with timestamp, yyyymmdd_hhmmss
    db_file = f"data_{TIMESTAMP}.db"
    if InitDB(keys, db_file):
        Log(f"Database {db_file} failed to create.")
        return 1
    Log(f"Database {db_file} created successfully.")
    
    if SaveCsvToDB(rows, db_file):
        Log(f"Failed to save data to database {db_file}.")
        return 1
    Log(f"Data successfully saved to database {db_file}.")
    
    # Get Date, User, IP Address, and get IP info from GeolocateIP to save to DB
    for row in rows:
        # Normalize keys to lowercase and underscores
        row = {k.lower().strip().replace(" ", "_").replace("-", "_").replace("/", "_").replace("\\", "_"): v for k, v in row.items()}   
        if "ip_address" in row:
            ip = row["ip_address"]
            user = row.get("user", "unknown")
            date = row.get("date", datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"))
            if ip:
                info = get_ip_info(ip)
                if info:
                    info["date"] = date
                    info["user"] = user
                    info["city"] = info.get("city_name", "unknown")
                    # State is name from the first element in subdivisions array after converting from JSON string to Python list
                    subdivisions = info.get("subdivisions", [])
                    if isinstance(subdivisions, str):
                        try:
                            subdivisions = json.loads(subdivisions)
                        except json.JSONDecodeError:
                            subdivisions = []
                    subdivision = subdivisions[0] if subdivisions else None
                    info["state"] = subdivision.get("name", "unknown") if subdivision else "unknown"
                    info["state_code"] = subdivision.get("iso_code", "unknown") if subdivision else "unknown"
                    info["country"] = info.get("country_name", "unknown")
                    info["country_code"] = info.get("country_iso_code", "unknown")
                    info["continent"] = info.get("continent_name", "unknown")
                    info["continent_code"] = info.get("continent_code", "unknown")
                    info["postal_code"] = info.get("postal_code", "unknown")
                    info["latitude"] = info.get("latitude", 0.0)
                    info["longitude"] = info.get("longitude", 0.0)
                    SaveIPInfoToDB({ip: info}, db_file)
                    Log(f"Saved IP info for {ip}: {info}")
                else:
                    Log(f"Failed to get IP info for {ip}")
            else:
                Log("No IP address found in row.")
        else:
            Log("No 'ip_address' column found in data.")
    
    # Get city counts
    city_count = GetCityCount(db_file)
    state_count = GetStateCount(db_file)
    us_state_count = GetStateByCountryCount("US", db_file)
    country_count = GetCountryCount(db_file)
    continent_count = GetContinentCount(db_file)

    # Use Matplotlib to create a bar chart of the country counts
    try:
        x_axis = list(country_count.keys())
        y_axis = list(country_count.values())

        plt.figure(figsize=(16, 8))
        plt.bar(x_axis, y_axis, color='skyblue')
        plt.xlabel('Country')
        plt.ylabel('Occurrences')
        plt.title('Sign-In Activity by Country')
        plt.xticks(rotation=33)
        plt.tight_layout()
        
        chart_file = f"country_counts_{TIMESTAMP}.png"
        plt.savefig(chart_file)
        Log(f"Country count chart saved to {chart_file}")
    except ImportError:
        Log("Matplotlib not installed. Skipping chart generation.")
    except Exception as e:
        Log(f"Error generating chart: {e}")

    # Use Matplotlib to create a bar chart of the US State counts
    try:
        x_axis = list(us_state_count.keys())
        y_axis = list(us_state_count.values())

        plt.figure(figsize=(16, 8))
        plt.bar(x_axis, y_axis, color='skyblue')
        plt.xlabel('US State')
        plt.ylabel('Occurrences')
        plt.title('Sign-In Activity by US State')
        plt.xticks(rotation=33)
        plt.tight_layout()
        
        chart_file = f"us_state_counts_{TIMESTAMP}.png"
        plt.savefig(chart_file)
        Log(f"US State count chart saved to {chart_file}")
    except ImportError:
        Log("Matplotlib not installed. Skipping chart generation.")
    except Exception as e:
        Log(f"Error generating chart: {e}")

    plt.close('all')

    # Use Cartopy to create a world map of the IP addresses
    try:
        # Get all latitude and longitude from ip_info table
        lat_long = GetLatLong(db_file)
        latitudes = [lat for lat, lon in lat_long]
        longitudes = [lon for lat, lon in lat_long]

        if latitudes and longitudes:
            plt.figure(figsize=(20, 8))
            ax = plt.axes(projection=ccrs.PlateCarree())
            ax.add_feature(cfeature.LAND)
            ax.add_feature(cfeature.OCEAN)
            ax.add_feature(cfeature.COASTLINE)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            ax.add_feature(cfeature.LAKES, alpha=0.5)
            ax.add_feature(cfeature.RIVERS)
            ax.add_feature(cfeature.COUNTRIES, edgecolor='gray')
            plt.scatter(longitudes, latitudes, color='red', s=10, alpha=0.7, transform=ccrs.PlateCarree())
            plt.title('Geolocation of IP Addresses')
            
            map_file = f"ip_geolocation_map_{TIMESTAMP}.png"
            plt.savefig(map_file)
            Log(f"IP geolocation map saved to {map_file}")
        else:
            Log("No latitude and longitude data available for mapping.")
    except ImportError:
        Log("Cartopy not installed. Skipping map generation.")
    except Exception as e:
        Log(f"Error generating map: {e}")

    # Use Cartopy to create a US map with state borders of the IP addresses filtered by country or country_code
    try:
        # Get all latitude and longitude from ip_info table filtered by US
        lat_long = GetLatLongByCountry("US", db_file)
        latitudes = [lat for lat, lon in lat_long]
        longitudes = [lon for lat, lon in lat_long]

        if latitudes and longitudes:
            plt.figure(figsize=(20, 12))
            ax = plt.axes(projection=ccrs.LambertConformal())
            ax.set_extent([-125, -66.5, 24, 49.5], crs=ccrs.PlateCarree())
            ax.add_feature(cfeature.LAND)
            ax.add_feature(cfeature.OCEAN)
            ax.add_feature(cfeature.COASTLINE)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            ax.add_feature(cfeature.LAKES, alpha=0.5)
            ax.add_feature(cfeature.RIVERS)
            ax.add_feature(cfeature.STATES, edgecolor='gray')
            plt.scatter(longitudes, latitudes, color='blue', s=10, alpha=0.7, transform=ccrs.PlateCarree())
            plt.title('Geolocation of IP Addresses in the US')
            
            map_file = f"us_ip_geolocation_map_{TIMESTAMP}.png"
            plt.savefig(map_file)
            Log(f"US IP geolocation map saved to {map_file}")
        else:
            Log("No latitude and longitude data available for US mapping.")
    except ImportError:
        Log("Cartopy not installed. Skipping US map generation.")
    except Exception as e:
        Log(f"Error generating US map: {e}")

    return 0

if __name__ == "__main__":
    # Define global variables
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_PATH = f"Visualize-IP_{TIMESTAMP}.log"

    exitcode = main()

    sys.exit(exitcode)