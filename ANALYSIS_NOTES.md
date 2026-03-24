# Food Analysis Project — Reference Notes

> Last updated: 2026-03-15
> Data coverage: **2026-01-02 → 2026-03-15** (Jan–Mar 2026, Mainz-Kostheim)

---

## Project Overview

An automated food receipt analysis system that:

1. **Syncs receipts from Google Drive** (`sync_from_drive.py`)
2. **Extracts item data** from HIT PDFs via pdfplumber, Lidl images via local Tesseract OCR, and Restaurant bills via pdfplumber + Tesseract fallback (`extract_receipts.py`, `seed_data.py`)
3. **Categorizes items** with health scores (`food_categories.py`)
4. **Visualizes everything** in a Streamlit dashboard (`dashboard.py`)

---

## Project Structure

```
Food_Analysis/
├── dashboard.py              # Streamlit dashboard (run: streamlit run dashboard.py)
├── extract_receipts.py       # PDF + image → CSV extractor (incremental, new files only)
├── food_categories.py        # Category classification + health scoring
├── sync_from_drive.py        # Google Drive sync
├── seed_data.py              # Full re-seed of all receipts from scratch
├── run_weekly_update.bat     # Windows: weekly sync + seed
├── Launch Dashboard.bat      # Windows: open dashboard
├── setup_weekly_task.ps1     # Windows Task Scheduler setup
├── credentials.json          # Google OAuth credentials (DO NOT share)
├── token.json                # OAuth token (auto-refreshed)
│
├── Grocery bills/
│   ├── Hit Bills/            # HIT receipts as PDFs
│   ├── Lidl bills/           # Lidl receipts as PNGs
│   └── Restaurant bills/     # Restaurant receipts (PDF or image)
│
└── data/
    ├── receipts.csv          # One row per shopping trip
    ├── items.csv             # One row per purchased item
    └── update_log.txt        # Sync history log
```

---

## How Each Script Works

### `extract_receipts.py` — Incremental processor

| Store | Format | Method |
|-------|--------|--------|
| HIT | PDF | `pdfplumber` text extraction + regex parsing |
| Lidl | PNG | Local **Tesseract OCR** (`pytesseract`, free, no API) |

- Skips already-processed receipts by checking `receipt_id` in `receipts.csv`
- Use `--force` flag to re-process everything

**Receipt ID format:**
- HIT: `HIT_YYYYMMDD_<filename_stem>`
- Lidl: `Lidl_YYYYMMDD_<filename_stem>`

### `seed_data.py` — Full re-seed

Rebuilds both CSVs from scratch:
- **HIT** — live pdfplumber extraction
- **Lidl** — hardcoded `LIDL_RECEIPTS` list (42 receipts, manually verified, free)
- **Restaurant** — pdfplumber for text PDFs; Tesseract OCR fallback for image PDFs; `RESTAURANT_OVERRIDES` dict for manually verified bills

**To add a new verified restaurant receipt:**
```python
RESTAURANT_OVERRIDES = {
    "Pizza Hut March26": {
        "restaurant_name": "Pizza Hut",
        "date": "2026-03-10",
        "total": 25.80,
        "items": [
            {"name": "Lunch Deal (CYO Pan S)", "price": 12.90, "quantity": "1"},
            {"name": "Lunch Deal (Cheese Love's Pan S)", "price": 12.90, "quantity": "1"},
            {"name": "Pepsi 0.3L", "price": 0.00, "quantity": "1"},
        ],
    },
    # Add future restaurant receipts here using filename stem as key
}
```

### `food_categories.py`

Health scores (0–10):

| Score | Label | Categories |
|-------|-------|------------|
| 9 | Very Healthy | Früchte, Gemüse, Wasser |
| 8 | Very Healthy | Eier, Fisch & Meeresfrüchte, Hülsenfrüchte & Nüsse |
| 7 | Healthy | Gesunde Getränke |
| 6 | Healthy | Milchprodukte, Fleisch & Geflügel, Brot & Getreide |
| 5 | Moderate | Restaurant |
| 4 | Moderate | Fertiggerichte & Saucen |
| 3 | Unhealthy | Zuckerhaltige Getränke, Snacks & Chips |
| 2 | Unhealthy | Süßigkeiten & Desserts |
| 0 | Non-Food | Cleaning, hygiene, packaging |

