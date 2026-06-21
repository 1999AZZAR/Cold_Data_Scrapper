# Cold Data Pipeline & Dashboard - Development Roadmap

This document lists the plan, architecture, and task list for building the modular cold data gathering pipeline, preparing it for dashboard control.

---

## 🛠️ Architecture Overview

The system uses a modular, database-centric pipeline built on SQLite. Each stage is an independent Python script that reads from and writes to the SQLite database (`cold_data.db`). This layout allows any dashboard (web/desktop) to trigger, monitor, and query progress asynchronously.

```mermaid
graph TD
    A[Region & Query Input] --> B[db_init.py: Init DB]
    B --> C[extractor_osm.py]
    B --> D[extractor_gmaps.py]
    C --> E[(cold_data.db)]
    D --> E
    E --> F[enricher_socials.py]
    F --> E
    E --> G[validator_contacts.py]
    G --> E
    E --> H[deduplicator.py]
    H --> E
    E --> I[export_converter.py]
    I --> J[XML / CSV / Excel Output]
```

---

## 📅 Roadmap & Tasks

### Phase 1: Database & Extraction (Completed)
- [x] **Database Setup (`db_init.py`)**
  - Create `runs` table (track extraction jobs).
  - Create `leads` table (unified business schema with fields for geolocation, contact details, social links, source details, validation state, and custom tags).
- [x] **OSM / Overpass Extractor (`extractor_osm.py`)**
  - Extract names, addresses, contacts, coordinates, and hours.
  - Automatically update `leads` and `runs` tables.
- [x] **Google Maps Scraper (`extractor_gmaps.py`)**
  - Zero-API-key fallback + browser automation using Playwright + SerpApi wrapper.
  - Extract business name, phone, address, and coordinates.

### Phase 2: Enrichment & Validation (Completed)
- [x] **Social Media & Web Enricher (`enricher_socials.py`)**
  - Scan the business website or search DDG to discover Instagram, Facebook, emails, and WhatsApp.
- [x] **Contact Validator (`validator_contacts.py`)**
  - Normalize and validate phone numbers and email MX records via native host command.

### Phase 3: Normalization & Export (Completed)
- [x] **Data Deduplicator & Merger (`deduplicator.py`)**
  - Fuzzy name matching and geographical distance matching (Haversine).
  - Merge OSM and Google Maps data, keeping the most complete fields.
- [x] **Export Converter (`export_converter.py`)**
  - Read from database and export clean datasets to XML and CSV.

### Phase 4: Dashboard Integration
- [x] **CLI Orchestrator (`orchestrator.py`)**
  - Unified controller script to run pipeline steps with CLI flags and print JSON statuses.
- [ ] **Web Dashboard (Next.js / Vite + Tailwind CSS)**
  - Interactive UI to:
    - Launch and monitor new extraction jobs.
    - View, search, and edit database records.
    - Export clean datasets to CSV/XML with one click.
