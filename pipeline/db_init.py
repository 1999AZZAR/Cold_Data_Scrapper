#!/usr/bin/env python3
"""
Database Initializer
Sets up the SQLite database schema and optimizes with WAL mode.
"""

import os
import sqlite3
import sys

DB_PATH = "data/cold_data.db"

def init_db():
    print(f"Initializing database: {DB_PATH}...")
    dir_name = os.path.dirname(DB_PATH)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    # Enable WAL (Write-Ahead Logging) mode for concurrent dashboard and script access
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    
    cursor = conn.cursor()

    # Create runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        region TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        results_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create leads table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT,
        latitude REAL,
        longitude REAL,
        address TEXT,
        phone TEXT,
        website TEXT,
        email TEXT,
        opening_hours TEXT,
        cuisine TEXT,
        brand TEXT,
        instagram TEXT,
        facebook TEXT,
        whatsapp TEXT,
        email_verified INTEGER DEFAULT 0,
        phone_verified INTEGER DEFAULT 0,
        duplicate_of INTEGER,
        opportunity_score INTEGER DEFAULT 0,
        price_range TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id),
        FOREIGN KEY(run_id) REFERENCES runs(id)
    );
    """)

    # Schema migration safeguard for existing databases
    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN opportunity_score INTEGER DEFAULT 0;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN price_range TEXT;")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("Database schema initialized with WAL mode optimizations.")

if __name__ == "__main__":
    init_db()
