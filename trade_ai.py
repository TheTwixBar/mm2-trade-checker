import os
from itertools import combinations
from typing import Dict, Any, List, Tuple, Optional

# ---------------- STABILITY MULTIPLIERS ----------------
# Positive = item is worth more than face value (rising/hyped)
# Negative = item is worth less than face value (dropping/underpaid)
STABILITY_MAP = {
    "Rising":        1.90,
    "Hyped":         1.60,
    "Doing Well":    1.40,
    "Overpaid For":  1.25,   # people pay over value — good to have
    "Stabilizing":   1.08,
    "Recovering":    1.07,
    "Stable":        1.00,
    "Fluctuating":   0.82,
    "Losing Hype":   0.68,
    "Underpaid For": 0.55,   # people underpay — bad to receive
    "Decreasing":    0.50,
}

# How much the stability gap matters in the final score
STABILITY_WEIGHT = 0.75

# Per-extra-item penalty on your side (bundle liquidity penalty)
BUNDLE_PENALTY_PER_ITEM = 0.03   # 3% per extra item you give

# ---------------- HELPERS ----------------
def parse_range(text: str):
    """Returns (low, high, mid) or (None, None, None)."""
    if not text or text.upper() == "N/A" or "-" not in text:
        return None, None, None
    try:
        low, high = map(int, text.split("-"))
        mid = (low + high) / 2
        return low, high, mid
    except ValueError:
        return None, None, None

def avg_stability_multiplier(stabilities: List[str]) -> float:
    if not stabilities:
        return 1.0
    return sum(STABILITY_MAP.get(s, 1.0) for s in stabilities) / len(stabilities)

def effective_base_value(item: Dict[str, Any]) -> float:
    """
    Always use range midpoint when available — not just for Fluctuating.
    This makes valuation consistent across all items that have a range.
    """
    if item.get("range_mid") is not None:
        return item["range_mid"]
    return float(item["value"])

# ---------------- LOAD ITEMS ----------------
def load_items(folder: str = "data_txt") -> Dict[str, Dict[str, Any]]:
    items: Dict[str, Dict[str, Any]] = {}

    if not os.path.exists(folder):
        print(f"Warning: Missing folder: {folder}")
        return items

    for file in os.listdir(folder):
        if not file.endswith(".txt"):
            continue
        if file.lower() == "inventory.txt":
            continue

        with open(os.path.join(folder, file), encoding="utf-8") as f:
            block: Dict[str, Any] = {}

            for line in f:
                line = line.strip()

                if line.startswith("Name:"):
                    block["name"] = line.replace("Name:", "").strip()
                elif line.startswith("Value:"):
                    val = line.replace("Value:", "").strip()
                    block["value"] = int(val) if val.isdigit() else 0
                elif line.startswith("Range:"):
                    low, high, mid = parse_range(line.replace("Range:", "").strip())
                    block["range_low"]  = low
                    block["range_high"] = high
                    block["range_mid"]  = mid
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
                        block.setdefault("value",      0)
                        block.setdefault("range_low",  None)
                        block.setdefault("range_high", None)
                        block.setdefault("range_mid",  None)
                        block.setdefault("demand",     0.0)
                        block.setdefault("rarity",     0.0)
                        block.setdefault("stability",  "Stable")
                        items[block["name"].lower()] = block
                    block = {}

    return items

