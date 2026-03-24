"""
German grocery item categorization and health scoring.
Health scores: 1 (unhealthy) to 10 (very healthy). 0 = non-food (excluded).
"""

CATEGORIES = {
    # ── Fruits ───────────────────────────────────────────────────────────────
    "Früchte": {
        "score": 9,
        "color": "#4CAF50",
        "keywords": [
            "banane", "apfel", "birne", "orange", "mandarine", "zitrone",
            "limette", "grapefruit", "traube", "erdbeere", "heidelbeere",
            "himbeere", "johannisbeere", "blaubeere", "kirsche", "pflaume",
            "pfirsich", "aprikose", "mango", "papaya", "ananas", "kiwi",
            "melone", "wassermelone", "granatapfel", "litschi", "dattel",
            "avocado", "kokosnuss", "trinkkokosnuss", "feige", "brombeere",
            "cranberry", "maracuja", "drachenfrucht", "rambutan", "physalis",
            "nektarine", "clementine", "pomelo", "kumquat", "saftorangen",
            "gourmet orangen", "orangen", "softfrüchte", "traub hell",
            "mandarinen", "birnen rot",
        ],
    },
    # ── Vegetables ───────────────────────────────────────────────────────────
    "Gemüse": {
        "score": 9,
        "color": "#8BC34A",
        "keywords": [
            "tomate", "gurke", "paprika", "salat", "spinat", "brokkoli",
            "broccoli", "blumenkohl", "karotte", "möhre", "möhren",
            "zwiebel", "knoblauch", "ingwer", "koriander", "petersilie",
            "zucchini", "aubergine", "kürbis", "mais", "zuckermais",
            "kartoffel", "rote bete", "rucola", "feldsalat", "lauch",
            "sellerie", "fenchel", "kohlrabi", "kohl", "rosenkohl",
            "pak choi", "shiitake", "champignon", "pilz", "erbse",
            "mini-paprika", "kart.", "strauchtomaten", "chicoree",
            "artischocke", "spargel", "dattelcherrytomat", "romatomaten",
            "bauerngurken", "snack gurken", "limetten", "bio limett",
        ],
    },
    # ── Legumes / Nuts ───────────────────────────────────────────────────────
    "Hülsenfrüchte & Nüsse": {
        "score": 8,
        "color": "#CDDC39",
        "keywords": [
            "linsen", "kichererbsen", "mandeln", "walnuss", "walnusskerne",
            "cashew", "cashewkerne", "pistazien", "haselnuss", "erdnuss",
            "nüsse", "nuss", "soft-pflaumen", "mandeln honig", "nüsse salz",
            "snack-mandeln",
        ],
    },
    # ── Eggs ─────────────────────────────────────────────────────────────────
    "Eier": {
        "score": 8,
        "color": "#FFF176",
        "keywords": ["eier", "bio-eier", "ei "],
    },
    # ── Fish & Seafood ───────────────────────────────────────────────────────
    "Fisch & Meeresfrüchte": {
        "score": 8,
        "color": "#4FC3F7",
        "keywords": [
            "lachs", "thunfisch", "forelle", "hering", "makrele",
            "garnelen", "eismeergarnelen", "fisch", "krabben", "shrimp",
            "kabeljau", "sardine", "meeresfrüchte",
        ],
    },
    # ── Dairy ────────────────────────────────────────────────────────────────
    "Milchprodukte": {
        "score": 6,
        "color": "#E1F5FE",
        "keywords": [
            "milch", "käse", "joghurt", "quark", "butter", "sahne",
            "rahm", "emmentaler", "gouda", "mozzarella", "frischkäse",
            "schmand", "kefir", "skyr", "bärenmilch", "bärenm",
            "meggle", "kerrygold", "kerry gold", "weidemilch", "cappino",
            "weidemel", "weidem", "mascarpone", "schmelzkäse",
            "naturjoghurt", "bioland naturjogh", "h-milch", "h-mil",
            "bärenmarke",
        ],
    },
    # ── Meat & Poultry ───────────────────────────────────────────────────────
    "Fleisch & Geflügel": {
        "score": 6,
        "color": "#FFCDD2",
        "keywords": [
            "fleisch", "hähnchen", "hähnchenbrustfilet", "huhn", "rind",
            "schwein", "schinken", "salami", "wurst", "bratwurst",
            "hackfleisch", "schnitzel", "filet", "chicken", "turkey",
            "pute", "lamm", "frikandel", "hot dog",
        ],
    },
    # ── Water ────────────────────────────────────────────────────────────────
    "Wasser": {
        "score": 9,
        "color": "#B3E5FC",
        "keywords": [
            "mineralwasser", "stilles wasser", "miwa still", "miwa",
            "wasser still", "water", "ja! miwa", "rewe miwa",
        ],
    },
    # ── Healthy Beverages ────────────────────────────────────────────────────
    "Gesunde Getränke": {
        "score": 7,
        "color": "#81D4FA",
        "keywords": [
            "granatapfelsaft", "rote-bete-saft", "rote bete saft",
            "aln.rot.bete", "smoothie", "bio saft", "direktsaft",
            "orangensaft", "apfelsaft", "gemüsesaft",
        ],
    },
    # ── Grains & Bread ───────────────────────────────────────────────────────
    "Brot & Getreide": {
        "score": 6,
        "color": "#FFE082",
        "keywords": [
            "brot", "brötchen", "vollkorn", "müsli", "haferflocken",
            "cornflakes", "toast", "bagel", "brioche", "hamburger br",
            "butcher", "semmel", "weizenmehl",
        ],
    },
    # ── Processed Food ───────────────────────────────────────────────────────
    "Fertiggerichte & Saucen": {
        "score": 4,
        "color": "#FFAB40",
        "keywords": [
            "knorr", "maggi", "fertig", "cappelletti", "suppe",
            "fix", "sauce", "tomaten basil", "knorr fix", "knorr supp",
            "knorr feinschm", "rewe bio cappell", "cappell",
            "barilla", "pesto", "ketchup", "mayonnaise", "sonnenblumenöl",
            "jodsalz", "bad reichenh", "pfeffer schwarz", "pfeffer",
            "honig", "bio blütenh", "rewe brauner",
        ],
    },
    # ── Sugary Beverages ─────────────────────────────────────────────────────
    "Zuckerhaltige Getränke": {
        "score": 3,
        "color": "#FFB74D",
        "keywords": [
            "capri-sun", "cola", "fanta", "sprite", "limonade",
            "hella erdbeere", "hella ", "eistee", "energydrink",
            "energy drink", "red bull", "paulaner", "weißbier", "bier",
            "weizen-mix", "saft erdb", "pepsi", "coca-cola", "7up",
        ],
    },
    # ── Snacks ───────────────────────────────────────────────────────────────
    "Snacks & Chips": {
        "score": 3,
        "color": "#FF8A65",
        "keywords": [
            "chips", "riffelchips", "popcorn", "cracker", "nachos",
            "flips", "student", "maryland snack", "maryland student",
        ],
    },
    # ── Sweets ───────────────────────────────────────────────────────────────
    "Süßigkeiten & Desserts": {
        "score": 2,
        "color": "#F06292",
        "keywords": [
            "oreo", "schokolade", "keks", "gebäck", "kuchen", "torte",
            "eiscreme", "eis ", "berliner", "mikado", "gummibärchen",
            "fruchtaufstrich", "glückfrucht", "nutella", "riegel",
            "bonbon", "lutscher", "waffel", "brownie", "remix brownie",
            "ja! eiscreme", "ja! 12x28", "miniteig",
            "donut", "croissant", "laugen brezel", "brezel", "rewe beste wahl mik",
            "ritter", "ritterwürfel", "hanuta", "langnese",
            "nesquik", "pudding", "berliner nuss", "berliner herz",
            "berliner mehrfrucht", "berliner m.", "apfel-quark",
            "marillenspitz", "frikandell",
        ],
    },
    # ── Restaurant meals ─────────────────────────────────────────────────────
    "Restaurant": {
        "score": 5,
        "color": "#CE93D8",
        "keywords": [
            "restaurant", "meal at", "café", "cafe", "pizza", "pasta",
            "burger", "sushi", "kebab", "döner", "schnitzel restaurant",
            "takeaway", "delivery", "bistro", "imbiss",
            "lunch deal", "pan s", "cheese love", "cyo pan",
        ],
    },
    # ── Non-Food ─────────────────────────────────────────────────────────────
    "Non-Food": {
        "score": 0,
        "color": "#B0BEC5",
        "keywords": [
            "spülmittel", "pril", "waschmittel", "shampoo", "duschgel",
            "zahnbürste", "zahnpasta", "q-tips", "wattest", "putzmi",
            "allzweck", "schwamm", "müllbeutel", "knotenbeutel",
            "küchentuch", "küchentücher", "toilettenpapier", "windeln",
            "seife", "drogerie", "elmex", "aronal", "kinderzahngel",
            "rein.tücher", "allzwecktüch", "rohrreiniger", "mgr tabs",
            "old spice", "oldspice", "deo", "pfand", "leergut",
            "holunderbeere seife", "strauss blumen", "blumen",
            "schlaufentra",
        ],
    },
}