Classification uses **longest-keyword-match** against German item names.

**Important:** Restaurant items always get category `Restaurant` (score 5) regardless of ingredient keywords in the dish name — prevents false matches like "Pizza Ananas" → Gemüse score 9.

**To add new keywords:** Edit `CATEGORIES` dict in `food_categories.py`, then re-run `seed_data.py`.

### `sync_from_drive.py`

Three Google Drive folders configured:
- **HIT folder**: `1debrgin6k4yr0_nil3NcRyjrx2BqzLlR`
- **Lidl folder**: `1QFaAZ5Ml5INAhSpfbbw1prJuxpi0QdZv`
- **Restaurant folder**: `1luZIK0Hsb9cCwirOGJAWL5PY7MyK5nLJ`

OAuth flow: `credentials.json` → `token.json` (auto-refreshes).

**Known fix applied:** Google Drive filenames use colons (`Receipt 14.03.2026 18:13.pdf`) which are illegal on Windows NTFS. The sync script replaces `:` → `_` before saving locally.

---

## Cost Analysis

| Component | Cost | Notes |
|-----------|------|-------|
| HIT PDF extraction | **€0** | pdfplumber — local |
| Lidl image OCR | **€0** | Tesseract — local (replaced Claude Vision API) |
| Restaurant image PDFs | **€0** | Tesseract fallback — local |
| Google Drive sync | **€0** | Free tier |
| Dashboard | **€0** | Streamlit — local |
| **Total** | **€0/month** | Fully cost-neutral |

**Tesseract setup (one-time):**
```bash
sudo apt install tesseract-ocr tesseract-ocr-deu
pip install pytesseract pillow
```

---

## Data Summary (Jan–Mar 2026)

### Receipts by Store

| Store | Receipts | Total |
|-------|----------|-------|
| Lidl | 42 | ~€469 |
| HIT | 12 | ~€264 |
| Restaurant | 1 | €25.80 |
| **Total** | **55** | **~€759** |

### Monthly Spending

| Month | Lidl | HIT | Restaurant | Total |
|-------|------|-----|------------|-------|
| Jan 2026 | ~€166 | ~€111 | — | ~€277 |
| Feb 2026 | ~€173 | ~€147 | — | ~€320 |
| Mar 2026 (to Mar 15) | ~€130 | ~€7 | €25.80 | ~€163 |

### Top Recurring Items

**Lidl:** Bioland Naturjoghurt, Bio-Eier OKT, Banane lose, Tomaten Strauch, Bio Baby Spinat, Bio Mini Möhren

**HIT:** Trinkkokosnuss (bought 2–5 at a time), ja! Miwa Still, Datteln Medjoul

**Restaurant:** Pizza Hut (1 visit — 2× Lunch Deal + Pepsi, €25.80)

### Health Profile

- Diet predominantly healthy — fruits, vegetables, eggs, nuts dominate
- Recurring indulgences: Donuts, Croissants, Berliner (1–3/week)
- Trinkkokosnuss classified as Früchte (score 9) — correct
- Pizza Hut visit: Restaurant score 5 (food) + Pepsi score 3 (drink)

---

## Running the System

### Initial Setup

```bash
# Install dependencies
pip install streamlit plotly pandas pdfplumber pytesseract pillow \
            google-auth google-auth-oauthlib google-api-python-client

# Install Tesseract (WSL/Ubuntu)
sudo apt install tesseract-ocr tesseract-ocr-deu

# Authorize Google Drive (one-time, opens browser)
python sync_from_drive.py --setup

# Full seed of all receipts
python seed_data.py

# Launch dashboard
streamlit run dashboard.py
```

### Weekly Update

```bash
python sync_from_drive.py        # downloads new files + auto re-seeds if new found
```

Or use the dashboard **"Pull from Google Drive + Refresh"** button in the sidebar.

On Windows: double-click `run_weekly_update.bat` or use Task Scheduler via `setup_weekly_task.ps1`.

### Force Re-process All Receipts

```bash
python -X utf8 seed_data.py      # full rebuild from scratch
python extract_receipts.py --force   # re-extract all incrementally
```

