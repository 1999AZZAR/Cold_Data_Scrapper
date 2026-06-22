#!/usr/bin/env python3
"""
Copyright (c) 2026 Azzar Budiyanto / LilyOpenCMS.
All rights reserved.

Contact: azzar.mr.zs@gmail.com for inquiries.
"""
"""
Lead Deduplicator & Merger
Matches leads by: (1) coordinates + name, (2) shared phone/email identity.
Merges all available data into the most complete record.
"""

import os
import sys
import sqlite3
import math
import re
from difflib import SequenceMatcher

DB_PATH = "data/cold_data.db"

# Matching thresholds
DISTANCE_HARD_METERS = 200.0     # Never match beyond this
DISTANCE_CLOSE_METERS = 50.0     # Very tight — name tolerance relaxed
NAME_SIMILARITY_THRESHOLD = 0.85
NAME_SIMILARITY_RELAXED = 0.60   # Used when distance is very close
NAME_SIMILARITY_IDENTITY = 0.50  # Minimum for phone/email matches (catches chain variants)
NAME_SIMILARITY_CHAIN = 0.95    # Very strict for chain businesses (centralized phones = false merges)

# Chain business patterns — phone alone is not enough to merge these
CHAIN_PATTERNS = re.compile(
    r'reddoorz|oYO|airy|zen\s+rooms|fave|amaris|swiss-bel|novotel|ibis|mercure|holiday\s+inn'
    r'|ritz|mandarin|sheraton|hyatt|marriott|hilton|aston|swissbell|arris|city\s+inn'
    r'|red\s*living|urbanview|collection\s+o|capital\s+o|super\s+oYO|townhouse\s+oYO',
    re.IGNORECASE
)

# Generic location descriptors to strip when comparing chain variants
GENERIC_DESCRIPTORS = re.compile(
    r'\bnear\b|\bat\b|\bplus\b|\bpremium\b|\bsyariah\b|\beco\b|\bmitra\b|\bredpartner\b'
    r'|\bdekat\b|\bsekitar\b|\bversion\b|\bby\b|\b-\b',
    re.IGNORECASE
)

STRIP_PATTERNS = re.compile(
    r'\b(pt|cv|tbk|tb|md|ud|yayasan|rumah\s+sakit|rs|rsu|klinik|apotek|masjid|mushola|gereja|vihara|pura)\b'
    r'|\bjl\.?\b|jalan\b|\bno\.?\b|\bunit\b|\blok\b|\bruko\b|\bmall\b|\bplaza\b|\btower\b',
    re.IGNORECASE
)

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def haversine_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def normalize_name(name):
    n = name.lower().strip()
    n = STRIP_PATTERNS.sub('', n)
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def name_similarity(name1, name2):
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return 0.0

    # For chain businesses, strip brand + generic descriptors before comparing
    if is_chain(name1) or is_chain(name2):
        n1 = CHAIN_PATTERNS.sub('', n1).strip()
        n2 = CHAIN_PATTERNS.sub('', n2).strip()
        n1 = GENERIC_DESCRIPTORS.sub('', n1).strip()
        n2 = GENERIC_DESCRIPTORS.sub('', n2).strip()
        n1 = re.sub(r'\s+', ' ', n1).strip()
        n2 = re.sub(r'\s+', ' ', n2).strip()
        # If nothing meaningful left, compare originals
        if len(n1) < 3 or len(n2) < 3:
            n1 = normalize_name(name1)
            n2 = normalize_name(name2)

    return SequenceMatcher(None, n1, n2).ratio()

def normalize_phone(phone):
    if not phone:
        return ""
    p = re.sub(r'[\s\-\(\)]', '', phone)
    p = p.lstrip('+')
    if p.startswith('62'):
        p = p[2:]
    if p.startswith('0'):
        p = p[1:]
    return p

def data_completeness(lead):
    fields = ["phone", "website", "email", "address", "opening_hours", "cuisine", "brand",
              "instagram", "facebook", "whatsapp", "price_range", "rating", "review_count"]
    score = 0
    for f in fields:
        val = lead.get(f)
        if val is not None and val != "":
            score += 1
    if lead.get("rating") is not None:
        score += 1
    return score

def pick_primary(a, b):
    ca, cb = data_completeness(a), data_completeness(b)
    if ca > cb:
        return a, b
    if cb > ca:
        return b, a
    return (a, b) if a["id"] < b["id"] else (b, a)

