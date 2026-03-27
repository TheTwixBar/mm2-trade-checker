import os
import math
from itertools import combinations
from typing import Dict, Any, List, Tuple, Optional

# ════════════════════════════════════════════════════════════════
# trade_ai.py  v3
# Based on your updated file — v3 improvements added on top:
#   1. Log-scaled demand/rarity bonuses (realistic curve, not flat linear)
#   2. Demand × Rarity interaction term (both high = extra bonus)
#   3. Value-tier liquidity modifier (low-value items penalised for being hard to move)
#   4. Smart bundle penalty (scales with how low-value the bundle is)
#   5. Threshold cap at ±400 (prevents godly trades having a massive blind zone)
#   6. N/A stability treated as mildly negative, not neutral
#   7. Confidence output (razor / clear / decisive / dominant)
# ════════════════════════════════════════════════════════════════

# ---------------- STABILITY MULTIPLIERS ----------------
STABILITY_MAP = {
    "Rising":        1.90,
    "Hyped":         1.60,
    "Doing Well":    1.40,
    "Overpaid For":  1.25,
    "Stabilizing":   1.08,
    "Recovering":    1.07,
    "Stable":        1.00,
    "N/A":           0.90,   # unknown — slight penalty
    "Fluctuating":   0.82,
    "Losing Hype":   0.68,
    "Underpaid For": 0.55,
    "Decreasing":    0.50,
}

STABILITY_WEIGHT = 0.75
BUNDLE_PENALTY_PER_ITEM = 0.03  # kept for legacy compat, v3 uses smart version

# Liquidity tiers: items worth less are harder to trade away
LIQUIDITY_TIERS = [
    (1000, 0.00),
    (200,  0.04),
    (50,   0.10),
    (0,    0.18),
]

# ---------------- HELPERS ----------------
def parse_range(text: str):
    if not text or text.upper() == "N/A" or "-" not in text:
        return None, None, None
    try:
        low, high = map(int, text.split("-"))
        return low, high, (low + high) / 2
    except ValueError:
        return None, None, None

def avg_stability_multiplier(stabilities: List[str]) -> float:
    if not stabilities:
        return 1.0
    return sum(STABILITY_MAP.get(s, 1.0) for s in stabilities) / len(stabilities)

def effective_base_value(item: Dict[str, Any]) -> float:
    if item.get("range_mid") is not None:
        return item["range_mid"]
    return float(item["value"])

def liquidity_penalty(value: float) -> float:
    for threshold, penalty in LIQUIDITY_TIERS:
        if value >= threshold:
            return penalty
    return 0.18

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

# ---------------- SCORING v3 ----------------
def score_item(item: Dict[str, Any]) -> Tuple[float, float, float, float, str]:
    """
    Returns (ai_score, base_value, demand, rarity, stability).

    v3 scoring:
    - Log-scaled demand/rarity (realistic curve, not flat linear)
    - Demand × Rarity interaction bonus for elite items
    - Value-tier liquidity penalty
    """
    base      = effective_base_value(item)
    stability = item.get("stability", "Stable")
    demand    = item.get("demand", 0.0)
    rarity    = item.get("rarity", 0.0)
    stab_mult = STABILITY_MAP.get(stability, 1.0)

    # Log-scaled demand bonus — normalised so demand=5 ≈ +18% (same as v2 baseline)
    demand_bonus = max(0.0, math.log2(demand + 1) * 0.0696 - 0.0696)

    # Log-scaled rarity bonus — normalised so rarity=4 ≈ +10% (same as v2 baseline)
    rarity_bonus = max(0.0, math.log2(rarity + 1) * 0.0431 - 0.0431)

    # Demand × Rarity interaction — fires only when both are meaningfully above average
    d_excess = max(0.0, demand - 3.0)
    r_excess = max(0.0, rarity - 3.0)
    interaction_bonus = d_excess * r_excess * 0.003

    # Stability
    stab_bonus = (stab_mult - 1.0) * STABILITY_WEIGHT

    # Liquidity penalty based on item value tier
    liq_penalty = liquidity_penalty(base)

    bonus_multiplier = 1.0 + demand_bonus + rarity_bonus + interaction_bonus + stab_bonus - liq_penalty
    bonus_multiplier = max(0.60, min(1.70, bonus_multiplier))

    return base * bonus_multiplier, base, demand, rarity, stability