# Flat keyword → (category, score) lookup for fast matching
_KEYWORD_MAP: dict[str, tuple[str, int]] = {}
for cat_name, cat_data in CATEGORIES.items():
    for kw in cat_data["keywords"]:
        _KEYWORD_MAP[kw.lower()] = (cat_name, cat_data["score"])


def classify_item(item_name: str) -> tuple[str, int]:
    """Return (category, health_score) for a German grocery item name."""
    name_lower = item_name.lower()
    best_match: tuple[str, int] | None = None
    best_len = 0
    for kw, (cat, score) in _KEYWORD_MAP.items():
        if kw in name_lower and len(kw) > best_len:
            best_match = (cat, score)
            best_len = len(kw)
    if best_match:
        return best_match
    return ("Sonstiges", 5)  # Unknown → neutral score


HEALTH_LABELS = {
    (8, 10): ("Sehr gesund", "#2E7D32"),
    (6, 7):  ("Gesund", "#558B2F"),
    (4, 5):  ("Mäßig", "#F57F17"),
    (2, 3):  ("Ungesund", "#E65100"),
    (0, 1):  ("Non-Food", "#546E7A"),
}


def health_label(score: int) -> tuple[str, str]:
    """Return (label, color) for a health score."""
    for (lo, hi), (label, color) in HEALTH_LABELS.items():
        if lo <= score <= hi:
            return label, color
    return ("Unbekannt", "#9E9E9E")
