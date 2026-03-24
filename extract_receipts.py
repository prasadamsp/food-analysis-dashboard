"""
extract_receipts.py
───────────────────
Extracts grocery items from:
  • HIT receipts   → PDF text via pdfplumber
  • Lidl receipts  → PNG images via Claude Vision API (claude-haiku-4-5)

Outputs two CSVs to ./data/:
  receipts.csv  – one row per shopping trip
  items.csv     – one row per item

Usage:
    python extract_receipts.py
    python extract_receipts.py --force   # re-process already-extracted files
"""

import os, re, argparse
from datetime import datetime
from pathlib import Path

import pdfplumber
import pandas as pd
from food_categories import classify_item

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
HIT_DIR    = BASE_DIR / "Grocery bills" / "Hit Bills"
LIDL_DIR   = BASE_DIR / "Grocery bills" / "Lidl bills"
DATA_DIR   = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RECEIPTS_CSV = DATA_DIR / "receipts.csv"
ITEMS_CSV    = DATA_DIR / "items.csv"

# ──────────────────────────────────────────────────────────────────────────────
# HIT PDF parser
# ──────────────────────────────────────────────────────────────────────────────
# Section headers found on HIT receipts
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
    "PFAND": None,  # deposit – skip
    "LEERGUT": None,
}

ITEM_RE = re.compile(
    r"^(.+?)\s+\(\d+\)\s+([\d,]+)\s+([AB])\*?$"
)
WEIGHT_RE = re.compile(r"^([\d,]+)\s+kg\s+x\s+([\d,]+)\s+€/kg$")
MULTI_RE  = re.compile(r"^(\d+)x\s+([\d,]+)\s+€$")


def _parse_price(s: str) -> float:
    return float(s.replace(",", "."))


def parse_hit_pdf(filepath: Path) -> dict:
    fname = filepath.name
    date_m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", fname)
    if not date_m:
        return {}
    date = datetime(int(date_m.group(3)), int(date_m.group(2)), int(date_m.group(1)))

    with pdfplumber.open(filepath) as pdf:
        raw = "\n".join(p.extract_text() or "" for p in pdf.pages)

    lines = [ln.strip() for ln in raw.split("\n")]

    items = []
    current_section = "Lebensmittel"
    skip = False
    total = 0.0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect total
        if line.startswith("SUMME"):
            m = re.search(r"([\d,]+)\s*$", line)
            if m:
                total = _parse_price(m.group(1))
            break

        # Detect section header
        section_hit = None
        for key, section in HIT_SECTIONS.items():
            if key in line.upper():
                section_hit = section
                break
        if section_hit is not None:
            current_section = section_hit
            skip = (section_hit is None)
            i += 1
            continue

        if skip:
            i += 1
            continue

        # Skip discount/promotion markers
        if line.startswith("***") or line.startswith("Rabatt") or not line:
            i += 1
            continue

        # Try to match item line
        m = ITEM_RE.match(line)
        if m:
            name, price_str, _ = m.groups()
            price = _parse_price(price_str)
            qty_str = "1"

            # Look ahead for weight or multi-qty modifier
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                wm = WEIGHT_RE.match(next_line)
                mm = MULTI_RE.match(next_line)
                if wm:
                    qty_str = f"{wm.group(1)} kg"
                    i += 1
                elif mm:
                    qty_str = mm.group(1)
                    i += 1

            cat, score = classify_item(name)
            # Override category with receipt section when helpful
            if current_section == "OBST & GEMÜSE" and cat == "Sonstiges":
                cat, score = "Früchte", 9

            items.append({
                "name": name.strip(),
                "price": price,
                "quantity": qty_str,
                "receipt_category": current_section,
                "category": cat,
                "health_score": score,
            })

        i += 1

    return {"date": date, "store": "HIT", "total": total, "items": items}


# ──────────────────────────────────────────────────────────────────────────────
# Lidl image extractor via local Tesseract OCR (free, no API)
# Requires: sudo apt install tesseract-ocr tesseract-ocr-deu
#           pip install pytesseract pillow
# ──────────────────────────────────────────────────────────────────────────────

