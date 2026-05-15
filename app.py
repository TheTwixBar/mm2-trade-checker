import json
import os
from flask import Flask, request, jsonify, render_template
from trade_ai import load_items, evaluate_trade, explain, score_item, find_best_offer, find_top_offers
from ml_model import ml_evaluate_trade

app = Flask(__name__)
db = load_items()

INVENTORY_FILE = "data_txt/inventory.json"

# Untradeable item prefixes — never show in autocomplete
UNTRADEABLE_PREFIXES = ("gold ", "silver ", "bronze ", "red ", "blue ", "purple ")

def is_untradeable(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(p) for p in UNTRADEABLE_PREFIXES)

def tradeable_items():
    return sorted(k for k in db.keys() if not is_untradeable(k))


# ── Inventory persistence ────────────────────────────────────────────────────
def load_inventory_json():
    if not os.path.exists(INVENTORY_FILE):
        return []
    try:
        with open(INVENTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_inventory_json(items: list):
    os.makedirs(os.path.dirname(INVENTORY_FILE), exist_ok=True)
    with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f)


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/trade", methods=["POST"])
def api_trade():
    data = request.get_json()
    yours_names  = [n.strip().lower() for n in data.get("yours",  "").split(",") if n.strip()]
    theirs_names = [n.strip().lower() for n in data.get("theirs", "").split(",") if n.strip()]

    missing = []
    yours_items  = []
    theirs_items = []

    for n in yours_names:
        if n in db: yours_items.append(db[n])
        else: missing.append(f"yours: '{n}'")

    for n in theirs_names:
        if n in db: theirs_items.append(db[n])
        else: missing.append(f"theirs: '{n}'")

    if missing:
        return jsonify({"error": "Unknown items: " + ", ".join(missing)}), 400
    if not yours_items or not theirs_items:
        return jsonify({"error": "Please enter at least one item on each side."}), 400

    result = ml_evaluate_trade(yours_items, theirs_items)
    return jsonify({
        "result":          result["result"],
        "confidence":      result.get("confidence", ""),
        "your_raw":        result["your_raw"],
        "their_raw":       result["their_raw"],
        "raw_diff":        result["raw_diff"],
        "your_ai":         result["your_ai"],
        "their_ai":        result["their_ai"],
        "ai_diff":         result["ai_diff"],
        "threshold":       result["threshold"],
        "your_demand":     round(result["your_demand"],  1),
        "their_demand":    round(result["their_demand"], 1),
        "demand_diff":     round(result["demand_diff"],  1),
        "your_rarity":     round(result["your_rarity"],  1),
        "their_rarity":    round(result["their_rarity"], 1),
        "rarity_diff":     round(result["rarity_diff"],  1),
        "your_stability":  result["your_stability"],
        "their_stability": result["their_stability"],
        "bundle_penalty":  result["bundle_penalty"],
    })


@app.route("/stats", methods=["GET"])
def api_stats():
    name = request.args.get("item", "").strip().lower()
    if name not in db:
        return jsonify({"error": f"Unknown item: '{name}'"}), 404

    item = db[name]
    range_text = "N/A"
    if item.get("range_low") is not None and item.get("range_high") is not None:
        range_text = f"{item['range_low']} - {item['range_high']}"

    ai_score, *_ = score_item(item)
    return jsonify({
        "name":      item["name"],
        "value":     item["value"],
        "range":     range_text,
        "demand":    item["demand"],
        "rarity":    item["rarity"],
        "stability": item["stability"],
        "ai_score":  round(ai_score),
    })


@app.route("/items", methods=["GET"])
def api_items():
    """Only tradeable items — no gold/silver/bronze/red/blue/purple variants."""
    return jsonify(tradeable_items())


# ── Inventory endpoints ───────────────────────────────────────────────────────
@app.route("/inventory", methods=["GET"])
def get_inventory():
    return jsonify(load_inventory_json())


