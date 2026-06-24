#!/usr/bin/env python3

import time
import random
import sqlite3
import requests

DB_PATH = "data/cold_data.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}


def log(msg, level="INFO"):
    print(f"[{level}] {msg}")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def retry_request(method, url, max_retries=3, base_delay=1.0, backoff_factor=2.0, **kwargs):
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code in (429, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            response.raise_for_status()
            return response
        except (requests.RequestException, requests.HTTPError) as e:
            if attempt == max_retries:
                raise
            delay = base_delay * (backoff_factor ** attempt) + random.uniform(0, 0.5)
            status = getattr(e, "response", None) and e.response.status_code or "?"
            log(f"Request failed (HTTP {status}): {e}. Retry {attempt+1}/{max_retries} in {delay:.1f}s...", "WARNING")
            time.sleep(delay)
    return None