def score_side(
    items: List[Dict[str, Any]],
    apply_bundle_penalty: bool = False
) -> Tuple[float, int, float, float, List[str]]:
    """
    v3 bundle penalty: scales with average liquidity of the items given.
    Giving 4 junk items is penalised harder than giving 4 godlies.
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

    if apply_bundle_penalty and len(items) > 1:
        base_penalty_pct = 0.025 * (len(items) - 1)
        avg_liq = sum(liquidity_penalty(effective_base_value(it)) for it in items) / len(items)
        total_penalty = base_penalty_pct * (1.0 + avg_liq * 2.0)
        total_penalty = min(total_penalty, 0.22)
        ai_total *= (1.0 - total_penalty)

    avg_demand = sum(demands) / len(demands) if demands else 0.0
    avg_rarity = sum(rarities) / len(rarities) if rarities else 0.0

    return ai_total, round(raw_total), avg_demand, avg_rarity, stabilities


# ---------------- TRADE EVALUATION ----------------
def _confidence_label(ai_diff: float, threshold: float) -> str:
    if abs(ai_diff) <= threshold:
        return "even"
    excess = abs(ai_diff) - threshold
    ratio  = excess / max(threshold, 1)
    if ratio < 0.5:  return "barely"
    if ratio < 1.5:  return "clearly"
    if ratio < 3.0:  return "easily"
    return "big"


def evaluate_trade(
    yours: List[Dict[str, Any]],
    theirs: List[Dict[str, Any]]
) -> Dict[str, Any]:

    y_ai, y_raw, y_dem, y_rar, y_stab = score_side(yours,  apply_bundle_penalty=True)
    t_ai, t_raw, t_dem, t_rar, t_stab = score_side(theirs, apply_bundle_penalty=False)

    raw_diff = t_raw - y_raw
    ai_diff  = t_ai  - y_ai

    total_trade_value = max(1, y_raw + t_raw)
    pct_threshold = total_trade_value * 0.045
    threshold = max(3.0, min(pct_threshold, 400.0))  # cap at 400 for godly trades

    if abs(ai_diff) <= threshold:
        result = "fair"
    elif ai_diff > threshold:
        result = "win"
    else:
        result = "lose"

    # Stability tiebreaker
    if result == "fair":
        y_stab_avg = avg_stability_multiplier(y_stab)
        t_stab_avg = avg_stability_multiplier(t_stab)
        diff = t_stab_avg - y_stab_avg
        if diff < -0.08:   result = "lose"
        elif diff > 0.08:  result = "win"

    # Rarity tiebreaker
    if result == "fair":
        y_top_rarity = max((i.get("rarity", 0) for i in yours), default=0)
        t_top_rarity = max((i.get("rarity", 0) for i in theirs), default=0)
        if y_top_rarity - t_top_rarity >= 1.5:
            result = "lose"

    confidence = _confidence_label(ai_diff, threshold)

    return {
        "result":           result,
        "confidence":       confidence,
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
    target_items: List[Dict[str, Any]],
    max_slots: int = 4,
    min_gain_pct: float = 0.03,
    min_gain_flat: float = 5.0
) -> Optional[Tuple[List[Dict[str, Any]], float, float]]:
    results = find_top_offers(inventory_items, target_items, max_slots, min_gain_pct, min_gain_flat, top_n=1)
    return results[0] if results else None


def find_top_offers(
    inventory_items: List[Dict[str, Any]],
    target_items: List[Dict[str, Any]],
    max_slots: int = 4,
    min_gain_pct: float = 0.03,
    min_gain_flat: float = 5.0,
    top_n: int = 3,
) -> List[Tuple[List[Dict[str, Any]], float, float]]:
    if not inventory_items:
        return []

    if isinstance(target_items, dict):
        target_items = [target_items]

    target_ai = sum(score_item(t)[0] for t in target_items)
    gain_margin       = max(min_gain_flat, target_ai * min_gain_pct)
    max_offer_allowed = target_ai - gain_margin

    scored_inv = [(it, score_item(it)[0]) for it in inventory_items]

    # Safety cap: prune inventory before combinatorics blow up
    MAX_POOL = 40
    scored_inv = [(it, ai) for it, ai in scored_inv if ai <= max_offer_allowed * 1.1]
    if len(scored_inv) > MAX_POOL:
        ideal = target_ai / max(1, max_slots)
        scored_inv.sort(key=lambda x: abs(x[1] - ideal))
        scored_inv = scored_inv[:MAX_POOL]

    valid    = []
    fallback = []
    used_keys: set = set()

    for r in range(1, max_slots + 1):
        for combo in combinations(scored_inv, r):
            offer_ai     = sum(ai for _, ai in combo)
            chosen_items = [it for it, _ in combo]
            key = frozenset(it["name"] for it in chosen_items)

            abs_diff = abs(offer_ai - target_ai)
            fallback.append((abs_diff, offer_ai, chosen_items))

            if offer_ai <= max_offer_allowed:
                your_gain = target_ai - offer_ai
                valid.append((your_gain, offer_ai, key, chosen_items))

    valid.sort(key=lambda x: x[0])
    results = []
    used_keys = set()
    for your_gain, offer_ai, key, items in valid:
        if key in used_keys:
            continue
        if any(len(key & prev) == len(key) for prev in used_keys):
            continue
        used_keys.add(key)
        results.append((items, offer_ai, your_gain))
        if len(results) >= top_n:
            break

    if len(results) < top_n:
        fallback.sort(key=lambda x: x[0])
        for abs_diff, offer_ai, items in fallback:
            key = frozenset(it["name"] for it in items)
            if key in used_keys:
                continue
            used_keys.add(key)
            your_gain = target_ai - offer_ai
            results.append((items, offer_ai, your_gain))
            if len(results) >= top_n:
                break

    return results


# ---------------- OUTPUT ----------------
def explain(r: Dict[str, Any]) -> str:
    result_label = {"win":"WIN  ✅","lose":"LOSE ❌","fair":"FAIR ➖"}.get(r["result"], r["result"].upper())
    conf = r.get("confidence", "")
    conf_str = f" ({conf})" if conf and conf != "even" else ""

    lines = [
        f"Result: {result_label}{conf_str}", "",
        "── MM2 Value ──────────────────────────",
        f"  You:  {r['your_raw']}",
        f"  Them: {r['their_raw']}  ({r['raw_diff']:+})", "",
        "── AI Score (v3) ──────────────────────",
        f"  You:  {r['your_ai']}",
        f"  Them: {r['their_ai']}  ({r['ai_diff']:+})",
        f"  Fair zone: ±{r['threshold']}",
    ]
    if r.get("bundle_penalty"):
        lines.append("  ⚠️  Bundle penalty applied to your side")
    lines += [
        "", "── Demand & Rarity ────────────────────",
        f"  Demand:  You {r['your_demand']:.1f} | Them {r['their_demand']:.1f}  ({r['demand_diff']:+.1f})",
        f"  Rarity:  You {r['your_rarity']:.1f} | Them {r['their_rarity']:.1f}  ({r['rarity_diff']:+.1f})",
        "", "── Stability ──────────────────────────",
        f"  You:  {', '.join(r['your_stability'])}",
        f"  Them: {', '.join(r['their_stability'])}",
    ]
    danger = {"Underpaid For","Decreasing","Losing Hype","Fluctuating"}
    their_danger = [s for s in r["their_stability"] if s in danger]
    your_danger  = [s for s in r["your_stability"]  if s in danger]
    if their_danger: lines.append(f"  ⚠️  You'd receive: {', '.join(their_danger)}")
    if your_danger:  lines.append(f"  ⚠️  You'd give:    {', '.join(your_danger)}")
    return "\n".join(lines)


# ---------------- INTERACTIVE MODE ----------------
if __name__ == "__main__":
    db = load_items()
    print("=" * 45)
    print("        MM2 Trade Checker  v3")
    print("=" * 45)
    print("Separate items with a comma and space.")
    print("Example: turkey, evergun")
    print("Type 'quit' at any time to exit.\n")

    while True:
        yours_input = input("Your items:  ").strip()
        if yours_input.lower() == "quit": break
        theirs_input = input("Their items: ").strip()
        if theirs_input.lower() == "quit": break

        yours_items = []; theirs_items = []; missing = []
        for name in [n.strip().lower() for n in yours_input.split(",") if n.strip()]:
            if name in db: yours_items.append(db[name])
            else: missing.append(f"yours  -> '{name}'")
        for name in [n.strip().lower() for n in theirs_input.split(",") if n.strip()]:
            if name in db: theirs_items.append(db[name])
            else: missing.append(f"theirs -> '{name}'")

        if missing:
            print("\n❌ Unknown items:"); [print(f"   {m}") for m in missing]; print(); continue
        if not yours_items or not theirs_items:
            print("\n❌ Please enter at least one item on each side.\n"); continue

        result = evaluate_trade(yours_items, theirs_items)
        print("\n" + "=" * 45)
        print(explain(result))
        print("=" * 45 + "\n")