def merge_leads(primary, secondary):
    """Aggressively merge: take whichever value is more complete."""
    updates = {}

    # Simple fields: take secondary's value if primary is empty
    simple_fields = ["phone", "website", "email", "opening_hours", "cuisine", "brand",
                     "instagram", "facebook", "whatsapp", "price_range", "maps_link",
                     "category"]
    for f in simple_fields:
        p_val = primary.get(f)
        s_val = secondary.get(f)
        if s_val and not p_val:
            updates[f] = s_val

    # Address: prefer longer (more complete) address
    p_addr = primary.get("address") or ""
    s_addr = secondary.get("address") or ""
    if s_addr and len(s_addr) > len(p_addr):
        updates["address"] = s_addr

    # Name: prefer more specific (longer normalized name)
    p_name = normalize_name(primary.get("name", ""))
    s_name = normalize_name(secondary.get("name", ""))
    if s_name and len(s_name) > len(p_name) + 2:
        updates["name"] = secondary["name"]

    # Rating: keep higher, but weight by review count reliability
    p_rating = primary.get("rating")
    s_rating = secondary.get("rating")
    p_reviews = primary.get("review_count") or 0
    s_reviews = secondary.get("review_count") or 0
    if s_rating is not None:
        if p_rating is None:
            updates["rating"] = s_rating
        elif s_rating > p_rating:
            # Prefer higher rating only if review count is reasonable
            if s_reviews >= p_reviews * 0.3 or s_rating - p_rating > 0.5:
                updates["rating"] = s_rating
    if s_reviews is not None:
        if p_reviews is None or s_reviews > p_reviews:
            updates["review_count"] = s_reviews

    # Merge sources
    sources = set()
    for src in (primary.get("source", "") or "").split(","):
        s = src.strip()
        if s:
            sources.add(s)
    for src in (secondary.get("source", "") or "").split(","):
        s = src.strip()
        if s:
            sources.add(s)
    combined = ", ".join(sorted(sources))
    if combined and combined != primary.get("source"):
        updates["source"] = combined

    return updates

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def build_phone_index(leads):
    """Index leads by normalized phone for identity matching."""
    idx = {}
    for lead in leads:
        phone = normalize_phone(lead.get("phone", ""))
        if phone and len(phone) >= 8:
            idx.setdefault(phone, []).append(lead)
    return idx

def build_email_index(leads):
    """Index leads by lowercase email for identity matching."""
    idx = {}
    for lead in leads:
        email = (lead.get("email") or "").lower().strip()
        if email and "@" in email:
            idx.setdefault(email, []).append(lead)
    return idx

def is_chain(name):
    return bool(CHAIN_PATTERNS.search(name or ""))

def find_matches_by_identity(leads):
    """Find pairs that share phone or email — strong identity signal.
    For chain businesses, requires high name similarity to avoid false merges."""
    pairs = []
    seen = set()

    phone_idx = build_phone_index(leads)
    for phone, group in phone_idx.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pair_key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                if pair_key in seen:
                    continue
                # Chain businesses need strict name similarity
                if is_chain(a["name"]) or is_chain(b["name"]):
                    sim = name_similarity(a["name"], b["name"])
                    if sim < NAME_SIMILARITY_CHAIN:
                        continue
                seen.add(pair_key)
                pairs.append((a, b, "phone"))

    email_idx = build_email_index(leads)
    for email, group in email_idx.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pair_key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                if pair_key in seen:
                    continue
                if is_chain(a["name"]) or is_chain(b["name"]):
                    sim = name_similarity(a["name"], b["name"])
                    if sim < NAME_SIMILARITY_CHAIN:
                        continue
                seen.add(pair_key)
                pairs.append((a, b, "email"))

    return pairs

