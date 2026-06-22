#!/usr/bin/env python3
"""
Copyright (c) 2026 Azzar Budiyanto / LilyOpenCMS.
All rights reserved.

Contact: azzar.mr.zs@gmail.com for inquiries.
"""
"""
Export Converter
Reads clean leads from the database and exports them to XML, CSV, & JSON formats.
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

def fetch_clean_leads(run_id=None, query_filter=None, region_filter=None, search=None, show_duplicates=False,
                      has_email=False, has_phone=False, has_website=False, min_score=None):
    """
    Fetches clean (or all) leads from SQLite database matching filters.
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
           l.source, l.source_id, l.opportunity_score, l.price_range, l.maps_link
    FROM leads l
    LEFT JOIN runs r ON l.run_id = r.id
    WHERE 1=1
    """
    params = []
    
    if not show_duplicates:
        query += " AND l.duplicate_of IS NULL"
        
    if run_id:
        query += " AND l.run_id = ?"
        params.append(run_id)
    if query_filter:
        query += " AND r.query LIKE ?"
        params.append(f"%{query_filter}%")
    if region_filter:
        query += " AND r.region LIKE ?"
        params.append(f"%{region_filter}%")
    if search:
        query += " AND (l.name LIKE ? OR l.address LIKE ? OR l.category LIKE ?)"
        like_val = f"%{search}%"
        params.extend([like_val, like_val, like_val])
        
    if has_email:
        query += " AND l.email IS NOT NULL AND l.email != ''"
    if has_phone:
        query += " AND l.phone IS NOT NULL AND l.phone != ''"
    if has_website:
        query += " AND l.website IS NOT NULL AND l.website != ''"
    if min_score is not None:
        query += " AND l.opportunity_score >= ?"
        params.append(min_score)
        
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

def export_json(records, filepath):
    import json
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    log(f"Exported JSON successfully: {filepath}")

def main():
    parser = argparse.ArgumentParser(description="Exports clean database leads to XML, CSV & JSON.")
    parser.add_argument("--run-id", type=int, help="Filter by specific scraper run ID")
    parser.add_argument("-q", "--query", help="Filter by run query (e.g. 'cafe')")
    parser.add_argument("-r", "--region", help="Filter by run region (e.g. 'Jakarta Selatan')")
    parser.add_argument("-s", "--search", help="Filter by general text search query")
    parser.add_argument("--show-duplicates", action="store_true", help="Include duplicate records in export")
    parser.add_argument("--has-email", action="store_true", help="Only export leads with email address")
    parser.add_argument("--has-phone", action="store_true", help="Only export leads with phone number")
    parser.add_argument("--has-website", action="store_true", help="Only export leads with website")
    parser.add_argument("--min-score", type=int, help="Only export leads with opportunity score >= min_score")
    parser.add_argument("--columns", help="Comma-separated list of columns to include in export")
    parser.add_argument("-f", "--format", choices=["csv", "xml", "json"], default="csv", help="Export format")
    parser.add_argument("-o", "--output", required=True, help="Output file prefix")
    
    args = parser.parse_args()
    
    records = fetch_clean_leads(
        run_id=args.run_id, 
        query_filter=args.query, 
        region_filter=args.region,
        search=args.search,
        show_duplicates=args.show_duplicates,
        has_email=args.has_email,
        has_phone=args.has_phone,
        has_website=args.has_website,
        min_score=args.min_score
    )
    log(f"Fetched {len(records)} clean leads for exporting.")
    
    if not records:
        log("No matching records found. Exiting.", "WARNING")
        sys.exit(0)
        
    # Filter columns if specified
    if args.columns:
        cols = [c.strip() for c in args.columns.split(",") if c.strip()]
        filtered_records = []
        for r in records:
            filtered_r = {k: r[k] for k in cols if k in r}
            filtered_records.append(filtered_r)
        records = filtered_records
        
    output_prefix = args.output
    os.makedirs("exports", exist_ok=True)
    if not output_prefix.startswith("exports/"):
        output_prefix = os.path.join("exports", os.path.basename(output_prefix))
        
    if args.format == "csv":
        export_csv(records, f"{output_prefix}.csv")
    elif args.format == "xml":
        export_xml(records, f"{output_prefix}.xml")
    elif args.format == "json":
        export_json(records, f"{output_prefix}.json")
        
    log("Export completed successfully.", "SUCCESS")

if __name__ == "__main__":
    main()
