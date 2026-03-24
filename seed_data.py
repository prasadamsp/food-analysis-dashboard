"""
seed_data.py
────────────
Builds receipts.csv and items.csv from:
  - HIT receipts         → extracted live via pdfplumber
  - Lidl receipts        → hardcoded from visual extraction (all 42 receipts)
  - Restaurant receipts  → extracted via pdfplumber (PDF) or Claude API (images)

Run:  python -X utf8 seed_data.py
"""

import re, os, json, base64
from datetime import datetime
from pathlib import Path

import pdfplumber
import pandas as pd
from food_categories import classify_item

BASE_DIR        = Path(__file__).parent
HIT_DIR         = BASE_DIR / "Grocery bills" / "Hit Bills"
LIDL_DIR        = BASE_DIR / "Grocery bills" / "Lidl bills"
RESTAURANT_DIR  = BASE_DIR / "Grocery bills" / "Restaurant bills"
DATA_DIR        = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RECEIPTS_CSV = DATA_DIR / "receipts.csv"
ITEMS_CSV    = DATA_DIR / "items.csv"

# ══════════════════════════════════════════════════════════════════════════════
# LIDL DATA  (visually extracted from all 42 PNG receipts)
# Format: {"date": "YYYY-MM-DD", "total": float, "items": [(name, price, qty)]}
# Deposit rows (Pfand/Leergut) and non-food items are kept so the dashboard
# can show the full spending picture; Non-Food classifier excludes them
# from the health score.
# ══════════════════════════════════════════════════════════════════════════════
LIDL_RECEIPTS = [
    {"date": "2026-01-02", "total": 33.61, "items": [
        ("Litschi", 1.45, "1"),
        ("Orangen", 2.99, "0.296 kg"),
        ("Avocado", 2.99, "1"),
        ("Erdbeeren 250g", 4.58, "2"),
        ("Traub hell 500g", 2.49, "1"),
        ("Zuckermais", 2.49, "1"),
        ("Zitronen", 0.99, "1"),
        ("Bio-Eier OKT", 6.78, "2"),
        ("Knorr Spargelcreme", 3.18, "2"),
        ("Knorr Feinschm.Blum.", 0.79, "1"),
        ("Knorr Suppen Toscana", 1.59, "1"),
        ("Oreo Remix Brownie", 1.39, "1"),
        ("Mandeln Honig/Salz", 1.99, "1"),
        ("Knotenbeutel", 0.02, "1"),
    ]},
    {"date": "2026-01-05", "total": 7.25, "items": [
        ("Kinderzahngel Erdb.", 0.50, "1"),
        ("Elmex/Aronal Duopack", 6.75, "1"),
    ]},
    {"date": "2026-01-06", "total": 15.94, "items": [
        ("Banane lose", 1.17, "0.906 kg"),
        ("Tomaten Strauch", 1.67, "0.838 kg"),
        ("Bioland Rote Bete", 1.99, "1"),
        ("Erdbeeren 250g", 4.38, "2"),
        ("Naturjoghurt Milch 3.8%", 1.98, "2"),
        ("Schmelzkäse Allgäuer", 1.69, "1"),
        ("Schmelzkäse Toast", 1.69, "1"),
        ("Vollk. Sandwi. Toast", 1.09, "1"),
        ("Knotenbeutel", 0.04, "2"),
    ]},
    {"date": "2026-01-07", "total": 9.75, "items": [
        ("Apfel rot süß", 1.00, "0.438 kg"),
        ("Bio Mini Möhren 200g", 0.99, "1"),
        ("Granatapfel", 1.19, "1"),
        ("Bio Baby Spinat", 1.29, "1"),
        ("Einzehenknoblauch", 2.29, "1"),
        ("Bauerngurken", 2.99, "1"),
    ]},
    {"date": "2026-01-08", "total": 5.88, "items": [
        ("Bio-Eier OKT 10er", 3.99, "1"),
        ("Softfrüchte Aprikose", 1.89, "1"),
    ]},
    {"date": "2026-01-10", "total": 3.42, "items": [
        ("Biol. Fruchtjoghurt Erdb.", 0.59, "1"),
        ("Bioland Naturjoghurt", 1.79, "1"),
        ("Nesquik Pudding Choc", 2.29, "1"),
        ("Holunderbeere Seife", 0.65, "1"),
        ("Pfeffer schwarz", 2.39, "1"),
    ]},
    {"date": "2026-01-13", "total": 5.68, "items": [
        ("Möhren Bioland", 0.56, "0.280 kg"),
        ("Bio Mini Möhren 200g", 0.99, "1"),
        ("Bioland Naturjoghurt", 1.79, "1"),
        ("Pistazien ungesalz.", 3.49, "1"),
    ]},
    {"date": "2026-01-15", "total": 12.46, "items": [
        ("Kartoffeln Süß", 0.56, "0.314 kg"),
        ("Banane lose", 1.10, "0.850 kg"),
        ("Zuckermais", 2.99, "1"),
        ("Bioland Naturjoghurt", 3.58, "2"),
        ("Mineralwasser still", 1.35, "1"),
        ("Mandeln Honig/Salz", 1.99, "1"),
    ]},
    {"date": "2026-01-16", "total": 10.79, "items": [
        ("Tomaten Strauch", 1.99, "0.834 kg"),
        ("Heidelbeeren", 1.49, "1"),
        ("Bio Baby Spinat", 1.29, "1"),
        ("Mandarinen", 2.79, "1"),
        ("Toilettenpapier 3lg.", 3.59, "1"),
        ("Knotenbeutel", 0.02, "1"),
    ]},
    {"date": "2026-01-21", "total": 13.94, "items": [
        ("Ananas", 1.95, "1.306 kg"),
        ("Zuckermais", 2.99, "1"),
        ("Romatomaten", 1.49, "1"),
        ("Bio-Eier OKT 10er", 7.98, "2"),
    ]},
    {"date": "2026-01-26", "total": 6.67, "items": [
        ("Mango", 1.39, "1"),
        ("Cashewkerne 200g", 2.99, "1"),
        ("Snack-Mandeln", 3.49, "1"),
    ]},
    {"date": "2026-01-28", "total": 20.97, "items": [
        ("Sonnenblumenöl raff.", 4.38, "2"),
        ("Fr.Eier a. Bodenhal.", 2.49, "1"),
        ("Heinz Ketchup", 2.79, "1"),
        ("Vegane Mayonnaise", 1.69, "1"),
        ("Rohrreiniger-Gel", 1.25, "1"),
        ("All-in 1 MGR Tabs", 5.89, "1"),
        ("Rein.tücher Meeresfr.", 1.49, "1"),
        ("Müllbeutel", 0.99, "1"),
    ]},
    {"date": "2026-01-29", "total": 4.46, "items": [
        ("Bio Blütenhonig flüssig", 2.65, "1"),
        ("Croissant Butt.", 0.98, "2"),
        ("Berliner NussN", 0.99, "1"),
    ]},
    {"date": "2026-01-30", "total": 14.70, "items": [
        ("Banane lose", 1.79, "1.384 kg"),
        ("Tomaten Strauch", 2.80, "1.126 kg"),
        ("Bioland Naturjoghurt", 1.79, "1"),
        ("Naturjoghurt mild", 0.89, "1"),
        ("Eier 18er Freilandh.", 4.19, "1"),
        ("Mineralwasser still", 1.74, "6"),
    ]},
    {"date": "2026-02-05", "total": 21.10, "items": [
        ("Banane lose", 0.79, "0.612 kg"),
        ("Ingwer", 1.39, "0.284 kg"),
        ("Kartoffeln Süß", 1.25, "0.696 kg"),
        ("Broccoli", 1.39, "1"),
        ("Zwiebeln rot", 1.58, "2"),
        ("Mozzarella gerieben", 1.79, "1"),
        ("Bioland Naturjoghurt", 3.58, "2"),
        ("Bio-Eier OKT 10er", 7.98, "2"),
    ]},
    {"date": "2026-02-05", "total": 4.81, "items": [
        ("Wasser still", 1.74, "6"),
        ("Croissant Butt.", 0.98, "2"),
        ("Donut Pinky", 0.59, "1"),
    ]},
    {"date": "2026-02-07", "total": 23.20, "items": [
        ("Barilla Girandole", 0.99, "1"),
        ("Barilla Pesto Secchi", 1.99, "1"),
        ("Paulaner Hefe-Weißb.", 3.27, "3"),
        ("Weizen-Mix Grapefru.", 0.49, "1"),
        ("Vollk. Sandwi. Toast", 1.09, "1"),
        ("Riffle Chips Paprika", 1.49, "1"),
        ("OldSpice Deo", 2.99, "1"),
        ("Hähnchenbrustfilet", 9.99, "1"),
    ]},
    {"date": "2026-02-09", "total": 8.91, "items": [
        ("Kartoffeln Süß", 1.54, "0.858 kg"),
        ("Bio Knoblauch", 1.49, "1"),
        ("Einzehenknoblauch", 2.29, "1"),
        ("Toilettenpapier 3lg.", 3.59, "1"),
    ]},
    {"date": "2026-02-10", "total": 7.23, "items": [
        ("Zuckermais", 2.99, "1"),
        ("Küchentücher 3-lagig", 2.75, "1"),
        ("Rein.tücher Meeresfr.", 1.49, "1"),
    ]},
    {"date": "2026-02-12", "total": 5.61, "items": [
        ("Wasser still", 1.74, "6"),
        ("Hot Dog Gef.Lau.", 1.98, "2"),
        ("Berliner Herz", 0.49, "1"),
    ]},
    {"date": "2026-02-13", "total": 13.54, "items": [
        ("Kartoffeln Süß", 0.89, "0.496 kg"),
        ("Tomaten Strauch", 3.34, "1.460 kg"),
        ("Bio Baby Spinat", 1.29, "1"),
        ("Naturjoghurt mild", 0.89, "1"),
        ("Eier 10er Freilandh.", 5.98, "2"),
        ("Knotenbeutel", 0.04, "2"),
    ]},
    {"date": "2026-02-17", "total": 9.72, "items": [
        ("Banane lose", 1.45, "1.124 kg"),
        ("Möhren 1kg", 1.09, "1"),
        ("RitterWürfel Dankeschön", 2.99, "1"),
        ("Hanuta Mini Fam.Pack", 4.19, "1"),
    ]},
    {"date": "2026-02-18", "total": 6.56, "items": [
        ("Bio-Eier OKT 10er", 3.99, "1"),
        ("Donut Schoko", 0.59, "1"),
        ("Croissant Wien.", 1.98, "2"),
    ]},
    {"date": "2026-02-19", "total": 3.96, "items": [
        ("Croissant Nuss", 1.38, "3"),
        ("Frikandel", 2.58, "2"),
    ]},
    {"date": "2026-02-20", "total": 6.66, "items": [
        ("Zuckermais", 2.99, "1"),
        ("Zwiebeln rot", 0.99, "1"),
        ("Bioland Naturjoghurt", 1.79, "1"),
        ("Naturjoghurt mild", 0.89, "1"),
    ]},
    {"date": "2026-02-23", "total": 16.85, "items": [
        ("Banane lose", 2.16, "1.672 kg"),
        ("Kartoffeln Süß", 3.74, "0.938 kg"),
        ("Snack Gurken", 1.69, "1"),
        ("Gurken", 1.29, "1"),
        ("Orangen", 5.49, "1"),
        ("Zitronen", 1.39, "1"),
        ("Vollk. Sandwi. Toast", 1.09, "1"),
    ]},
    {"date": "2026-02-24", "total": 15.38, "items": [
        ("Bunter Strauss Blumen", 4.99, "1"),
        ("Naturjoghurt mild", 0.89, "1"),
        ("Bioland Naturjoghurt", 1.79, "1"),
        ("Bad Reichenh. Salz", 0.75, "1"),
        ("Snack-Mandeln", 3.49, "1"),
        ("Apfel-Quark-Tasche", 1.98, "2"),
        ("Berliner Mehrfrucht", 2.29, "1"),
    ]},
    {"date": "2026-02-25", "total": 0.89, "items": [
        ("Naturjoghurt mild", 0.89, "1"),
    ]},
    {"date": "2026-02-27", "total": 2.94, "items": [
        ("Banane lose", 1.36, "1.058 kg"),
        ("Donut Pinky", 0.59, "1"),
        ("Laugen Brezel", 0.99, "1"),
    ]},
    {"date": "2026-02-28", "total": 25.53, "items": [
        ("Tomaten Strauch", 3.49, "1.460 kg"),
        ("Birnen rot lose", 1.78, "0.594 kg"),
        ("Avocado", 3.69, "1"),
        ("Dattelcherrytomaten", 2.19, "1"),
        ("Broccoli", 0.95, "1"),
        ("Rein.tücher Meeresfr.", 1.49, "1"),
        ("Knotenbeutel", 0.04, "2"),
        ("White Tiger Garnelen", 4.29, "1"),
    ]},
    {"date": "2026-03-02", "total": 10.17, "items": [
        ("Kartoffeln Süß", 0.95, "0.564 kg"),
        ("Cashewkerne 200g", 2.99, "1"),
        ("Küchentücher 3-lagig", 2.75, "1"),
        ("Toilettenpapier 3lg.", 3.59, "1"),
    ]},
    {"date": "2026-03-03", "total": 6.79, "items": [
        ("Ingwer Bio", 1.50, "0.306 kg"),
        ("Bioland Rote Bete", 1.99, "1"),
        ("Bio Mini Möhren 200g", 0.99, "1"),
        ("Bio Baby Spinat", 1.29, "1"),
        ("Bärenmarke H-Milch 3.8%", 1.90, "2"),
        ("Knotenbeutel", 0.02, "1"),
    ]},
    {"date": "2026-03-04", "total": 14.70, "items": [
        ("Banane lose", 1.09, "0.844 kg"),
        ("Zuckermais", 2.99, "1"),
        ("Bioland Naturjoghurt", 3.58, "2"),
        ("Naturjoghurt mild", 0.89, "1"),
        ("Sonnenblumenöl raff.", 4.38, "2"),
        ("Fr.Eier a. Bodenhal.", 2.49, "1"),
    ]},
    {"date": "2026-03-04", "total": 5.49, "items": [
        ("Langnese Mandel Whirl", 5.49, "1"),
    ]},
    {"date": "2026-03-05", "total": 13.28, "items": [
        ("Bio Limetten", 1.99, "1"),
        ("Bio Mini Möhren 200g", 0.99, "1"),
        ("Erdbeeren 400g", 3.99, "1"),
        ("Bauerngurken", 2.99, "1"),
        ("Bio Zitronen", 1.49, "1"),
        ("Pfeffer schwarz", 1.19, "1"),
        ("Knotenbeutel", 1.24, "62"),
    ]},
    {"date": "2026-03-05", "total": 4.16, "items": [
        ("Marillenspitz", 0.99, "1"),
        ("Frikandel", 2.58, "2"),
        ("Donut Schoko", 0.59, "1"),
    ]},
    {"date": "2026-03-06", "total": 11.71, "items": [
        ("Möhren", 1.59, "1"),
        ("Romatomaten", 1.29, "1"),
        ("Mozzarella", 0.85, "1"),
        ("Bio-Eier OKT 10er", 7.98, "2"),
    ]},
    {"date": "2026-03-07", "total": 30.99, "items": [
        ("Ananas", 2.32, "1.560 kg"),
        ("Banane lose", 1.13, "1.094 kg"),
        ("Orangen", 5.59, "1"),
        ("Mandarinen/Clau.", 3.29, "1"),
        ("Mascarpone OGT", 3.58, "2"),
        ("Mineralwasser still", 1.35, "1"),
        ("Riffle Chips Salz", 1.39, "1"),
        ("Vollk. Sandwi. Toast", 1.09, "1"),
        ("Allzwecktücher", 4.99, "1"),
        ("Knotenbeutel", 0.02, "1"),
        ("Hähnchenbrustfilet", 9.99, "1"),
    ]},
    {"date": "2026-03-09", "total": 2.22, "items": [
        ("Bio Mini Möhren 200g", 0.99, "1"),
        ("Bioland Naturjoghurt", 1.79, "1"),
    ]},
    {"date": "2026-03-10", "total": 5.99, "items": [
        ("Spargel grün", 5.99, "1"),
    ]},
    {"date": "2026-03-11", "total": 22.28, "items": [
        ("Kartoffeln Süß", 1.65, "0.752 kg"),
        ("Bio Knoblauch", 2.98, "2"),
        ("Naturjoghurt mild", 1.78, "2"),
        ("Walnusskerne XXL", 5.99, "1"),
        ("Müllbeutel", 0.99, "1"),
        ("Lachsfilet", 5.99, "1"),
    ]},
    {"date": "2026-03-12", "total": 2.57, "items": [
        ("Donut Pinky", 0.59, "1"),
        ("Hot Dog Gef.Lau.", 1.98, "2"),
    ]},
]