# Item line: "Banane lose             1,79 A"
_LIDL_ITEM_RE   = re.compile(r"^(.+?)\s{2,}([\d]+[,.][\d]{2})\s+[AB]\*?$")
# Weight modifier: "1,384 kg x 1,29 €/kg"
_LIDL_WEIGHT_RE = re.compile(r"([\d,]+)\s*kg\s*[x×]\s*([\d,]+)")
# Multi-qty: "2 x 3,39" or "3x 1,79"
_LIDL_MULTI_RE  = re.compile(r"^(\d+)\s*[x×]\s*([\d,]+)")
# Total line: "SUMME EUR  33,61" or "SUMME       33,61"
_LIDL_TOTAL_RE  = re.compile(r"SUMME\b.*([\d]+[,.][\d]{2})")
# Date: "02.01.2026" or "02.01.26"
_LIDL_DATE_RE   = re.compile(r"(\d{2})\.(\d{2})\.(\d{2,4})")
# Discount: "Preisvorteil" or "Rabatt"
_LIDL_DISCOUNT_RE = re.compile(r"(?:Preisvorteil|Rabatt|RABATT)\s+[-–]?([\d,]+)")
# Skip lines
_LIDL_SKIP_RE   = re.compile(
    r"(?i)(pfand|leergut|summe|mwst|steuer|ust\.|geg\.|change|bonus|"
    r"karte|bar |visa|mastercard|eur\b|lidl|filiale|tel\.|www\.|^\s*$|"
    r"danke|tschüss|kassierer|kassen|transaktion)"
)


def _parse_price(s: str) -> float:
    return float(s.replace(",", "."))


