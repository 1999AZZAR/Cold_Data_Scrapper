#!/usr/bin/env python3
"""
Copyright (c) 2026 Azzar Budiyanto / LilyOpenCMS.
All rights reserved.

Contact: azzar.mr.zs@gmail.com for inquiries.
"""
"""
Social Media and Contact Enricher
Scrapes business website (if available) or queries DuckDuckGo search 
to find Instagram, Facebook, emails, and WhatsApp contacts for leads in the DB.
"""

import os
import sys
import sqlite3
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from utils import log, get_db_connection, retry_request
except ImportError:
    from pipeline.utils import log, get_db_connection, retry_request

load_dotenv()

DB_PATH = "data/cold_data.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {'User-Agent': USER_AGENT}

def search_social_google_gse(name, region, platform):
    """
    Searches Google Custom Search Engine (GSE) for the business name + platform.
    """
    gse_api = os.getenv('GSE_API_KEY')
    gse_id = os.getenv('GSE_ID')
    if not gse_api or not gse_id:
        return ""
        
    query = f"{name} {region} {platform}"
    url = 'https://www.googleapis.com/customsearch/v1/'
    params = {
        'q': query,
        'key': gse_api,
        'cx': gse_id,
        'safe': 'off',
        'num': 5,
        'filter': 0
    }
    
    try:
        log(f"Searching Google GSE for {platform}: '{name}' in '{region}'...")
        response = retry_request("GET", url, params=params, timeout=10, max_retries=2)
        data = response.json()
        items = data.get('items', [])
        
        for item in items:
            link = item.get('link', '')
            if f"{platform}.com/" in link.lower() and "/p/" not in link.lower() and "/tags/" not in link.lower():
                log(f"Discovered {platform} link via Google GSE: {link}")
                return link
    except Exception as e:
        log(f"Google GSE search failed for {platform}: {e}", "WARNING")
        
    return ""

def extract_contacts_from_html(html_content, base_url):
    """
    Parses website HTML to find email addresses and social media links.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    
    # 1. Extract email addresses using regex
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = re.findall(email_pattern, text)
    email = emails[0].strip() if emails else ""
    
    # 2. Extract social links from anchor hrefs
    instagram = ""
    facebook = ""
    whatsapp = ""
    
    for a in soup.find_all('a', href=True):
        href = a['href'].lower()
        if "instagram.com/" in href and not instagram:
            instagram = a['href']
        elif "facebook.com/" in href and not facebook:
            facebook = a['href']
        elif ("wa.me/" in href or "api.whatsapp.com/send" in href or "whatsapp:" in href) and not whatsapp:
            whatsapp = a['href']
            
    return email, instagram, facebook, whatsapp

def scrape_website(url):
    """
    Fetches the website URL and extracts contact info.
    """
    if not url.startswith("http"):
        url = "http://" + url
        
    try:
        log(f"Scraping website: {url}...")
        response = retry_request("GET", url, headers=HEADERS, timeout=10, max_retries=2)
        return extract_contacts_from_html(response.text, url)
    except Exception as e:
        log(f"Website scrape failed: {e}", "WARNING")
        return "", "", "", ""

def search_social_duckduckgo(name, region, platform):
    """
    Searches DuckDuckGo HTML search for the business name + platform.
    Returns the discovered social page URL.
    """
    query = f"{name} {region} {platform}"
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    
    try:
        log(f"Searching DDG for {platform}: '{name}' in '{region}'...")
        response = retry_request("GET", url, headers=HEADERS, timeout=10, max_retries=2)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', class_='result__a', href=True)
        
        for link in links:
            href = link['href']
            if "uddg=" in href:
                parsed = urllib.parse.urlparse(href)
                query_params = urllib.parse.parse_qs(parsed.query)
                if "uddg" in query_params:
                    href = query_params["uddg"][0]
                    
            if f"{platform}.com/" in href.lower() and "/p/" not in href.lower() and "/tags/" not in href.lower():
                log(f"Discovered {platform} link: {href}")
                return href
    except Exception as e:
        log(f"DDG search failed for {platform}: {e}", "WARNING")
        
    return ""

def search_social_bing(name, region, platform):
    query = f"{name} {region} {platform}"
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    try:
        log(f"Searching Bing for {platform}: '{name}' in '{region}'...")
        response = retry_request("GET", url, headers=HEADERS, timeout=10, max_retries=2)
        soup = BeautifulSoup(response.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if f"{platform}.com/" in href.lower() and "/p/" not in href.lower() and "/tags/" not in href.lower():
                log(f"Discovered {platform} link via Bing: {href}")
                return href
    except Exception as e:
        log(f"Bing search failed for {platform}: {e}", "WARNING")
    return ""


def enrich_lead(lead_id, name, address, website):
    email, instagram, facebook, whatsapp = "", "", "", ""

    if website:
        email, instagram, facebook, whatsapp = scrape_website(website)

    region = address.split(",")[-1].strip() if address else "Indonesia"

    if not instagram:
        instagram = search_social_google_gse(name, region, "instagram")
        if not instagram:
            instagram = search_social_duckduckgo(name, region, "instagram")
            if not instagram:
                instagram = search_social_bing(name, region, "instagram")

    if not facebook:
        facebook = search_social_google_gse(name, region, "facebook")
        if not facebook:
            facebook = search_social_duckduckgo(name, region, "facebook")
            if not facebook:
                facebook = search_social_bing(name, region, "facebook")

    return email, instagram, facebook, whatsapp

def main():
    if not os.path.exists(DB_PATH):
        log(f"Database {DB_PATH} not found.", "ERROR")
        sys.exit(1)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Select leads where email/instagram/facebook is missing and not marked as duplicate
    cursor.execute("""
    SELECT id, name, address, website 
    FROM leads 
    WHERE (email IS NULL OR email = '' OR instagram IS NULL OR instagram = '' OR facebook IS NULL OR facebook = '')
      AND duplicate_of IS NULL
    """)
    
    leads = cursor.fetchall()
    log(f"Found {len(leads)} leads eligible for social media enrichment.")
    
    updated_count = 0
    for lead in leads:
        lead_id, name, address, website = lead
        log(f"Enriching: '{name}' (ID: {lead_id})...")
        
        email, instagram, facebook, whatsapp = enrich_lead(lead_id, name, address, website)
        
        # Build update queries
        updates = []
        params = []
        
        if email:
            updates.append("email = ?")
            params.append(email)
        if instagram:
            updates.append("instagram = ?")
            params.append(instagram)
        if facebook:
            updates.append("facebook = ?")
            params.append(facebook)
        if whatsapp:
            updates.append("whatsapp = ?")
            params.append(whatsapp)
            
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(lead_id)
            query = f"UPDATE leads SET {', '.join(updates)} WHERE id = ?"
            try:
                cursor.execute(query, params)
                conn.commit()
                updated_count += 1
                log(f"Successfully updated lead: '{name}'")
            except sqlite3.Error as e:
                log(f"Failed to update database for lead {lead_id}: {e}", "WARNING")
                
        # Politeness rate limiting delay between scraping/queries
        import time
        time.sleep(2)
        
    # Recalculate opportunity scores for all leads after enrichment
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
        log("Opportunity scores recalculated for all leads after social enrichment.")
    except sqlite3.Error as e:
        log(f"Failed to update opportunity scores: {e}", "WARNING")

    conn.close()
    log(f"Enrichment task completed. Enriched {updated_count} leads.", "SUCCESS")

if __name__ == "__main__":
    main()