# ══════════════════════════════════════════════════════════════════════════════
# HIT PDF PARSER  (same logic as extract_receipts.py)
# ══════════════════════════════════════════════════════════════════════════════
HIT_SECTIONS = {
    "OBST": "OBST & GEMÜSE",
    "GEMÜSE": "OBST & GEMÜSE",
    "GETRÄNKE": "Getränke",
    "LEBENSMITTEL": "Lebensmittel",
    "GEKÜHLTE": "Gekühlte Lebensmittel",
    "TIEFKÜHL": "Tiefkühlkost",
    "FRÜHSTÜCK": "Frühstück",
    "DROGERIE": "Non-Food",
    "NON FOOD": "Non-Food",
    "PFAND": None,
    "LEERGUT": None,
}

ITEM_RE  = re.compile(r"^(.+?)\s+\(\d+\)\s+([\d,]+)\s+([AB])\*?$")
WEIGHT_RE = re.compile(r"^([\d,]+)\s+kg\s+x\s+([\d,]+)")
MULTI_RE  = re.compile(r"^(\d+)x\s+([\d,]+)\s+")


def _p(s):
    return float(s.replace(",", "."))


def parse_hit_pdf(filepath):
    fname = filepath.name
    dm = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", fname)
    if not dm:
        return None
    date = datetime(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))

    with pdfplumber.open(filepath) as pdf:
        raw = "\n".join(p.extract_text() or "" for p in pdf.pages)

    lines  = [ln.strip() for ln in raw.split("\n")]
    items  = []
    section = "Lebensmittel"
    skip    = False
    total   = 0.0
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("SUMME"):
            m = re.search(r"([\d,]+)\s*$", line)
            if m:
                total = _p(m.group(1))
            break

        sec_hit = None
        for key, sec in HIT_SECTIONS.items():
            if key in line.upper():
                sec_hit = sec
                break
        if sec_hit is not None:
            section = sec_hit
            skip = (sec_hit is None)
            i += 1
            continue

        if skip or line.startswith("***") or line.startswith("Rabatt") or not line:
            i += 1
            continue

        m = ITEM_RE.match(line)
        if m:
            name, price_str, _ = m.groups()
            price = _p(price_str)
            qty   = "1"
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if WEIGHT_RE.match(nxt):
                    qty = WEIGHT_RE.match(nxt).group(1) + " kg"
                    i += 1
                elif MULTI_RE.match(nxt):
                    qty = MULTI_RE.match(nxt).group(1)
                    i += 1
            cat, score = classify_item(name)
            if section == "OBST & GEMÜSE" and cat == "Sonstiges":
                cat, score = "Früchte", 9
            items.append({"name": name.strip(), "price": price,
                          "quantity": qty, "receipt_category": section,
                          "category": cat, "health_score": score})
        i += 1

    return {"date": date, "store": "HIT", "total": total, "items": items}


