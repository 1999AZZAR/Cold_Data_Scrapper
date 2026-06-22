#!/usr/bin/env python3
"""
Copyright (c) 2026 Azzar Budiyanto / LilyOpenCMS.
All rights reserved.

Contact: azzar.mr.zs@gmail.com for inquiries.
"""
"""
Google Maps Extraper Script
Gathers business details from Google Maps.
Supports:
1. SerpApi (API-based: stable, fast, recommended)
2. Playwright (Browser-based: local scraping, requires 'pip install playwright')
"""

import os
import sys
import argparse
import json
import sqlite3
import csv
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import requests

DB_PATH = "data/cold_data.db"

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def get_cached_search(query, region, engine="google_maps"):
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT search_id, json_response, created_at
            FROM search_archive
            WHERE query = ? AND region = ? AND engine = ?
              AND datetime(created_at) >= datetime('now', '-31 days')
            ORDER BY created_at DESC
            LIMIT 1
        """, (query, region, engine))
        row = cursor.fetchone()
        conn.close()
        if row:
            log(f"Cache hit: search_id={row[0]}, cached at {row[2]}")
            return json.loads(row[1]) if row[1] else None
    except Exception as e:
        log(f"Cache lookup failed: {e}", "WARNING")
    return None

def cache_search(search_id, query, region, engine, page_offset, result_count, json_data):
    if not search_id or not os.path.exists(DB_PATH):
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO search_archive
            (search_id, query, region, engine, page_offset, result_count, json_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (search_id, query, region, engine, page_offset, result_count, json.dumps(json_data)))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"Cache store failed: {e}", "WARNING")

def purge_expired_caches():
    if not os.path.exists(DB_PATH):
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_archive WHERE datetime(created_at) < datetime('now', '-31 days')")
        purged = cursor.rowcount
        conn.commit()
        conn.close()
        if purged > 0:
            log(f"Purged {purged} expired cache entries.")
        return purged
    except Exception as e:
        log(f"Cache purge failed: {e}", "WARNING")
        return 0

def parse_serpapi_results(data, limit=None):
    records = []
    results = data.get("local_results", [])
    for item in (results[:limit] if limit else results):
        gps = item.get("gps_coordinates", {})
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        records.append({
            "source_id": str(item.get("data_id", "")),
            "name": item.get("title", "Unnamed Business"),
            "category": item.get("type", "Business"),
            "latitude": float(lat) if lat else None,
            "longitude": float(lon) if lon else None,
            "address": item.get("address", ""),
            "phone": item.get("phone", ""),
            "website": item.get("website", ""),
            "email": "",
            "opening_hours": "",
            "cuisine": "",
            "brand": "",
            "instagram": "",
            "facebook": "",
            "whatsapp": "",
            "price_range": item.get("price", ""),
            "rating": float(item["rating"]) if item.get("rating") else None,
            "review_count": int(item["reviews"]) if item.get("reviews") else None,
            "maps_link": item.get("link", "")
        })
    return records

def run_serpapi(query, region, api_key, limit, search_id=None):
    """
    Query Google Maps data using SerpApi with automatic caching.
    Checks local cache first, then SerpAPI archive, then fresh search.
    """
    engine = "google_maps"

    # 1. Direct search_id → fetch from SerpAPI archive
    if search_id:
        log(f"Fetching from SerpAPI archive: search_id={search_id}...")
        url = f"https://serpapi.com/searches/{search_id}.json"
        params = {"api_key": api_key}
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                log(f"SerpApi archive error: {data['error']}", "ERROR")
                return [], search_id
            records = parse_serpapi_results(data, limit)
            log(f"SerpApi archive returned {len(records)} results.")
            return records, search_id
        except Exception as e:
            log(f"Failed to fetch from SerpApi archive: {e}", "ERROR")
            return [], None

    # 2. Auto-check local cache (zero credits, zero network)
    cached = get_cached_search(query, region, engine)
    if cached:
        log("Reusing locally cached SerpAPI results (0 credits).")
        records = parse_serpapi_results(cached, limit)
        sid = cached.get("search_metadata", {}).get("id")
        return records, sid

    # 3. Fresh search with auto-caching per page
    log("Running fresh SerpAPI Google Maps search...")
    url = "https://serpapi.com/search.json"
    params = {
        "engine": engine,
        "q": f"{query} in {region}",
        "api_key": api_key,
        "hl": "id",
        "gl": "id"
    }

    effective_limit = limit if limit else 500
    records = []
    start = 0
    retrieved_search_id = None

    while True:
        params["start"] = start
        try:
            log(f"Requesting SerpAPI results at offset {start}...")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            page_search_id = data.get("search_metadata", {}).get("id")
            if not retrieved_search_id and page_search_id:
                retrieved_search_id = page_search_id
                log(f"SerpApi Search ID: {page_search_id}")

            results = data.get("local_results", [])
            if not results:
                log("No more results.")
                break

            log(f"SerpApi returned {len(results)} results at offset {start}.")

            # Cache this page's full response
            cache_search(page_search_id, query, region, engine, start, len(results), data)

            records.extend(parse_serpapi_results(data))

            if len(records) >= effective_limit:
                log(f"Reached limit of {effective_limit} records.")
                break

            next_link = data.get("serpapi_pagination", {}).get("next")
            if not next_link:
                log("No next page.")
                break

            start += 20
        except Exception as e:
            log(f"SerpApi request failed: {e}", "ERROR")
            break

    return records, retrieved_search_id

def run_playwright(query, region, limit):
    """
    Run local Google Maps scraper using Playwright browser automation.
    """
    log("Attempting Playwright browser automation...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright is not installed. Install via: pip install playwright && playwright install", "ERROR")
        return []

    records = []
    search_query = f"{query} in {region}"
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
    
    with sync_playwright() as p:
        log("Launching headless browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        
        # Accept cookie consents if prompted
        try:
            page.wait_for_selector("form[action*='consent'] button", timeout=3000)
            consent_buttons = page.query_selector_all("form[action*='consent'] button")
            if consent_buttons:
                consent_buttons[-1].click()
                log("Accepted Google consent cookies.")
        except Exception:
            pass
            
        log("Waiting for map search results...")
        # Search sidebar selector
        sidebar_selector = "div[role='feed']"
        try:
            page.wait_for_selector(sidebar_selector, timeout=10000)
        except Exception:
            log("Result sidebar feed not found. Google Maps layout may have changed.", "WARNING")
            browser.close()
            return []

        # Scroll sidebar to load results
        log("Scrolling sidebar to extract results...")
        
        effective_limit = limit if limit else 500
        last_count = 0
        scroll_attempts = 0
        
        while scroll_attempts < 5:
            # Scroll feed container directly
            page.evaluate("const feed = document.querySelector(\"div[role='feed']\"); if (feed) { feed.scrollBy(0, 10000); }")
            page.wait_for_timeout(2000)
            
            # Count current cards
            cards = page.query_selector_all("a[href*='/maps/place/']")
            current_count = len(cards)
            log(f"Sidebar scroll: found {current_count} places...")
            
            if current_count >= effective_limit:
                break
                
            if current_count == last_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_count = current_count
                
            # Stop if Google Maps footer message is reached
            if page.query_selector("text=\"You've reached the end of the list.\""):
                log("Reached the end of the Google Maps list.")
                break
            
        # Get elements
        cards = page.query_selector_all("a[href*='/maps/place/']")
        log(f"Found {len(cards)} places total. Beginning extraction...")
        
        count = 0
        for card in cards:
            if count >= effective_limit:
                break
                
            try:
                # Hover and click to trigger detail view
                card.click()
                page.wait_for_timeout(1500)
                
                # Scrape detail view
                name_elem = page.query_selector("h1")
                name = name_elem.inner_text() if name_elem else "Unnamed Business"
                
                # Categorization (usually text next to rating stars)
                cat_elem = page.query_selector("button[jsaction*='pane.rating.category']")
                category = cat_elem.inner_text() if cat_elem else "Business"
                
                # Phone number
                phone_elem = page.query_selector("button[data-item-id*='phone:tel:']")
                phone = phone_elem.get_attribute("data-item-id").replace("phone:tel:", "").strip() if phone_elem else ""
                
                # Website
                web_elem = page.query_selector("a[data-item-id='authority']")
                website = web_elem.get_attribute("href") if web_elem else ""
                
                # Address
                addr_elem = page.query_selector("button[data-item-id='address']")
                address = addr_elem.inner_text() if addr_elem else ""
                
                # Lat/Lon extraction from current URL
                current_url = page.url
                lat, lon = None, None
                if "@" in current_url:
                    parts = current_url.split("@")[1].split(",")
                    if len(parts) >= 2:
                        lat, lon = float(parts[0]), float(parts[1])
                
                # Price range/level (e.g., $$, $$$ or price per person range)
                price_range = ""
                try:
                    price_elem = page.query_selector("span[aria-label*='price'], span[aria-label*='Price'], span[aria-label*='harga'], span[aria-label*='Harga']")
                    if price_elem:
                        price_range = price_elem.inner_text().strip()
                    else:
                        details_container = page.query_selector("div[class*='fontBodyMedium']")
                        if details_container:
                            text = details_container.inner_text()
                            import re
                            price_match = re.search(r'(Rp\s*\d+[\d.,]*\s*–\s*Rp\s*\d+[\d.,]*|Rp\s*\d+[\d.,]*\s*–\s*\d+[\d.,]*|\$\d+\s*–\s*\d+|\b\${1,4}\b)', text)
                            if price_match:
                                price_range = price_match.group(0).strip()
                except Exception:
                    pass

                records.append({
                    "source_id": card.get_attribute("href").split("/place/")[1].split("/")[0],
                    "name": name,
                    "category": category,
                    "latitude": lat,
                    "longitude": lon,
                    "address": address,
                    "phone": phone,
                    "website": website,
                    "email": "",
                    "opening_hours": "",
                    "cuisine": "",
                    "brand": "",
                    "instagram": "",
                    "facebook": "",
                    "whatsapp": "",
                    "price_range": price_range,
                    "rating": None,
                    "review_count": None,
                    "maps_link": current_url
                })
                count += 1
                log(f"Extracted: {name}")
            except Exception as e:
                log(f"Error scraping card: {e}", "WARNING")
                
        browser.close()
    return records

def save_to_db(records, query_name, region_name, run_id=None, search_id=None):
    """
    Saves records to SQLite database.
    """
    if not os.path.exists(DB_PATH):
        log(f"Database {DB_PATH} not found. Run db_init.py first.", "ERROR")
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if run_id is None:
            cursor.execute(
                "INSERT INTO runs (query, region, status, search_id) VALUES (?, ?, 'running', ?)",
                (query_name, region_name, search_id)
            )
            run_id = cursor.lastrowid
        else:
            if search_id:
                cursor.execute(
                    "UPDATE runs SET status='running', search_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (search_id, run_id)
                )
            else:
                cursor.execute(
                    "UPDATE runs SET status='running', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (run_id,)
                )

        inserted_count = 0
        for r in records:
            try:
                # Calculate initial opportunity score
                score = 0
                if not r.get("website"): score += 30
                if not r.get("instagram"): score += 20
                if not r.get("facebook"): score += 10
                if not r.get("phone"): score += 15
                if not r.get("email"): score += 15
                if not r.get("address"): score += 10

                cursor.execute("""
                INSERT OR REPLACE INTO leads (
                    run_id, source, source_id, name, category, latitude, longitude,
                    address, phone, website, email, opening_hours, cuisine, brand,
                    instagram, facebook, whatsapp, opportunity_score, price_range, rating, review_count, maps_link, updated_at
                ) VALUES (?, 'gmaps', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    run_id, r["source_id"], r["name"], r["category"], r["latitude"], r["longitude"],
                    r["address"], r["phone"], r["website"], r["email"], r["opening_hours"],
                    r["cuisine"], r["brand"], r["instagram"], r["facebook"], r["whatsapp"], score, r.get("price_range"), r.get("rating"), r.get("review_count"), r.get("maps_link")
                ))
                inserted_count += 1
            except sqlite3.Error as e:
                log(f"Failed to insert record {r['name']}: {e}", "WARNING")

        if search_id:
            cursor.execute(
                "UPDATE runs SET status='completed', results_count=results_count+?, search_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (inserted_count, search_id, run_id)
            )
        else:
            cursor.execute(
                "UPDATE runs SET status='completed', results_count=results_count+?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (inserted_count, run_id)
            )
        conn.commit()
        log(f"Saved {inserted_count} records to SQLite database (Run ID: {run_id}).")
        return run_id
    except sqlite3.Error as e:
        conn.rollback()
        log(f"Database error: {e}", "ERROR")
        return None
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Gathers local business data from Google Maps.")
    parser.add_argument("-q", "--query", required=True, help="Scraping search query (e.g. 'cafe')")
    parser.add_argument("-r", "--region", required=True, help="Region to search (e.g. 'Jakarta Selatan')")
    parser.add_argument("-k", "--key", help="SerpApi Key (optional)")
    parser.add_argument("-l", "--limit", type=int, help="Limit number of results")
    parser.add_argument("-o", "--output", help="Output file prefix (default: region_query)")
    parser.add_argument("--run-id", type=int, help="Optional database run ID to associate data and update status")
    parser.add_argument("--search-id", help="Optional SerpApi search ID to fetch from search archive")
    parser.add_argument("--reuse-search", action="store_true", help="(Deprecated) Auto-reuse is now always on")
    
    args = parser.parse_args()
    
    # Auto-purge expired cache entries on startup
    purge_expired_caches()
    
    api_key = args.key or os.environ.get("SERPAPI_KEY")
    records = []
    retrieved_search_id = None
    
    # Auto-reuse: always check cache unless explicit search_id provided
    if api_key:
        records, retrieved_search_id = run_serpapi(args.query, args.region, api_key, args.limit, search_id=args.search_id)
    else:
        records = run_playwright(args.query, args.region, args.limit)
        
    if not records:
        log("No records retrieved. Please provide a SERPAPI_KEY or install playwright.", "ERROR")
        sys.exit(1)
        
    # Save to SQLite
    save_to_db(records, args.query, args.region, run_id=args.run_id, search_id=retrieved_search_id)
    
    # Export files
    output_prefix = args.output or f"{args.region.lower().replace(' ', '_')}_{args.query.lower().replace(' ', '_')}_gmaps"
    os.makedirs("exports", exist_ok=True)
    if not output_prefix.startswith("exports/"):
        output_prefix = os.path.join("exports", os.path.basename(output_prefix))
    
    # Export CSV
    with open(f"{output_prefix}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    log(f"Exported CSV successfully: {output_prefix}.csv")

    # Export XML
    root = ET.Element("businesses")
    for r in records:
        business_el = ET.SubElement(root, "business")
        for k, v in r.items():
            child = ET.SubElement(business_el, k)
            child.text = str(v) if v is not None else ""
            
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")
    
    with open(f"{output_prefix}.xml", "wb") as f:
        f.write(pretty_xml)
    log(f"Exported XML successfully: {output_prefix}.xml")
    
    log("Completed successfully.", "SUCCESS")

if __name__ == "__main__":
    main()
