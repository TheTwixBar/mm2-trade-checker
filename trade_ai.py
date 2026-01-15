import os

# ---------------- STABILITY MULTIPLIERS ----------------
STABILITY_MAP = {
    "Rising": 1.5,
    "Hyped": 1.3,
    "Overpaid For": 1.2,
    "Doing Well": 1.18,
    "Stabilizing": 1.08,
    "Stable": 1,
    "Fluctuating": 0.87,
    "Losing Hype": 0.70,
    "Underpaid For": 0.60,
    "Decreasing": 0.50
}

WEIGHTS = {
    "value": 1.5,
    "demand": 0.85,
    "rarity": 0.3
}

AI_SCALE = 0.2
AI_THRESHOLD = 30

# ---------------- HELPERS ----------------
def normalize_value(value):
    return value * 100 if value < 500 else value

def parse_range(text):
    if not text or text.upper() == "N/A" or "-" not in text:
        return None
    try:
        low, high = map(int, text.split("-"))
        return (low + high) / 2
    except ValueError:
        return None

def avg_stability_multiplier(stabilities):
    if not stabilities:
        return 0
    return sum(STABILITY_MAP.get(s, 1) for s in stabilities) / len(stabilities)

# ---------------- LOAD ITEMS ----------------
def load_items(folder="data_txt"):
    items = {}

    if not os.path.exists(folder):
        print(f"⚠️ Missing folder: {folder}")
        return items

    for file in os.listdir(folder):
        if not file.endswith(".txt"):
            continue

        with open(os.path.join(folder, file), encoding="utf-8") as f:
            block = {}
            for line in f:
                line = line.strip()
                if line.startswith("Name:"):
                    block["name"] = line.replace("Name:", "").strip()
                elif line.startswith("Value:"):
                    val = line.replace("Value:", "").strip()
                    block["value"] = int(val) if val.isdigit() else 0
                elif line.startswith("Range:"):
                    block["range_mid"] = parse_range(line.replace("Range:", "").strip())
                elif line.startswith("Demand:"):
                    try:
                        block["demand"] = float(line.replace("Demand:", "").strip())
                    except ValueError:
                        block["demand"] = 0.0
                elif line.startswith("Rarity:"):
                    try:
                        block["rarity"] = float(line.replace("Rarity:", "").strip())
                    except ValueError:
                        block["rarity"] = 0.0
                elif line.startswith("Stability:"):
                    block["stability"] = line.replace("Stability:", "").strip().title()
                elif line.startswith("-"):
                    if "name" in block:
                        block.setdefault("value", 0)
                        block.setdefault("range_mid", None)
                        block.setdefault("demand", 0.0)
                        block.setdefault("rarity", 0.0)
                        block.setdefault("stability", "Stable")
                        items[block["name"].lower()] = block
                    block = {}
    return items

# ---------------- SCORING ----------------
def score_item(item):
    raw_value = item["value"]
    if item["stability"] == "Fluctuating" and item["range_mid"] is not None:
        adjusted_raw = item["range_mid"]
    else:
        adjusted_raw = raw_value

    base_value = item["range_mid"] if item["range_mid"] is not None else adjusted_raw
    base_value_scaled = normalize_value(base_value)
    stability_mult = STABILITY_MAP.get(item["stability"], 0.9)

    value_score = base_value_scaled * WEIGHTS["value"]
    demand_score = item["demand"] * 1000 * WEIGHTS["demand"]
    rarity_score = item["rarity"] * 800 * WEIGHTS["rarity"]

    ai_score = ((value_score + demand_score + rarity_score) * stability_mult) * AI_SCALE
    return ai_score, adjusted_raw, item["demand"], item["rarity"], item["stability"]

def score_side(items):
    ai_total = 0
    raw_total = 0
    demands = []
    rarities = []
    stabilities = []

    for item in items:
        ai, raw, demand, rarity, stability = score_item(item)
        ai_total += ai
        raw_total += raw
        demands.append(demand)
        rarities.append(rarity)
        stabilities.append(stability)

    avg_demand = sum(demands) / len(demands) if demands else 0
    avg_rarity = sum(rarities) / len(rarities) if rarities else 0
    return ai_total, round(raw_total), avg_demand, avg_rarity, stabilities

# ---------------- GET ITEMS ----------------
def get_items(prompt, db):
    while True:
        names = [n.strip().lower() for n in input(prompt).split(",")]
        items = []
        missing = []
        for name in names:
            if name in db:
                items.append(db[name])
            else:
                missing.append(name)
        if missing:
            print(f"❌ Unknown items: {', '.join(missing)}\n")
        else:
            return items

# ---------------- TRADE EVALUATION ----------------
def evaluate_trade(yours, theirs):
    y_ai, y_raw, y_dem, y_rar, y_stab = score_side(yours)
    t_ai, t_raw, t_dem, t_rar, t_stab = score_side(theirs)

    raw_diff = t_raw - y_raw
    ai_diff = t_ai - y_ai

    if abs(raw_diff) <= 1:
        result = "fair"
    elif ai_diff > AI_THRESHOLD:
        result = "win"
    elif ai_diff < -AI_THRESHOLD:
        result = "lose"
    else:
        result = "fair"

    # ---- FAIR → LOSE if stability goes down ----
    if result == "fair":
        if avg_stability_multiplier(t_stab) < avg_stability_multiplier(y_stab):
            result = "lose"

    return {
        "result": result,
        "your_raw": y_raw,
        "their_raw": t_raw,
        "raw_diff": raw_diff,
        "your_demand": y_dem,
        "their_demand": t_dem,
        "demand_diff": t_dem - y_dem,
        "your_rarity": y_rar,
        "their_rarity": t_rar,
        "rarity_diff": t_rar - y_rar,
        "your_ai": round(y_ai),
        "their_ai": round(t_ai),
        "ai_diff": round(ai_diff),
        "your_stability": y_stab,
        "their_stability": t_stab
    }

# ---------------- OUTPUT ----------------
def explain(r):
    lines = [
        f"Result: {r['result'].upper()}",
        "",
        "Raw MM2 Value:",
        f"You: {r['your_raw']} | Them: {r['their_raw']} ({r['raw_diff']:+})",
        "",
        "Demand & Rarity:",
        f"Demand: You {r['your_demand']:.2f} | Them {r['their_demand']:.2f} ({r['demand_diff']:+.2f})",
        f"Rarity: You {r['your_rarity']:.2f} | Them {r['their_rarity']:.2f} ({r['rarity_diff']:+.2f})",
        "",
        "AI Score:",
        f"You: {r['your_ai']} | Them: {r['their_ai']} ({r['ai_diff']:+})",
        "",
        "Stability Summary:",
        f"{', '.join(r['your_stability'])} -> {', '.join(r['their_stability'])}"
    ]

    if "Fluctuating" in r["your_stability"] or "Fluctuating" in r["their_stability"]:
        lines.append("")
        lines.append(
            "⚠️ Fluctuating items use the average of their value range "
            "for raw MM2 value calculations."
        )

    return "\n".join(lines)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("MM2 AI Trade Checker\n")

    db = load_items()
    if not db:
        print("⚠️ No items loaded. Make sure 'data_txt' folder exists and contains .txt files.")
        exit()

    print(f"Loaded {len(db)} items\n")

    yours = get_items("Enter YOUR items (comma separated): ", db)
    theirs = get_items("Enter THEIR items (comma separated): ", db)

    result = evaluate_trade(yours, theirs)
    print("\n" + explain(result))