# ══════════════════════════════════════════════════════════════════════════════
# BUILD DATAFRAMES
# ══════════════════════════════════════════════════════════════════════════════
receipt_rows = []
item_rows    = []


def add_receipt(rid, date_str, store, total, items):
    receipt_rows.append({
        "receipt_id":  rid,
        "date":        date_str,
        "store":       store,
        "total":       total,
        "item_count":  len(items),
    })
    for it in items:
        item_rows.append({"receipt_id": rid, "date": date_str,
                          "store": store, **it})


# ── HIT PDFs ──────────────────────────────────────────────────────────────────
print("=== HIT receipts ===")
for pdf in sorted(HIT_DIR.glob("*.pdf")):
    data = parse_hit_pdf(pdf)
    if not data:
        continue
    dm = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", pdf.name)
    d  = datetime(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
    rid = f"HIT_{d.strftime('%Y%m%d')}_{pdf.stem}"
    print(f"  {pdf.name}: {len(data['items'])} items, total {data['total']:.2f}")
    add_receipt(rid, d.strftime("%Y-%m-%d"), "HIT", data["total"], data["items"])

# ── Lidl (hardcoded) ──────────────────────────────────────────────────────────
print("\n=== Lidl receipts ===")
lidl_date_counts = {}
for rec in LIDL_RECEIPTS:
    dt   = rec["date"]
    cnt  = lidl_date_counts.get(dt, 0)
    lidl_date_counts[dt] = cnt + 1
    suffix = f"_{cnt}" if cnt > 0 else ""
    rid  = f"Lidl_{dt.replace('-', '')}{suffix}"

    items = []
    for name, price, qty in rec["items"]:
        cat, score = classify_item(name)
        items.append({"name": name, "price": price, "quantity": str(qty),
                      "receipt_category": "Lidl", "category": cat,
                      "health_score": score})

    print(f"  {dt}{suffix}: {len(items)} items, total {rec['total']:.2f}")
    add_receipt(rid, dt, "Lidl", rec["total"], items)

# ── Lidl (new PNGs from Drive not covered by hardcoded list) ─────────────────

_LIDL_ITEM_RE    = re.compile(r"^(.+?)\s+([\d]+[,.][\d]{2})\s+[AB]\*?$")
_LIDL_WEIGHT_RE  = re.compile(r"([\d,]+)\s*kg\s*[x×]\s*([\d,]+)")
_LIDL_MULTI_RE   = re.compile(r"^(\d+)\s*[x×]\s*([\d,]+)")
_LIDL_ZU_ZAHLEN_RE = re.compile(r"(?i)zu zahlen\D+(\d+[,.]\d{2})")
_LIDL_SUMME_RE     = re.compile(r"(?i)^summe\b")
_LIDL_DATE_RE    = re.compile(r"(\d{2})\.(\d{2})\.(\d{2,4})")
_LIDL_DISCOUNT_RE = re.compile(r"(?:Preisvorteil|Rabatt|RABATT)\s+[-–]?([\d,]+)")
_LIDL_SKIP_RE    = re.compile(
    r"(?i)(pfand|leergut|summe|mwst|steuer|ust\.|geg\.|change|bonus|"
    r"karte|bar |visa|mastercard|eur\b|lidl|filiale|tel\.|www\.|^\s*$|"
    r"danke|tschüss|kassierer|kassen|transaktion)"
)


def _ocr_extract_lidl(image_path: Path, fallback_date: str) -> dict | None:
    """Extract items from a Lidl receipt PNG using Tesseract OCR (free)."""
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageOps
    except ImportError:
        print("    pip install pytesseract pillow")
        return None

    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    os.environ["TESSDATA_PREFIX"] = r"C:\Users\prasa\AppData\Local\tessdata"

    try:
        img = Image.open(image_path).convert("L")
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.SHARPEN)
        if img.width < 1200:
            scale = 1200 / img.width
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        text = pytesseract.image_to_string(img, lang="deu", config="--psm 6 --oem 3")
    except Exception as e:
        print(f"    Tesseract error: {e}")
        return None

    lines  = [ln.strip() for ln in text.splitlines()]
    items  = []
    total  = 0.0
    date   = fallback_date

    for i, line in enumerate(lines):
        dm = _LIDL_DATE_RE.search(line)
        if dm and "DATUM" in line.upper():
            try:
                day, mon, yr = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                if yr < 100: yr += 2000
                date = f"{yr:04d}-{mon:02d}-{day:02d}"
            except ValueError:
                pass
        # "zu zahlen X,XX" is the definitive total
        zu = _LIDL_ZU_ZAHLEN_RE.search(line)
        if zu:
            try: total = float(zu.group(1).replace(",", "."))
            except ValueError: pass
            continue
        # "Summe A B C" tax breakdown — grab last price on the line as fallback
        if _LIDL_SUMME_RE.search(line):
            prices = re.findall(r"\d+[,.]\d{2}", line)
            if prices and total == 0.0:
                try: total = float(prices[-1].replace(",", "."))
                except ValueError: pass
            continue
        if _LIDL_SKIP_RE.search(line):
            continue
        dm2 = _LIDL_DISCOUNT_RE.search(line)
        if dm2 and items:
            try: items[-1]["price"] = max(0.0, items[-1]["price"] - float(dm2.group(1).replace(",", ".")))
            except ValueError: pass
            continue
        m = _LIDL_ITEM_RE.match(line)
        if not m:
            continue
        name  = m.group(1).strip()
        price = float(m.group(2).replace(",", "."))
        qty   = "1"
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            wm = _LIDL_WEIGHT_RE.search(nxt)
            mm = _LIDL_MULTI_RE.match(nxt)
            if wm:   qty = f"{wm.group(1).replace(',', '.')} kg"
            elif mm: qty = mm.group(1)
        cat, score = classify_item(name)
        items.append({"name": name, "price": price, "quantity": qty,
                      "receipt_category": "Lidl", "category": cat, "health_score": score})

    if total == 0.0 and items:
        total = round(sum(it["price"] for it in items), 2)

    return {"date": date, "total": total, "items": items}


