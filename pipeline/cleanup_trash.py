#!/usr/bin/env python3
"""
Copyright (c) 2026 Azzar Budiyanto / LilyOpenCMS.
All rights reserved.

Contact: azzar.mr.zs@gmail.com for inquiries.
"""
"""
Trash Data Cleanup
Removes unnamed, generic, or junk businesses/places from the leads table.
Marks them as duplicates with a special prefix so they can be filtered out
but still audited if needed.
"""

import os
import sys
import sqlite3
import re

DB_PATH = "data/cold_data.db"

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")


# Exact matches (case-insensitive) — businesses with no real name
EXACT_TRASH = {
    "untitled",
    "unnamed",
    "unnamed business",
    "unnamed road",
    "unnamed place",
    "no name",
    "none",
    "n/a",
    "tbd",
    "unknown",
    "temp",
    "temporary",
    "test",
    "placeholder",
    "lorem ipsum",
    "new business",
    "new place",
    "new location",
    "coming soon",
    "opening soon",
    "closed",
    "permanently closed",
}

# Prefix/suffix patterns — junk names like "00:00", "+62 812..."
JUNK_PATTERNS = [
    re.compile(r"^\d{1,4}(:\d{2})?\s*(am|pm)?$", re.I),          # Time-like: "08:00", "12:30 PM"
    re.compile(r"^\+?\d[\d\s\-()]{6,}$"),                          # Phone-only names: "+62 812 3456 7890"
    re.compile(r"^[-+]?\d+\.\d+,\s*[-+]?\d+\.\d+$"),              # Coordinates: "-6.2123, 106.8456"
    re.compile(r"^[\w\s]{0,2}$"),                                   # Too short: "A", "Bb", "Ok"
    re.compile(r"^(loc|location|lokasi|tempat|point)\s*\d*$", re.I),  # Generic location labels
    re.compile(r"^(bisnis|usaha|toko|rumah)\s*\d*$", re.I),        # Generic business labels
]

# Substring presence — if name contains these and is short, likely junk
JUNK_SUBSTRINGS = ["rumah makan", "warung", "toko", "kedai", "tempat"]


def is_trash_name(name):
    """Check if a business name is junk/unnamed/generic."""
    if not name or not name.strip():
        return True

    clean = name.strip()
    lower = clean.lower()

    # Exact match
    if lower in EXACT_TRASH:
        return True

    # Pattern match
    for pattern in JUNK_PATTERNS:
        if pattern.match(clean):
            return True

    # Generic label + number (e.g., "Warung 123", "Toko 45")
    if re.match(r"^(warung|toko|rumah|kedai|tempat|usaha|bisnis)\s+\d+$", lower):
        return True

    return False


def cleanup():
    """Find and mark all trash leads as duplicates."""
    if not os.path.exists(DB_PATH):
        log(f"Database not found at {DB_PATH}", "ERROR")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Only process active leads (not already marked as duplicates)
    cur.execute("SELECT id, name FROM leads WHERE duplicate_of IS NULL")
    leads = cur.fetchall()

    trash_ids = []
    for lead in leads:
        if is_trash_name(lead["name"]):
            trash_ids.append(lead["id"])

    if not trash_ids:
        log("No trash data found.")
        conn.close()
        return

    log(f"Found {len(trash_ids)} trash leads out of {len(leads)} active leads.")

    placeholders = ",".join("?" * len(trash_ids))
    cur.execute(
        f"UPDATE leads SET duplicate_of = 'trash_cleanup' WHERE id IN ({placeholders})",
        trash_ids
    )
    conn.commit()

    log(f"Marked {len(trash_ids)} leads as trash (duplicate_of='trash_cleanup').")

    # Summary
    cur.execute("SELECT COUNT(*) FROM leads WHERE duplicate_of IS NULL")
    remaining = cur.fetchone()[0]
    log(f"Remaining active leads: {remaining}")

    conn.close()


if __name__ == "__main__":
    cleanup()
