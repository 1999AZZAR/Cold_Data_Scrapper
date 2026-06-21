#!/usr/bin/env python3
"""
Contact Validator
Normalizes and validates phone numbers (creates WhatsApp links)
and checks email domains for valid MX records using native host command.
"""

import os
import sys
import sqlite3
import re
import subprocess

DB_PATH = "data/cold_data.db"

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def check_mx_record(domain):
    """
    Checks if a domain has valid MX records using native Linux 'host' command.
    """
    try:
        # Run native Linux host command to fetch MX record
        result = subprocess.run(
            ["host", "-t", "mx", domain],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            text=True
        )
        # "mail is handled by" is standard response for valid MX records
        return "mail is handled by" in result.stdout
    except Exception:
        return False

def validate_email(email):
    """
    Validates email format and MX record.
    Returns: 1 (valid), -1 (invalid)
    """
    email = email.strip()
    if not email:
        return 0
        
    # Standard email regex pattern
    pattern = r'^[^@]+@[^@]+\.[^@]+$'
    if not re.match(pattern, email):
        return -1
        
    domain = email.split('@')[-1]
    if check_mx_record(domain):
        return 1
    else:
        log(f"Domain {domain} has no valid MX records.", "WARNING")
        return -1

def normalize_phone(phone):
    """
    Normalizes phone numbers to standard international format (starts with country code).
    Mainly targets Indonesian numbers.
    """
    # Remove non-digits
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return "", ""
        
    # Replace leading '0' with Indonesian country code '62'
    if digits.startswith("08"):
        digits = "62" + digits[1:]
    elif digits.startswith("8") and len(digits) >= 9:
        digits = "62" + digits
        
    if not digits.startswith("62") and len(digits) >= 9:
        # If no country code, default to Indonesian prefix 62 for local convenience
        digits = "62" + digits
        
    formatted = f"+{digits}"
    whatsapp_link = f"https://wa.me/{digits}"
    
    return formatted, whatsapp_link

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def main():
    if not os.path.exists(DB_PATH):
        log(f"Database {DB_PATH} not found.", "ERROR")
        sys.exit(1)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query unverified emails and phone numbers
    cursor.execute("""
    SELECT id, name, phone, email 
    FROM leads 
    WHERE (email_verified = 0 OR phone_verified = 0)
      AND duplicate_of IS NULL
    """)
    leads = cursor.fetchall()
    log(f"Found {len(leads)} leads to validate.")
    
    validated_count = 0
    for lead in leads:
        lead_id, name, phone, email = lead
        
        email_status = 0
        phone_status = 0
        formatted_phone = ""
        whatsapp_link = ""
        
        # 1. Validate email
        if email:
            email_status = validate_email(email)
        
        # 2. Normalize and format phone
        if phone:
            formatted_phone, whatsapp_link = normalize_phone(phone)
            phone_status = 1 if formatted_phone else -1
            
        # Update lead in database
        try:
            cursor.execute("""
            UPDATE leads 
            SET email_verified = ?, 
                phone_verified = ?, 
                phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                whatsapp = CASE WHEN ? != '' THEN ? ELSE whatsapp END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (
                email_status, 
                phone_status, 
                formatted_phone, formatted_phone, 
                whatsapp_link, whatsapp_link, 
                lead_id
            ))
            conn.commit()
            validated_count += 1
            log(f"Validated contacts for lead '{name}' (Email status: {email_status}, Phone: {formatted_phone})")
        except sqlite3.Error as e:
            log(f"Database error updating lead {lead_id}: {e}", "WARNING")
            
    # Recalculate opportunity scores for all leads
    try:
        cursor.execute("""
        UPDATE leads 
        SET opportunity_score = CASE WHEN duplicate_of IS NOT NULL THEN 0 ELSE (
          (CASE WHEN (website IS NULL OR website = '') THEN 30 ELSE 0 END) +
          (CASE WHEN (instagram IS NULL OR instagram = '') THEN 20 ELSE 0 END) +
          (CASE WHEN (facebook IS NULL OR facebook = '') THEN 10 ELSE 0 END) +
          (CASE WHEN (phone IS NULL OR phone = '') THEN 15 ELSE 0 END) +
          (CASE WHEN (email IS NULL OR email = '') THEN 15 ELSE 0 END) +
          (CASE WHEN (address IS NULL OR address = '') THEN 10 ELSE 0 END) +
          (CASE WHEN email_verified = -1 THEN 10 ELSE 0 END) +
          (CASE WHEN phone_verified = -1 THEN 10 ELSE 0 END)
        ) END
        """)
        conn.commit()
        log("Opportunity scores recalculated for all leads.")
    except sqlite3.Error as e:
        log(f"Failed to update opportunity scores: {e}", "WARNING")
        
    conn.close()
    log(f"Validation completed. Validated {validated_count} leads.", "SUCCESS")

if __name__ == "__main__":
    main()