def find_matches_by_proximity(leads):
    """Find pairs close in location with similar names."""
    pairs = []
    checked = set()

    for i in range(len(leads)):
        a = leads[i]
        id_a = a["id"]
        if id_a in checked:
            continue

        for j in range(i + 1, len(leads)):
            b = leads[j]
            id_b = b["id"]
            if id_b in checked:
                continue

            dist = haversine_distance(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
            if dist > DISTANCE_HARD_METERS:
                continue

            sim = name_similarity(a["name"], b["name"])

            # Tight distance = relaxed name threshold
            if dist <= DISTANCE_CLOSE_METERS:
                threshold = NAME_SIMILARITY_RELAXED
            else:
                threshold = NAME_SIMILARITY_THRESHOLD

            if sim >= threshold:
                pairs.append((a, b, f"proximity({dist:.0f}m,sim={sim:.2f})"))

    return pairs

def deduplicate():
    if not os.path.exists(DB_PATH):
        log(f"Database {DB_PATH} not found.", "ERROR")
        return

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, run_id, source, source_id, name, category, latitude, longitude,
           address, phone, website, email, opening_hours, cuisine, brand,
           instagram, facebook, whatsapp, price_range, rating, review_count, maps_link
    FROM leads
    WHERE duplicate_of IS NULL
    """)
    leads = [dict(row) for row in cursor.fetchall()]
    log(f"Loaded {len(leads)} active leads.")

    # Phase 1: Identity matches (phone/email) — strongest signal
    identity_pairs = find_matches_by_identity(leads)
    log(f"Phase 1: {len(identity_pairs)} identity matches (phone/email).")

    # Phase 2: Proximity + name matches
    proximity_pairs = find_matches_by_proximity(leads)
    log(f"Phase 2: {len(proximity_pairs)} proximity+name matches.")

    # Combine, dedupe, prioritize identity matches
    all_pairs = {}
    for a, b, reason in identity_pairs:
        pair_key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
        all_pairs[pair_key] = (a, b, reason)
    for a, b, reason in proximity_pairs:
        pair_key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
        if pair_key not in all_pairs:
            all_pairs[pair_key] = (a, b, reason)

    log(f"Total unique pairs to process: {len(all_pairs)}.")

    duplicates_found = 0
    merged_fields_count = 0
    merge_log = []
    checked = set()

    for (id_a, id_b), (a, b, reason) in all_pairs.items():
        if id_a in checked or id_b in checked:
            continue

        primary, secondary = pick_primary(a, b)
        prim_id, sec_id = primary["id"], secondary["id"]

        log(f"Match [{reason}]: '{a['name']}' [{a['source']}] ↔ '{b['name']}' [{b['source']}] → primary=ID:{prim_id}")

        merged_data = merge_leads(primary, secondary)
        if merged_data:
            set_clause = ", ".join(f"{k} = ?" for k in merged_data)
            cursor.execute(
                f"UPDATE leads SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                list(merged_data.values()) + [prim_id]
            )
            merged_fields_count += len(merged_data)
            merge_log.append({
                "primary_id": prim_id, "primary_name": primary["name"],
                "secondary_id": sec_id, "secondary_name": secondary["name"],
                "reason": reason, "merged_fields": list(merged_data.keys())
            })
            log(f"  → Merged into ID:{prim_id}: {list(merged_data.keys())}")

        cursor.execute(
            "UPDATE leads SET duplicate_of = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (prim_id, sec_id)
        )
        duplicates_found += 1
        checked.add(id_a)
        checked.add(id_b)

    # Recalculate opportunity scores
    try:
        cursor.execute("""
        UPDATE leads
        SET opportunity_score = CASE WHEN duplicate_of IS NOT NULL THEN 0 ELSE (
          (CASE WHEN (website IS NULL OR website = '') THEN 30 ELSE 0 END) +
          (CASE WHEN (instagram IS NULL OR instagram = '') THEN 20 ELSE 0 END) +
          (CASE WHEN (facebook IS NULL OR facebook = '') THEN 10 ELSE 0 END) +
          (CASE WHEN (phone IS NULL OR phone = '') THEN 15 ELSE 0 END) +
          (CASE WHEN (email IS NULL OR email = '') THEN 15 ELSE 0 END) +
          (CASE WHEN (address IS NULL OR address = '') THEN 10 ELSE 0 END)
        ) END
        """)
        conn.commit()
    except sqlite3.Error as e:
        log(f"Score recalc failed: {e}", "WARNING")

    conn.close()

    log(f"Deduplication complete. {duplicates_found} duplicates, {merged_fields_count} fields merged.", "SUCCESS")
    if merge_log:
        log("Merge details:")
        for m in merge_log:
            log(f"  [{m['reason']}] ID:{m['primary_id']} '{m['primary_name']}' ← ID:{m['secondary_id']} '{m['secondary_name']}' → {m['merged_fields']}")

if __name__ == "__main__":
    deduplicate()
