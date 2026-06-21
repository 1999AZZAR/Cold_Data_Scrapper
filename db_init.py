#!/usr/bin/env python3
"""
Database Initializer
Sets up the SQLite database schema for the Cold Data Pipeline.
"""

import os
import sqlite3
import sys

DB_PATH = "cold_data.db"

def init_db():
    print(f"Initializing database: {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id),
        FOREIGN KEY(run_id) REFERENCES runs(id)
    );
    """)

    conn.commit()
    conn.close()
    print("Database schema initialized successfully.")

if __name__ == "__main__":
    init_db()