def load_inventory(path: str = "data_txt/inventory.txt") -> List[str]:
    if not os.path.exists(path):
        return []
    seen = set()
    inv: List[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if not name or name.lstrip().startswith("#"):
                continue
            key = name.lower().strip()
            if key not in seen:
                seen.add(key)
                inv.append(key)
    return inv

# ---------------- SCORING ----------------
def score_item(item: Dict[str, Any]) -> Tuple[float, float, float, float, str]:
    """
    Returns (ai_score, base_value, demand, rarity, stability).

    Improvements over v1:
    - Always uses range midpoint as base when available
    - Stability penalty/bonus weighted more aggressively
    - Demand bonus scales with how much above average it is (not flat)
    - Rarity bonus applied per-tier, not flat
    """
    base = effective_base_value(item)
    stability  = item.get("stability", "Stable")
    demand     = item.get("demand", 0.0)
    rarity     = item.get("rarity", 0.0)

    stab_mult  = STABILITY_MAP.get(stability, 1.0)

    # Demand: meaningful above 3, stronger curve
    demand_bonus = max(0.0, (demand - 2.0) * 0.06)

    # Rarity: meaningful above 2, scaled per tier
    rarity_bonus = max(0.0, (rarity - 1.5) * 0.04)

    # Stability: weighted delta from neutral (1.0)
    stab_bonus = (stab_mult - 1.0) * STABILITY_WEIGHT

    bonus_multiplier = 1.0 + demand_bonus + rarity_bonus + stab_bonus

    # Wider range than v1 to let stability extremes breathe
    MIN_MULT = 0.70
    MAX_MULT = 1.60
    bonus_multiplier = max(MIN_MULT, min(bonus_multiplier, MAX_MULT))

    ai_score = base * bonus_multiplier
    return ai_score, base, demand, rarity, stability


def score_side(
    items: List[Dict[str, Any]],
    apply_bundle_penalty: bool = False
) -> Tuple[float, int, float, float, List[str]]:
    """
    Scores a full side of a trade.

    apply_bundle_penalty: if True, applies a small per-item liquidity
    penalty for every item beyond the first (you giving 4 items is worse
    than giving 1 item of the same total value).
    """
    ai_total   = 0.0
    raw_total  = 0.0
    demands:     List[float] = []
    rarities:    List[float] = []
    stabilities: List[str]   = []

    for item in items:
        ai, base, demand, rarity, stability = score_item(item)
        ai_total  += ai
        raw_total += base
        demands.append(demand)
        rarities.append(rarity)
        stabilities.append(stability)

    # Bundle penalty: each extra item beyond the first reduces total AI by 3%
    if apply_bundle_penalty and len(items) > 1:
        penalty = 1.0 - BUNDLE_PENALTY_PER_ITEM * (len(items) - 1)
        penalty = max(0.80, penalty)   # cap penalty at 20%
        ai_total *= penalty

    avg_demand = sum(demands) / len(demands) if demands else 0.0
    avg_rarity = sum(rarities) / len(rarities) if rarities else 0.0

    return ai_total, round(raw_total), avg_demand, avg_rarity, stabilities


# ---------------- TRADE EVALUATION ----------------
def evaluate_trade(
    yours: List[Dict[str, Any]],
    theirs: List[Dict[str, Any]]
) -> Dict[str, Any]:

    # Score both sides — your side gets bundle penalty, theirs does not
    # (you want to know the real cost of what you're giving up)
    y_ai, y_raw, y_dem, y_rar, y_stab = score_side(yours,  apply_bundle_penalty=True)
    t_ai, t_raw, t_dem, t_rar, t_stab = score_side(theirs, apply_bundle_penalty=False)

    raw_diff = t_raw - y_raw
    ai_diff  = t_ai  - y_ai

    # ── Percentage-based threshold ─────────────────────────────────────
    # Use total trade value so the threshold scales naturally at all price levels
    total_trade_value = max(1, y_raw + t_raw)
    pct_threshold = total_trade_value * 0.045   # 4.5% of total trade = noise

    # Minimum flat floor so tiny trades still have a sensible threshold
    flat_floor = 3.0
    threshold = max(flat_floor, pct_threshold)

    # ── Result ────────────────────────────────────────────────────────
    if abs(ai_diff) <= threshold:
        result = "fair"
    elif ai_diff > threshold:
        result = "win"
    else:
        result = "lose"

    # ── Stability tiebreaker ──────────────────────────────────────────
    # If it's fair on value, check whether their items trend better/worse
    if result == "fair":
        y_stab_avg = avg_stability_multiplier(y_stab)
        t_stab_avg = avg_stability_multiplier(t_stab)
        diff = t_stab_avg - y_stab_avg
        if diff < -0.08:
            result = "lose"
        elif diff > 0.08:
            result = "win"

    # ── Cross-category rarity check ───────────────────────────────────
    # If the result is still fair but you're giving significantly rarer items,
    # flag it as a slight loss (harder for you to retrade)
    if result == "fair":
        y_top_rarity = max((i.get("rarity", 0) for i in yours), default=0)
        t_top_rarity = max((i.get("rarity", 0) for i in theirs), default=0)
        if y_top_rarity - t_top_rarity >= 1.5:
            result = "lose"

    return {
        "result":           result,
        "your_raw":         y_raw,
        "their_raw":        t_raw,
        "raw_diff":         raw_diff,
        "your_demand":      y_dem,
        "their_demand":     t_dem,
        "demand_diff":      t_dem - y_dem,
        "your_rarity":      y_rar,
        "their_rarity":     t_rar,
        "rarity_diff":      t_rar - y_rar,
        "your_ai":          round(y_ai),
        "their_ai":         round(t_ai),
        "ai_diff":          round(ai_diff),
        "your_stability":   y_stab,
        "their_stability":  t_stab,
        "threshold":        round(threshold, 1),
        "bundle_penalty":   len(yours) > 1,
    }


# ---------------- OFFER FINDER ----------------
def find_best_offer(
    inventory_items: List[Dict[str, Any]],
    target_item: Dict[str, Any],
    max_slots: int = 4,
    min_gain_pct: float = 0.03,
    min_gain_flat: float = 5.0
) -> Optional[Tuple[List[Dict[str, Any]], float, float]]:
    if not inventory_items:
        return None

    target_ai, *_ = score_item(target_item)
    gain_margin      = max(min_gain_flat, target_ai * min_gain_pct)
    max_offer_allowed = target_ai - gain_margin

    scored_inv = [(it, score_item(it)[0]) for it in inventory_items]

    best_under = None
    best_any   = None

    for r in range(1, max_slots + 1):
        for combo in combinations(scored_inv, r):
            offer_ai     = sum(ai for _, ai in combo)
            chosen_items = [it for it, _ in combo]

            abs_diff = abs(offer_ai - target_ai)
            if best_any is None or abs_diff < best_any[0]:
                best_any = (abs_diff, offer_ai, chosen_items)

            if offer_ai <= max_offer_allowed:
                your_gain = target_ai - offer_ai
                if best_under is None or your_gain < best_under[0]:
                    best_under = (your_gain, offer_ai, chosen_items)

    chosen = best_under if best_under is not None else best_any
    if chosen is None:
        return None

    if chosen is best_under:
        your_gain, offer_ai, items = best_under
        return items, offer_ai, your_gain

    _, offer_ai, items = best_any
    your_gain = target_ai - offer_ai
    return items, offer_ai, your_gain


# ---------------- OUTPUT ----------------
def explain(r: Dict[str, Any]) -> str:
    result_label = {
        "win":  "WIN  ✅",
        "lose": "LOSE ❌",
        "fair": "FAIR ➖",
    }.get(r["result"], r["result"].upper())

    lines = [
        f"Result: {result_label}",
        "",
        "── MM2 Value ──────────────────────────",
        f"  You:  {r['your_raw']}",
        f"  Them: {r['their_raw']}  ({r['raw_diff']:+})",
        "",
        "── AI Score ───────────────────────────",
        f"  You:  {r['your_ai']}",
        f"  Them: {r['their_ai']}  ({r['ai_diff']:+})",
        f"  Fair zone: ±{r['threshold']}",
    ]

    if r.get("bundle_penalty"):
        lines.append("  ⚠️  Bundle penalty applied to your side")

    lines += [
        "",
        "── Demand & Rarity ────────────────────",
        f"  Demand:  You {r['your_demand']:.1f} | Them {r['their_demand']:.1f}  ({r['demand_diff']:+.1f})",
        f"  Rarity:  You {r['your_rarity']:.1f} | Them {r['their_rarity']:.1f}  ({r['rarity_diff']:+.1f})",
        "",
        "── Stability ──────────────────────────",
        f"  You:  {', '.join(r['your_stability'])}",
        f"  Them: {', '.join(r['their_stability'])}",
    ]

    # Highlight dangerous stabilities
    danger = {"Underpaid For", "Decreasing", "Losing Hype", "Fluctuating"}
    your_danger  = [s for s in r["your_stability"]  if s in danger]
    their_danger = [s for s in r["their_stability"] if s in danger]

    if their_danger:
        lines.append(f"  ⚠️  You'd receive: {', '.join(their_danger)}")
    if your_danger:
        lines.append(f"  ⚠️  You'd give:    {', '.join(your_danger)}")

    return "\n".join(lines)


# ---------------- INTERACTIVE MODE ----------------
if __name__ == "__main__":
    db = load_items()

    print("=" * 45)
    print("        MM2 Trade Checker  v2")
    print("=" * 45)
    print("Separate items with a comma and space.")
    print("Example: turkey, evergun")
    print("Type 'quit' at any time to exit.\n")

    while True:
        yours_input = input("Your items:  ").strip()
        if yours_input.lower() == "quit":
            break

        theirs_input = input("Their items: ").strip()
        if theirs_input.lower() == "quit":
            break

        yours_items  = []
        theirs_items = []
        missing      = []

        for name in [n.strip().lower() for n in yours_input.split(",") if n.strip()]:
            if name in db:
                yours_items.append(db[name])
            else:
                missing.append(f"yours  -> '{name}'")

        for name in [n.strip().lower() for n in theirs_input.split(",") if n.strip()]:
            if name in db:
                theirs_items.append(db[name])
            else:
                missing.append(f"theirs -> '{name}'")

        if missing:
            print("\n❌ Unknown items (check spelling):")
            for m in missing:
                print(f"   {m}")
            print()
            continue

        if not yours_items or not theirs_items:
            print("\n❌ Please enter at least one item on each side.\n")
            continue

        result = evaluate_trade(yours_items, theirs_items)
        print("\n" + "=" * 45)
        print(explain(result))
        print("=" * 45 + "\n")