def parse_lidl_image(filepath: Path, _client=None) -> dict:
    """Extract items from a Lidl receipt PNG using local Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageOps
    except ImportError:
        raise RuntimeError(
            "pip install pytesseract pillow  and  "
            "sudo apt install tesseract-ocr tesseract-ocr-deu"
        )

    # ── Date from filename (fallback) ─────────────────────────────────────────
    fname = filepath.name
    date_m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", fname)
    fallback_date = datetime.now()
    if date_m:
        fallback_date = datetime(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)))

    # ── Preprocess image for better OCR ──────────────────────────────────────
    img = Image.open(filepath).convert("L")          # greyscale
    img = ImageOps.autocontrast(img)                 # normalise contrast
    img = img.filter(ImageFilter.SHARPEN)            # sharpen edges
    # Scale up if narrow (Tesseract likes ≥300 dpi equivalent)
    if img.width < 1200:
        scale = 1200 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)

    # ── Run OCR ──────────────────────────────────────────────────────────────
    text = pytesseract.image_to_string(
        img,
        lang="deu",
        config="--psm 6 --oem 3",   # assume uniform block of text
    )

    # ── Parse lines ──────────────────────────────────────────────────────────
    lines = [ln.strip() for ln in text.splitlines()]
    items   = []
    total   = 0.0
    date    = fallback_date
    pending_price = None   # price of last matched item (for discount look-ahead)

    for i, line in enumerate(lines):
        # Extract date from receipt body
        dm = _LIDL_DATE_RE.search(line)
        if dm and "DATUM" in line.upper():
            try:
                day, mon, yr = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                if yr < 100:
                    yr += 2000
                date = datetime(yr, mon, day)
            except ValueError:
                pass

        # Total
        tm = _LIDL_TOTAL_RE.search(line)
        if tm:
            try:
                total = _parse_price(tm.group(1))
            except ValueError:
                pass
            continue

        # Skip non-item lines
        if _LIDL_SKIP_RE.search(line):
            continue

        # Discount applied to previous item
        dm2 = _LIDL_DISCOUNT_RE.search(line)
        if dm2 and items:
            try:
                items[-1]["price"] = max(0.0, items[-1]["price"] - _parse_price(dm2.group(1)))
            except ValueError:
                pass
            continue

        # Item line
        m = _LIDL_ITEM_RE.match(line)
        if not m:
            continue
        name  = m.group(1).strip()
        price = _parse_price(m.group(2))
        qty   = "1"

        # Look ahead for weight or multi-qty on next line
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            wm = _LIDL_WEIGHT_RE.search(nxt)
            mm = _LIDL_MULTI_RE.match(nxt)
            if wm:
                qty = f"{wm.group(1).replace(',', '.')} kg"
            elif mm:
                qty = mm.group(1)

        cat, score = classify_item(name)
        items.append({
            "name": name,
            "price": price,
            "quantity": qty,
            "receipt_category": "Lidl",
            "category": cat,
            "health_score": score,
        })

    # Use sum of items as total fallback if OCR missed SUMME line
    if total == 0.0 and items:
        total = round(sum(it["price"] for it in items), 2)

    return {"date": date, "store": "Lidl", "total": total, "items": items}


# ──────────────────────────────────────────────────────────────────────────────
# Main extraction loop
# ──────────────────────────────────────────────────────────────────────────────
def load_existing_ids() -> set[str]:
    if RECEIPTS_CSV.exists():
        df = pd.read_csv(RECEIPTS_CSV)
        return set(df["receipt_id"].tolist())
    return set()


def receipt_id(store: str, date: datetime, filename: str) -> str:
    return f"{store}_{date.strftime('%Y%m%d')}_{Path(filename).stem}"


def run(force: bool = False):
    existing_ids = set() if force else load_existing_ids()

    receipt_rows = []
    item_rows    = []

    # Load existing data
    if not force and RECEIPTS_CSV.exists():
        receipt_rows = pd.read_csv(RECEIPTS_CSV).to_dict("records")
        item_rows    = pd.read_csv(ITEMS_CSV).to_dict("records")

    # ── HIT PDFs ──────────────────────────────────────────────────────────────
    print("\n=== Processing HIT receipts ===")
    for pdf_file in sorted(HIT_DIR.glob("*.pdf")):
        rid = receipt_id("HIT", datetime.now(), pdf_file.name)
        # Use date from filename for proper ID
        date_m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", pdf_file.name)
        if date_m:
            d = datetime(int(date_m.group(3)), int(date_m.group(2)), int(date_m.group(1)))
            rid = receipt_id("HIT", d, pdf_file.name)

        if rid in existing_ids:
            print(f"  SKIP {pdf_file.name} (already extracted)")
            continue

        print(f"  -> {pdf_file.name}")
        data = parse_hit_pdf(pdf_file)
        if not data or not data.get("items"):
            print(f"    WARNING: no items found")
            continue

        receipt_rows.append({
            "receipt_id": rid,
            "date": data["date"].strftime("%Y-%m-%d"),
            "store": "HIT",
            "total": data["total"],
            "item_count": len(data["items"]),
        })
        for it in data["items"]:
            item_rows.append({
                "receipt_id": rid,
                "date": data["date"].strftime("%Y-%m-%d"),
                "store": "HIT",
                **it,
            })

    # ── Lidl PNGs ─────────────────────────────────────────────────────────────
    print("\n=== Processing Lidl receipts ===")
    png_files = sorted(LIDL_DIR.glob("*.png"))
    new_lidl = [
        f for f in png_files
        if receipt_id("Lidl", datetime.strptime(
            re.match(r"(\d{4}\.\d{2}\.\d{2})", f.name).group(1), "%Y.%m.%d"
        ), f.name) not in existing_ids
    ]

    if new_lidl:
        for img_file in new_lidl:
            date_m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", img_file.name)
            d = datetime(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)))
            rid = receipt_id("Lidl", d, img_file.name)

            print(f"  -> {img_file.name}")
            try:
                data = parse_lidl_image(img_file)
            except Exception as e:
                print(f"    ERROR: {e}")
                continue

            receipt_rows.append({
                "receipt_id": rid,
                "date": data["date"].strftime("%Y-%m-%d"),
                "store": "Lidl",
                "total": data["total"],
                "item_count": len(data["items"]),
            })
            for it in data["items"]:
                item_rows.append({
                    "receipt_id": rid,
                    "date": data["date"].strftime("%Y-%m-%d"),
                    "store": "Lidl",
                    **it,
                })
    else:
        print("  All Lidl receipts already extracted.")

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    if receipt_rows:
        receipts_df = pd.DataFrame(receipt_rows)
        receipts_df["date"] = pd.to_datetime(receipts_df["date"])
        receipts_df = receipts_df.sort_values("date").drop_duplicates("receipt_id")
        receipts_df.to_csv(RECEIPTS_CSV, index=False)
        print(f"\nSaved {len(receipts_df)} receipts -> {RECEIPTS_CSV}")

    if item_rows:
        items_df = pd.DataFrame(item_rows)
        items_df["date"] = pd.to_datetime(items_df["date"])
        items_df = items_df.sort_values("date")
        items_df.to_csv(ITEMS_CSV, index=False)
        print(f"Saved {len(items_df)} items -> {ITEMS_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-process all receipts")
    args = parser.parse_args()
    run(force=args.force)