---

## Dashboard Features

| Section | What it shows |
|---------|---------------|
| KPI Row | Total spend, avg/trip, trips, health score, healthy % |
| Health Gauge | Overall health score out of 10 |
| Spending by Health Category | Bar chart: Very Healthy → Unhealthy |
| Monthly Spending | Stacked bar (HIT + Lidl + Restaurant) with total line |
| Category Pie | Food spend breakdown by category |
| Weekly Health Trend | Line chart with healthy threshold at 6 |
| Store Comparison | All stores: spend + avg health score |
| Restaurant vs Grocery | Monthly split when restaurant data present |
| Healthy vs Unhealthy Over Time | Stacked bar per month |
| Top Items | By total spend (€) and by frequency |
| Raw Explorer | Filterable table of all items |

Sidebar: **Store** and **Month(s)** filters + **"Pull from Google Drive + Refresh"** button.

**Note:** Subtitle, store comparison header, and footer date range are all auto-generated from live data — no hardcoded store names.

---

## Data Schema

### `receipts.csv`

| Column | Type | Description |
|--------|------|-------------|
| receipt_id | string | Unique ID per trip |
| date | date | Purchase date |
| store | string | HIT / Lidl / Restaurant |
| total | float | Receipt total (€) |
| item_count | int | Number of items |

### `items.csv`

| Column | Type | Description |
|--------|------|-------------|
| receipt_id | string | Links to receipts.csv |
| date | date | Purchase date |
| store | string | Store name |
| name | string | Item name (German) |
| price | float | Item price (€) |
| quantity | string | Count or weight (e.g. "1", "0.5 kg") |
| receipt_category | string | HIT section / "Lidl" / restaurant name |
| category | string | Normalized category from food_categories.py |
| health_score | int | 0–9 health score |

---

## Known Issues & Fixes Applied

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| March 14 HIT bill not syncing | Google Drive filename had `:` (illegal on Windows NTFS) | `sync_from_drive.py` replaces `:` → `_` before saving |
| Pizza Hut total = €0.00 | Image-only PDF — pdfplumber got no text, no fallback | Added Tesseract OCR fallback for image PDFs in `seed_data.py` |
| "CYO Pan S Ananas" scored 9 (Gemüse) | Ingredient keywords in dish name triggered false match | Restaurant items always forced to Restaurant category (score 5) |
| Pepsi scored 5 instead of 3 | "pepsi" missing from Zuckerhaltige Getränke keywords | Added pepsi, coca-cola, 7up to keywords |
| Lidl receipts cost ~€0.002/receipt | Claude Vision API called per new PNG | Replaced with free local Tesseract OCR |

---

## Adding a New Store

1. Create a folder under `Grocery bills/`
2. Add a Google Drive folder ID to `sync_from_drive.py` (`GDRIVE_<STORE>_FOLDER_ID`)
3. Add a `sync_folder()` call in `sync_from_drive.py`
4. Add a parser in `extract_receipts.py` or `seed_data.py` for the receipt format
5. Add a color entry in `dashboard.py`: `colors_store = {"HIT": ..., "Lidl": ..., "NewStore": "#HEX"}`
6. Dashboard subtitle, comparison header, and footer update automatically

---

## Restaurant Personal Share Feature

For group outings where one person pays the full bill, rename the file on Google Drive before sync:

```
Pizza Hut March26 [me=12.90].pdf    ← consumed €12.90 of the €25.80 bill
Birthday Dinner [me=25%].pdf        ← 25% share
Friends BBQ [me=0].pdf              ← paid but ate nothing
```

Full implementation spec is in **RESTAURANT_SHARE_GUIDE.md** — covers changes needed across `sync_from_drive.py`, `seed_data.py`, `receipts.csv`, and `dashboard.py`.

---

## Potential Improvements

- [ ] Price-per-kg normalization for weight-based items
- [ ] Export weekly health report as PDF
- [ ] Alert when monthly spending exceeds a threshold
- [ ] Track price changes for recurring items over time
- [ ] Riffle Chips Paprika currently maps to Gemüse — add explicit snack keyword
- [ ] Auto-detect new restaurant receipts via Tesseract without needing manual override