# Dates already covered by hardcoded LIDL_RECEIPTS
_lidl_covered_dates = {rec["date"] for rec in LIDL_RECEIPTS}

def _lidl_date_from_filename(name: str) -> str | None:
    """Extract YYYY-MM-DD from Lidl filenames.
    Handles both '2026.03.12_...' and '23003366842026031953708...' formats."""
    # Format 1: starts with YYYY.MM.DD
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Format 2: YYYYMMDD embedded anywhere (e.g. store_id + 20260319 + seq)
    m = re.search(r"(202[0-9])(\d{2})(\d{2})\d{3,}", name)
    if m:
        try:
            datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except ValueError:
            pass
    return None


if LIDL_DIR.exists():
    lidl_new_count = 0
    for png in sorted(LIDL_DIR.glob("*.png")):
        date_str = _lidl_date_from_filename(png.name)
        if not date_str:
            continue
        if date_str in _lidl_covered_dates:
            continue  # already in hardcoded list

        print(f"  [new] {png.name}")
        data = _ocr_extract_lidl(png, date_str)
        if not data:
            continue

        actual_date = data.get("date", date_str)
        # Deduplicate by date (handle multiple receipts on same day)
        cnt = lidl_date_counts.get(actual_date, 0)
        lidl_date_counts[actual_date] = cnt + 1
        suffix = f"_{cnt}" if cnt > 0 else ""
        rid = f"Lidl_{actual_date.replace('-', '')}{suffix}"

        items = []
        for it in data.get("items", []):
            name  = it.get("name", "").strip()
            price = float(it.get("price", 0))
            qty   = str(it.get("quantity", "1"))
            cat, score = classify_item(name)
            items.append({"name": name, "price": price, "quantity": qty,
                          "receipt_category": "Lidl", "category": cat,
                          "health_score": score})

        total = float(data.get("total", sum(i["price"] for i in items)))
        print(f"    {actual_date}{suffix}: {len(items)} items, total {total:.2f}")
        add_receipt(rid, actual_date, "Lidl", total, items)
        _lidl_covered_dates.add(actual_date)
        lidl_new_count += 1

    if lidl_new_count == 0:
        print("  No new Lidl PNGs to extract.")


