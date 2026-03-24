from flask import Flask, request, jsonify, render_template
from trade_ai import load_items, evaluate_trade, explain, score_item

app = Flask(__name__)
db = load_items()

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

    result = evaluate_trade(yours_items, theirs_items)
    return jsonify({
        "result":          result["result"],
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

@app.route("/api/stats", methods=["GET"])
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

@app.route("/api/items", methods=["GET"])
def api_items():
    return jsonify(sorted(db.keys()))

if __name__ == "__main__":
    app.run(debug=False)