@app.route("/inventory", methods=["POST"])
def set_inventory():
    data = request.get_json()
    items = data.get("items", [])
    if not isinstance(items, list):
        return jsonify({"error": "items must be a list"}), 400

    clean = []
    unknown = []
    for name in items:
        key = name.strip().lower()
        if key in db:
            clean.append(key)
        else:
            unknown.append(key)

    if unknown:
        return jsonify({"error": "Unknown items: " + ", ".join(unknown)}), 400

    save_inventory_json(clean)
    return jsonify({"saved": clean})


# ── Offer suggester ───────────────────────────────────────────────────────────
@app.route("/suggest-offer", methods=["POST"])
def suggest_offer():
    data = request.get_json()

    # Support both single target (legacy) and multiple targets (expanded flat list)
    raw_targets = data.get("targets") or []
    if not raw_targets:
        single = data.get("target", "").strip().lower()
        if single:
            raw_targets = [single]

    target_names = [t.strip().lower() for t in raw_targets if isinstance(t, str) and t.strip()]

    if not target_names:
        return jsonify({"error": "No target item provided."}), 400

    unknown = [n for n in target_names if n not in db]
    if unknown:
        return jsonify({"error": f"Unknown item: '{unknown[0]}'"}), 404

    # Accept inventory from request body first (sent by JS with qty expansion),
    # fall back to server-saved file if not provided
    req_inventory = data.get("inventory")
    if req_inventory and isinstance(req_inventory, list):
        inventory_keys = [n.strip().lower() for n in req_inventory if isinstance(n, str)]
    else:
        inventory_keys = load_inventory_json()

    if not inventory_keys:
        return jsonify({"error": "Your inventory is empty. Add items on the Inventory tab first."}), 400

    target_items = [db[n] for n in target_names]
    inventory_items = [db[k] for k in inventory_keys if k in db]

    min_gain_pct = float(data.get("min_gain_pct", 0.05))

    try:
        alternatives = find_top_offers(
            inventory_items,
            target_items,
            max_slots=4,
            min_gain_pct=min_gain_pct,
            min_gain_flat=5.0,
            top_n=3,
        )
    except Exception as e:
        return jsonify({"error": f"Offer generation failed: {str(e)}"}), 500

    if not alternatives:
        return jsonify({"error": "Could not find a suitable offer from your inventory."}), 400

    target_ai_total  = sum(score_item(t)[0] for t in target_items)
    target_raw_total = sum(t.get("value", 0) for t in target_items)

    alt_list = []
    for offer_items, offer_ai, your_gain in alternatives:
        trade_result = evaluate_trade(offer_items, target_items)
        alt_list.append({
            "offer_items": [item["name"] for item in offer_items],
            "offer_ai":    round(offer_ai),
            "offer_raw":   sum(item.get("value", 0) for item in offer_items),
            "your_gain":   round(your_gain),
            "verdict":     trade_result["result"],
            "ai_diff":     trade_result["ai_diff"],
        })

    return jsonify({
        "alternatives":  alt_list,
        "target_name":   target_items[0]["name"],
        "target_names":  [t["name"] for t in target_items],
        "target_ai":     round(target_ai_total),
        "target_raw":    target_raw_total,
    })


# ── Inventory value summary ───────────────────────────────────────────────────
@app.route("/inventory/summary", methods=["POST"])
def inventory_summary():
    data = request.get_json()
    items_flat = data.get("items", [])
    if not items_flat:
        return jsonify({"error": "No items provided."}), 400

    total_ai  = 0
    total_raw = 0
    for name in items_flat:
        key = name.strip().lower()
        if key in db:
            ai, *_ = score_item(db[key])
            total_ai  += ai
            total_raw += db[key].get("value", 0)

    return jsonify({
        "total_items": len(items_flat),
        "total_ai":    round(total_ai),
        "total_raw":   total_raw,
    })



if __name__ == "__main__":
    app.run(debug=False)
