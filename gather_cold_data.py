#!/usr/bin/env python3
"""
Cold Data Gatherer Tool
Gathers local business and point-of-interest data from OpenStreetMap (Overpass API)
for a given region, formats it, and exports it to XML and CSV.
"""

import os
import sys
import argparse
import requests
import json
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import csv
from urllib.parse import quote

# Configuration & Overpass server list for redundancy
OVERPASS_SERVERS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

USER_AGENT = "ColdDataGathererAzzar/1.0 (azzar.dev@gmail.com)"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/json'
}

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def geocode_region(region_name):
    """
    Geocodes region name to find OSM area ID or bounding box coordinates.
    Returns a dict with area_id, bbox (south, west, north, east) or None.
    """
    log(f"Geocoding region: '{region_name}' using Nominatim...")
    url = f"https://nominatim.openstreetmap.org/search?q={quote(region_name)}&format=json&limit=5"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        results = response.json()
        
        if not results:
            log("No geocoding results found.", "WARNING")
            return None
            
        # Prioritize relation boundaries, then ways, then nodes
        best_match = None
        for item in results:
            if item.get("osm_type") == "relation":
                best_match = item
                break
        if not best_match:
            for item in results:
                if item.get("osm_type") == "way":
                    best_match = item
                    break
        if not best_match:
            best_match = results[0]
            
        osm_id = int(best_match["osm_id"])
        osm_type = best_match["osm_type"]
        display_name = best_match.get("display_name", "")
        bbox = [float(x) for x in best_match.get("boundingbox", [])] # [south, north, west, east]
        
        log(f"Matched location: {display_name}")
        
        area_id = None
        if osm_type == "relation":
            area_id = osm_id + 3600000000
        elif osm_type == "way":
            area_id = osm_id + 2400000000
            
        return {
            "area_id": area_id,
            # Nominatim bbox is [south, north, west, east] -> Overpass bbox is (south, west, north, east)
            "bbox": (bbox[0], bbox[2], bbox[1], bbox[3]) if len(bbox) == 4 else None,
            "display_name": display_name
        }
    except Exception as e:
        log(f"Geocoding failed: {e}", "ERROR")
        return None

def build_overpass_query(area_info, category, custom_query=None):
    """
    Builds the Overpass QL query string based on category/tags and area info.
    """
    # Define tag filters based on category
    tag_filters = []
    if custom_query:
        if "=" in custom_query:
            key, val = custom_query.split("=", 1)
            tag_filters = [f'["{key}"="{val}"]']
        else:
            tag_filters = [f'["amenity"="{custom_query}"]', f'["shop"="{custom_query}"]']
    else:
        cat = category.lower().strip()
        if cat == "cafe":
            tag_filters = ['["amenity"="cafe"]', '["shop"="coffee"]']
        elif cat == "restaurant":
            tag_filters = ['["amenity"="restaurant"]', '["amenity"="fast_food"]']
        elif cat == "hotel":
            tag_filters = ['["tourism"="hotel"]', '["tourism"="guest_house"]', '["tourism"="hostel"]']
        elif cat == "gym":
            tag_filters = ['["leisure"="fitness_centre"]', '["leisure"="sports_centre"]']
        elif cat == "store":
            tag_filters = ['["shop"]']
        else:
            # Generic amenity query fallback
            tag_filters = [f'["amenity"="{cat}"]', f'["shop"="{cat}"]']

    # Query structure: Area search vs Bounding box search
    query_parts = []
    query_parts.append("[out:json];")
    
    if area_info.get("area_id"):
        area_id = area_info["area_id"]
        query_parts.append(f"area({area_id})->.searchArea;")
        query_parts.append("(")
        for tf in tag_filters:
            query_parts.append(f"  node{tf}(area.searchArea);")
            query_parts.append(f"  way{tf}(area.searchArea);")
        query_parts.append(");")
    elif area_info.get("bbox"):
        s, w, n, e = area_info["bbox"]
        bbox_str = f"{s},{w},{n},{e}"
        query_parts.append("(")
        for tf in tag_filters:
            query_parts.append(f"  node{tf}({bbox_str});")
            query_parts.append(f"  way{tf}({bbox_str});")
        query_parts.append(");")
    else:
        raise ValueError("Invalid area information for query building")
        
    query_parts.append("out center;")
    return "\n".join(query_parts)

def fetch_overpass_data(query):
    """
    Executes the Overpass QL query, rotating through available servers on failure.
    """
    for url in OVERPASS_SERVERS:
        log(f"Querying Overpass API server: {url}...")
        try:
            response = requests.post(url, data={'data': query}, headers=HEADERS, timeout=30)
            if response.status_code == 429:
                log("Server returned 429 (Rate Limit). Trying next mirror...", "WARNING")
                continue
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log(f"Error on {url}: {e}", "WARNING")
            
    raise RuntimeError("All Overpass API servers timed out or returned errors.")