# ── Restaurant receipts (PDFs + images via Claude API) ────────────────────────
print("\n=== Restaurant receipts ===")

RESTAURANT_PROMPT = """
Extract all items from this restaurant receipt. Return ONLY valid JSON:
{
  "restaurant_name": "name or Unknown",
  "date": "YYYY-MM-DD",
  "total": 0.00,
  "items": [
    {"name": "dish name", "price": 0.00, "quantity": "1"}
  ]
}
Rules: exclude service charges and tips as items (add to total only).
Prices in EUR with dot decimal. Date format YYYY-MM-DD.
"""


def _claude_extract_image(image_path: Path) -> dict | None:
    """Use Claude Haiku to extract items from a restaurant receipt image."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        img_b64 = base64.b64encode(image_path.read_bytes()).decode()
        # Detect mime type
        suffix = image_path.suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else \
               "image/png"  if suffix == ".png" else "image/jpeg"
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": mime, "data": img_b64}},
                {"type": "text", "text": RESTAURANT_PROMPT},
            ]}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        print(f"    Claude API error: {e}")
        return None


def _pdf_to_image_text(filepath: Path) -> str:
    """Render an image-only PDF page and OCR it with Tesseract (free)."""
    try:
        import pytesseract
        from PIL import ImageFilter, ImageOps
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        os.environ["TESSDATA_PREFIX"] = r"C:\Users\prasa\AppData\Local\tessdata"
        with pdfplumber.open(filepath) as pdf:
            page = pdf.pages[0]
            img = page.to_image(resolution=300).original
            img = img.convert("L")
            img = ImageOps.autocontrast(img)
            img = img.filter(ImageFilter.SHARPEN)
            return pytesseract.image_to_string(img, lang="deu", config="--psm 6")
    except Exception as e:
        print(f"    Tesseract fallback failed: {e}")
        return ""


def parse_restaurant_pdf(filepath: Path) -> dict | None:
    """Extract text from a restaurant PDF receipt.
    Falls back to Tesseract OCR if the PDF is image-only (no text layer)."""
    try:
        with pdfplumber.open(filepath) as pdf:
            raw = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return None

    # Image-only PDF — no text layer; try Tesseract OCR
    if not raw.strip():
        print(f"    No text layer found — trying Tesseract OCR...")
        raw = _pdf_to_image_text(filepath)
        if not raw.strip():
            return None

    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    # Try to find date in the text
    date = datetime.now()
    for line in lines:
        for fmt in (r"(\d{2})[./](\d{2})[./](\d{4})",
                    r"(\d{4})[./](\d{2})[./](\d{2})"):
            m = re.search(fmt, line)
            if m:
                try:
                    g = m.groups()
                    if len(g[0]) == 4:
                        date = datetime(int(g[0]), int(g[1]), int(g[2]))
                    else:
                        date = datetime(int(g[2]), int(g[1]), int(g[0]))
                    break
                except ValueError:
                    pass

    # Try to parse total — matches "Summe", "Total", "Zu zahlen", "Fälliger Betrag" etc.
    total = 0.0
    for line in reversed(lines):
        m = re.search(
            r"(?:total|gesamt|summe|zu zahlen|f[aä]lliger)[^\d]*([\d]+[.,][\d]{2})",
            line, re.IGNORECASE)
        if m:
            total = float(m.group(1).replace(",", "."))
            break
    if not total:
        # Fallback: largest price on the receipt
        amounts = []
        for line in lines:
            for m in re.finditer(r"\b(\d+[.,]\d{2})\b", line):
                try:
                    amounts.append(float(m.group(1).replace(",", ".")))
                except ValueError:
                    pass
        if amounts:
            total = max(amounts)

    # Build a single summary item for the whole bill
    return {
        "restaurant_name": filepath.stem,
        "date": date,
        "total": total,
        "items": [{"name": f"Restaurant meal ({filepath.stem})",
                   "price": total, "quantity": "1"}],
    }


# Manually verified restaurant receipts (used when parser can't extract correctly)
RESTAURANT_OVERRIDES = {
    # key = filename stem → verified data
    "Pizza Hut March26": {
        "restaurant_name": "Pizza Hut",
        "date": "2026-03-10",
        "total": 25.80,
        "items": [
            {"name": "Lunch Deal (CYO Pan S — Ananas, Paprika-Mix)", "price": 12.90, "quantity": "1"},
            {"name": "Lunch Deal (Cheese Love's Pan S)",              "price": 12.90, "quantity": "1"},
            {"name": "Pepsi 0.3L",                                    "price":  0.00, "quantity": "1"},
        ],
    },
}

if RESTAURANT_DIR.exists():
    rest_files = sorted(
        list(RESTAURANT_DIR.glob("*.pdf")) +
        list(RESTAURANT_DIR.glob("*.png")) +
        list(RESTAURANT_DIR.glob("*.jpg")) +
        list(RESTAURANT_DIR.glob("*.jpeg"))
    )

    if not rest_files:
        print("  No restaurant bills found yet.")

    rest_date_counts = {}
    for f in rest_files:
        print(f"  {f.name}")
        data = None

        # Use manually verified data if available
        if f.stem in RESTAURANT_OVERRIDES:
            data = RESTAURANT_OVERRIDES[f.stem]
            print(f"    Using verified override data")
        elif f.suffix.lower() == ".pdf":
            data = parse_restaurant_pdf(f)
        else:
            data = _claude_extract_image(f)
            # Fallback: treat whole bill as one item
            if data is None:
                dm = re.match(r"(\d{4})[._-](\d{2})[._-](\d{2})", f.name)
                fallback_date = datetime(int(dm.group(1)), int(dm.group(2)),
                                         int(dm.group(3))) if dm else datetime.now()
                data = {"restaurant_name": f.stem, "date": fallback_date,
                        "total": 0.0, "items": []}

        if not data:
            continue

        # Normalise date
        if isinstance(data.get("date"), str):
            try:
                bill_date = datetime.strptime(data["date"], "%Y-%m-%d")
            except ValueError:
                bill_date = datetime.now()
        else:
            bill_date = data.get("date", datetime.now())

        date_str = bill_date.strftime("%Y-%m-%d")
        cnt      = rest_date_counts.get(date_str, 0)
        rest_date_counts[date_str] = cnt + 1
        suffix   = f"_{cnt}" if cnt > 0 else ""
        rid      = f"Restaurant_{date_str.replace('-', '')}{suffix}"
        rname    = data.get("restaurant_name", "Restaurant")

        items = []
        for it in data.get("items", []):
            name  = it.get("name", "").strip() or f"Meal at {rname}"
            price = float(it.get("price", 0))
            qty   = str(it.get("quantity", "1"))
            # Use explicit category/score from override if provided
            if "category" in it and "health_score" in it:
                cat, score = it["category"], it["health_score"]
            else:
                cat, score = classify_item(name)
                # Prevent food ingredient keywords in dish names from
                # overriding the restaurant context (e.g. "Pizza Ananas" → Gemüse)
                if cat not in ("Zuckerhaltige Getränke", "Gesunde Getränke",
                               "Wasser", "Restaurant"):
                    cat, score = "Restaurant", 5
            items.append({"name": name, "price": price, "quantity": qty,
                          "receipt_category": rname,
                          "category": cat, "health_score": score})

        if not items and data.get("total", 0) > 0:
            items = [{"name": f"Meal at {rname}", "price": data["total"],
                      "quantity": "1", "receipt_category": rname,
                      "category": "Restaurant", "health_score": 5}]

        print(f"    {date_str}: {len(items)} items, total {data.get('total', 0):.2f}")
        add_receipt(rid, date_str, "Restaurant", data.get("total", 0), items)
else:
    print("  Restaurant bills folder not found — skipping.")

# ── Save ──────────────────────────────────────────────────────────────────────
receipts_df = (pd.DataFrame(receipt_rows)
               .drop_duplicates("receipt_id")
               .sort_values("date"))
items_df    = pd.DataFrame(item_rows).sort_values("date")

receipts_df.to_csv(RECEIPTS_CSV, index=False)
items_df.to_csv(ITEMS_CSV, index=False)

print(f"\nSaved {len(receipts_df)} receipts ({len(items_df)} items)")
print(f"  -> {RECEIPTS_CSV}")
print(f"  -> {ITEMS_CSV}")
