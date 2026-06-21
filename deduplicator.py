#!/usr/bin/env python3
"""
Lead Deduplicator
Finds duplicate business leads in the DB using coordinate distance (Haversine)
and name similarity (difflib). Merges contact info and marks duplicates.
"""

import os
import sys
import sqlite3
import math
from difflib import SequenceMatcher

DB_PATH = "cold_data.db"
DISTANCE_THRESHOLD_METERS = 100.0  # Proximity threshold
NAME_SIMILARITY_THRESHOLD = 0.7   # String similarity threshold (0.0 - 1.0)

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth (meters).
    """
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')
        
    R = 6371000.0 # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return R * c

def name_similarity(name1, name2):
    """
    Returns string similarity ratio between name1 and name2.
    """
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    return SequenceMatcher(None, n1, n2).ratio()

def merge_leads(primary, secondary):
    """
    Combines contacts/social fields from secondary lead into primary if primary is missing them.
    Returns a dict of fields to update in primary.
    """
    updates = {}
    fields = ["phone", "website", "email", "opening_hours", "cuisine", "brand", "instagram", "facebook", "whatsapp"]
    
    for f in fields:
        p_val = primary.get(f)
        s_val = secondary.get(f)
        if s_val and not p_val:
            updates[f] = s_val
            
    return updates

def deduplicate():
    if not os.path.exists(DB_PATH):
        log(f"Database {DB_PATH} not found.", "ERROR")
        return
        
    conn = sqlite3.connect(DB_PATH)
    # Configure row factory to return dict-like rows
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query all active (non-duplicate) leads
    cursor.execute("""
    SELECT id, run_id, source, source_id, name, category, latitude, longitude,
           address, phone, website, email, opening_hours, cuisine, brand,
           instagram, facebook, whatsapp
    FROM leads
    WHERE duplicate_of IS NULL
    """)
    leads = [dict(row) for row in cursor.fetchall()]
    log(f"Loaded {len(leads)} active leads for deduplication scanning.")
    
    duplicates_found = 0
    merged_fields_count = 0
    
    # Simple O(N^2) comparison - fine for regional lists (thousands of leads)
    # For massive lists, grid clustering or index grouping by geohash would be used.
    checked = set()
    
    for i in range(len(leads)):
        lead_a = leads[i]
        id_a = lead_a["id"]
        if id_a in checked:
            continue
            
        for j in range(i + 1, len(leads)):
            lead_b = leads[j]
            id_b = lead_b["id"]
            if id_b in checked:
                continue
                
            # 1. Geolocation Proximity Check
            dist = haversine_distance(
                lead_a["latitude"], lead_a["longitude"],
                lead_b["latitude"], lead_b["longitude"]
            )
            
            if dist <= DISTANCE_THRESHOLD_METERS:
                # 2. Name Similarity Check
                sim = name_similarity(lead_a["name"], lead_b["name"])
                if sim >= NAME_SIMILARITY_THRESHOLD:
                    log(f"Match found: '{lead_a['name']}' ({lead_a['source']}) and '{lead_b['name']}' ({lead_b['source']}) - Distance: {dist:.1f}m, Similarity: {sim:.2f}")
                    
                    # Determine primary (older, or OSM source which has more meta tags)
                    if lead_a["source"] == "osm" and lead_b["source"] != "osm":
                        primary, secondary = lead_a, lead_b
                    else:
                        primary, secondary = lead_b, lead_a
                        
                    prim_id, sec_id = primary["id"], secondary["id"]
                    
                    # Merge secondary fields into primary
                    merged_data = merge_leads(primary, secondary)
                    if merged_data:
                        update_set = ", ".join([f"{k} = ?" for k in merged_data.keys()])
                        cursor.execute(
                            f"UPDATE leads SET {update_set}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            list(merged_data.values()) + [prim_id]
                        )
                        merged_fields_count += len(merged_data)
                        log(f"  Merged fields {list(merged_data.keys())} into primary lead (ID: {prim_id})")
                        
                    # Mark secondary as duplicate of primary
                    cursor.execute(
                        "UPDATE leads SET duplicate_of = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (prim_id, sec_id)
                    )
                    
                    duplicates_found += 1
                    checked.add(sec_id)
                    
        checked.add(id_a)
        
    conn.commit()
    conn.close()
    
    log(f"Deduplication completed. Found {duplicates_found} duplicates. Merged {merged_fields_count} fields.", "SUCCESS")

if __name__ == "__main__":
    deduplicate()