def parse_elements(elements):
    """
    Parses OSM JSON elements into a clean list of dictionaries with standard business info.
    """
    parsed_records = []
    
    for el in elements:
        tags = el.get("tags", {})
        if not tags:
            continue
            
        # Get coordinates
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        
        # Build address
        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        subdistrict = tags.get("addr:subdistrict") or tags.get("addr:neighborhood") or tags.get("addr:village", "")
        city = tags.get("addr:city") or tags.get("addr:province", "")
        postcode = tags.get("addr:postcode", "")
        
        address_parts = []
        if street:
            address_parts.append(f"{street} {housenumber}".strip())
        if subdistrict:
            address_parts.append(subdistrict)
        if city:
            address_parts.append(city)
        if postcode:
            address_parts.append(postcode)
            
        full_address = ", ".join(address_parts) if address_parts else tags.get("addr:full", "")
        
        # Extract metadata
        name = tags.get("name", "Unnamed Business")
        category = tags.get("amenity") or tags.get("shop") or tags.get("tourism") or tags.get("leisure", "Business")
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:whatsapp", "")
        website = tags.get("website") or tags.get("contact:website") or tags.get("url", "")
        email = tags.get("email") or tags.get("contact:email", "")
        opening_hours = tags.get("opening_hours", "")
        cuisine = tags.get("cuisine", "")
        brand = tags.get("brand", "")
        
        # Social links
        instagram = tags.get("contact:instagram") or tags.get("instagram", "")
        facebook = tags.get("contact:facebook") or tags.get("facebook", "")
        
        parsed_records.append({
            "name": name,
            "category": category,
            "latitude": str(lat) if lat else "",
            "longitude": str(lon) if lon else "",
            "address": full_address,
            "phone": phone,
            "website": website,
            "email": email,
            "opening_hours": opening_hours,
            "cuisine": cuisine,
            "brand": brand,
            "instagram": instagram,
            "facebook": facebook,
            "osm_id": str(el.get("id", ""))
        })
        
    return parsed_records

def export_to_xml(records, filepath):
    """
    Exports business records to formatted XML file.
    """
    root = ET.Element("businesses")
    
    for r in records:
        business_el = ET.SubElement(root, "business")
        for k, v in r.items():
            child = ET.SubElement(business_el, k)
            child.text = v if v is not None else ""
            
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")
    
    with open(filepath, "wb") as f:
        f.write(pretty_xml)
        
    log(f"Exported XML successfully: {filepath}")

def export_to_csv(records, filepath):
    """
    Exports business records to standard CSV file (with Excel compatibility encoding).
    """
    if not records:
        return
        
    keys = records[0].keys()
    
    # Write using UTF-8-SIG to ensure Excel opens non-ASCII characters correctly
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)
        
    log(f"Exported CSV successfully: {filepath}")

def main():
    parser = argparse.ArgumentParser(description="Gathers local business cold data from OpenStreetMap.")
    parser.add_argument("-q", "--query", required=True, help="Category query (e.g. 'cafe', 'restaurant', 'hotel') or exact OSM tag (e.g. 'amenity=school')")
    parser.add_argument("-r", "--region", required=True, help="Region to query (e.g. 'Jakarta Selatan', 'Bandung')")
    parser.add_argument("-o", "--output", help="Output file prefix (default: region_query)")
    parser.add_argument("-l", "--limit", type=int, help="Limit output records count")
    
    args = parser.parse_args()
    
    # Geocode region
    area_info = geocode_region(args.region)
    if not area_info:
        log("Could not geocode the region. Exiting.", "ERROR")
        sys.exit(1)
        
    # Build query
    custom = args.query if "=" in args.query else None
    query = build_overpass_query(area_info, args.query, custom_query=custom)
    
    # Fetch data
    try:
        raw_data = fetch_overpass_data(query)
    except Exception as e:
        log(f"Failed to fetch data from Overpass: {e}", "ERROR")
        sys.exit(1)
        
    # Parse elements
    elements = raw_data.get("elements", [])
    log(f"Fetched {len(elements)} raw elements.")
    
    records = parse_elements(elements)
    log(f"Successfully parsed {len(records)} valid records.")
    
    if args.limit and args.limit < len(records):
        records = records[:args.limit]
        log(f"Limited output to {args.limit} records.")
        
    # Output file paths
    output_prefix = args.output
    if not output_prefix:
        sanitized_region = args.region.lower().replace(" ", "_")
        sanitized_query = args.query.lower().replace("=", "_").replace(" ", "_")
        output_prefix = f"{sanitized_region}_{sanitized_query}"
        
    xml_path = f"{output_prefix}.xml"
    csv_path = f"{output_prefix}.csv"
    
    # Export
    export_to_xml(records, xml_path)
    export_to_csv(records, csv_path)
    
    log(f"Completed! Saved {len(records)} items.", "SUCCESS")

if __name__ == "__main__":
    main()
