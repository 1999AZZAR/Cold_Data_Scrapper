#!/usr/bin/env python3
"""
Export Converter
Reads clean leads from the database and exports them to XML & CSV formats.
"""

import os
import sys
import argparse
import sqlite3
import csv
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

DB_PATH = "data/cold_data.db"

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def fetch_clean_leads(run_id=None, query_filter=None, region_filter=None):
    """
    Fetches clean (non-duplicate) leads from SQLite database.
    """
    if not os.path.exists(DB_PATH):
        log(f"Database {DB_PATH} not found.", "ERROR")
        return []
        
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
    SELECT l.id, l.name, l.category, l.latitude, l.longitude, l.address,
           l.phone, l.website, l.email, l.opening_hours, l.cuisine, l.brand,
           l.instagram, l.facebook, l.whatsapp, l.email_verified, l.phone_verified,
           l.source, l.source_id
    FROM leads l
    LEFT JOIN runs r ON l.run_id = r.id
    WHERE l.duplicate_of IS NULL
    """
    params = []
    
    if run_id:
        query += " AND l.run_id = ?"
        params.append(run_id)
    if query_filter:
        query += " AND r.query LIKE ?"
        params.append(f"%{query_filter}%")
    if region_filter:
        query += " AND r.region LIKE ?"
        params.append(f"%{region_filter}%")
        
    query += " ORDER BY l.name ASC"
    
    cursor.execute(query, params)
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return leads

def export_xml(records, filepath):
    root = ET.Element("businesses")
    for r in records:
        business_el = ET.SubElement(root, "business")
        for k, v in r.items():
            child = ET.SubElement(business_el, k)
            child.text = str(v) if v is not None else ""
            
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")
    
    with open(filepath, "wb") as f:
        f.write(pretty_xml)
    log(f"Exported XML successfully: {filepath}")

def export_csv(records, filepath):
    if not records:
        log("No records to export.", "WARNING")
        return
        
    keys = records[0].keys()
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)
    log(f"Exported CSV successfully: {filepath}")

def main():
    parser = argparse.ArgumentParser(description="Exports clean database leads to XML & CSV.")
    parser.add_argument("--run-id", type=int, help="Filter by specific scraper run ID")
    parser.add_argument("-q", "--query", help="Filter by run query (e.g. 'cafe')")
    parser.add_argument("-r", "--region", help="Filter by run region (e.g. 'Jakarta Selatan')")
    parser.add_argument("-o", "--output", required=True, help="Output file prefix")
    
    args = parser.parse_args()
    
    records = fetch_clean_leads(run_id=args.run_id, query_filter=args.query, region_filter=args.region)
    log(f"Fetched {len(records)} clean leads for exporting.")
    
    if not records:
        log("No matching records found. Exiting.", "WARNING")
        sys.exit(0)
        
    export_xml(records, f"{args.output}.xml")
    export_csv(records, f"{args.output}.csv")
    log("Export completed successfully.", "SUCCESS")

if __name__ == "__main__":
    main()
