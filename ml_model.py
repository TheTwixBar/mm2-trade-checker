"""
ml_model.py
===========
ML-powered trade evaluation — drop-in augmentation for trade_ai.py.

Provides:
  ml_evaluate_trade(yours, theirs, feature_cache_path)
    Returns the same dict as evaluate_trade() but with extra keys:
      ml_label       - 'win' / 'fair' / 'lose'
      ml_win_prob    - float 0–1
      ml_fair_prob   - float 0–1
      ml_lose_prob   - float 0–1
      ml_score       - signed numeric score (+100 = big win, -100 = big loss)
      ml_confidence  - 'low' / 'medium' / 'high'

Usage in app.py:
  from ml_model import ml_evaluate_trade
  result = ml_evaluate_trade(yours_items, theirs_items)
"""

import math
import pickle
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

# ── Stability score map (must match build_features.py) ───────────────────────
STAB_MAP = {
    "Rising": 1., "Hyped": .9, "Doing Well": .7, "Overpaid For": .6,
    "Improving": .5, "Stabilizing": .3, "Recovering": .3, "Stable": 0.,
    "N/A": -.1, "Fluctuating": -.3, "Receding": -.4,
    "Losing Hype": -.5, "Underpaid For": -.7, "Decreasing": -.9,
}

MODEL_PATH = Path(__file__).parent / "mm2_model.pkl"
CACHE_PATH = Path(__file__).parent / "feature_cache.csv"

_model_bundle = None
_feature_cache = None


def _load_model():
    global _model_bundle
    if _model_bundle is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}. Run train_model.py first.")
        with open(MODEL_PATH, "rb") as f:
            _model_bundle = pickle.load(f)
    return _model_bundle


def _load_cache():
    """Load feature cache lazily. Returns a dict: item_lower -> latest feature row."""
    global _feature_cache
    if _feature_cache is None:
        if not CACHE_PATH.exists():
            return {}
        import pandas as pd
        df = pd.read_csv(CACHE_PATH, parse_dates=["date"])
        # Keep only the most recent snapshot per item
        df = df.sort_values("date")
        latest = df.groupby("item").last().reset_index()
        _feature_cache = {}
        for _, row in latest.iterrows():
            _feature_cache[row["item"].lower()] = row.to_dict()
    return _feature_cache


def _item_features(item: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract ML features for a single item.
    Falls back to current item stats if no cache entry found.
    """
    cache = _load_cache()
    key = item["name"].lower()
    cached = cache.get(key)

    value = float(item.get("value") or 0)
    demand = float(item.get("demand") or 5.0)
    rarity = float(item.get("rarity") or 3.0)
    stab_str = str(item.get("stability") or "Stable").strip().title()
    stab_score = STAB_MAP.get(stab_str, 0.0)

    if cached:
        return {
            "value":      float(cached.get("value", value)),
            "log_value":  float(cached.get("log_value", math.log1p(value))),
            "demand":     float(cached.get("demand", demand)),
            "rarity":     float(cached.get("rarity", rarity)),
            "stab_score": float(cached.get("stab_score", stab_score)),
            "p7":         float(cached.get("p7", 0.0)),
            "p30":        float(cached.get("p30", 0.0)),
            "p90":        float(cached.get("p90", 0.0)),
            "updates30":  float(cached.get("updates30", 1.0)),
            "streak":     float(cached.get("streak", 0.0)),
        }
    else:
        # No history — use current snapshot only, zero out trend features
        return {
            "value":      value,
            "log_value":  math.log1p(value),
            "demand":     demand,
            "rarity":     rarity,
            "stab_score": stab_score,
            "p7":  0.0, "p30": 0.0, "p90": 0.0,
            "updates30": 1.0, "streak": 0.0,
        }


def _agg_side(items: List[Dict[str, Any]], prefix: str) -> Dict[str, float]:
    feat_list = [_item_features(it) for it in items]

    vals   = [f["value"]      for f in feat_list]
    lvals  = [f["log_value"]  for f in feat_list]
    dems   = [f["demand"]     for f in feat_list]
    rars   = [f["rarity"]     for f in feat_list]
    stabs  = [f["stab_score"] for f in feat_list]
    p7s    = [f["p7"]         for f in feat_list]
    p30s   = [f["p30"]        for f in feat_list]
    p90s   = [f["p90"]        for f in feat_list]
    upds   = [f["updates30"]  for f in feat_list]
    stks   = [f["streak"]     for f in feat_list]

    return {
        f"{prefix}_value_sum":   sum(vals),
        f"{prefix}_log_val_sum": sum(lvals),
        f"{prefix}_demand_avg":  float(np.mean(dems)),
        f"{prefix}_rarity_avg":  float(np.mean(rars)),
        f"{prefix}_stab_avg":    float(np.mean(stabs)),
        f"{prefix}_p7_avg":      float(np.mean(p7s)),
        f"{prefix}_p30_avg":     float(np.mean(p30s)),
        f"{prefix}_p90_avg":     float(np.mean(p90s)),
        f"{prefix}_updates30":   float(np.mean(upds)),
        f"{prefix}_streak_avg":  float(np.mean(stks)),
        f"{prefix}_n_items":     float(len(items)),
    }


def ml_evaluate_trade(
    yours: List[Dict[str, Any]],
    theirs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate a trade using the trained ML model.
    Returns a dict with ml_label, ml_*_prob, ml_score, ml_confidence.
    Also includes all original evaluate_trade() keys.
    """
    # Import here to avoid circular if ml_model is in same folder as trade_ai
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from trade_ai import evaluate_trade

    # Get the rule-based result too (keep it for reference)
    base_result = evaluate_trade(yours, theirs)

    try:
        bundle = _load_model()
        model = bundle["model"]
        feat_cols = bundle["features"]

        yf = _agg_side(yours,  "y")
        tf = _agg_side(theirs, "t")

        row = {
            **yf, **tf,
            "value_ratio":  yf["y_value_sum"] / max(tf["t_value_sum"], 1),
            "demand_diff":  yf["y_demand_avg"]  - tf["t_demand_avg"],
            "rarity_diff":  yf["y_rarity_avg"]  - tf["t_rarity_avg"],
            "stab_diff":    yf["y_stab_avg"]    - tf["t_stab_avg"],
            "p30_diff":     yf["y_p30_avg"]     - tf["t_p30_avg"],
            "p90_diff":     yf["y_p90_avg"]     - tf["t_p90_avg"],
            "streak_diff":  yf["y_streak_avg"]  - tf["t_streak_avg"],
            "total_items":  float(len(yours) + len(theirs)),
        }

        X = np.array([[row.get(c, 0.0) for c in feat_cols]])
        proba = model.predict_proba(X)[0]
        classes = list(model.classes_)

        def p(label):
            return float(proba[classes.index(label)]) if label in classes else 0.0

        win_p  = p("win")
        fair_p = p("fair")
        lose_p = p("lose")

        # Signed score: +100 = certain win, -100 = certain loss
        ml_score = round((win_p - lose_p) * 100, 1)

        # Label: highest probability class, but fair needs to beat both others
        ml_label = classes[int(np.argmax(proba))]

        # Confidence based on margin
        margin = max(proba) - sorted(proba)[-2]
        if margin > 0.5:   ml_conf = "high"
        elif margin > 0.2: ml_conf = "medium"
        else:              ml_conf = "low"

        base_result.update({
            "ml_label":      ml_label,
            "ml_win_prob":   round(win_p,  3),
            "ml_fair_prob":  round(fair_p, 3),
            "ml_lose_prob":  round(lose_p, 3),
            "ml_score":      ml_score,
            "ml_confidence": ml_conf,
            "ml_available":  True,
        })

    except Exception as e:
        import traceback
        warnings.warn(f"ML model unavailable: {e}\n{traceback.format_exc()}")
        print(f"ML ERROR: {traceback.format_exc()}")
        base_result.update({
            "ml_label":      base_result["result"],
            "ml_win_prob":   None,
            "ml_fair_prob":  None,
            "ml_lose_prob":  None,
            "ml_score":      None,
            "ml_confidence": None,
            "ml_available":  False,
        })

    return base_result


if __name__ == "__main__":
    # Quick smoke test
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "mm2-trade-checker-main"))
    from trade_ai import load_items

    db = load_items("mm2-trade-checker-main/data_txt")

    test_trades = [
        (["darkshot"], ["constellation"]),
        (["constellation", "evergreen"], ["travelers gun"]),
        (["darkshot"], ["darkshot"]),
    ]

    for y_names, t_names in test_trades:
        yi = [db[n] for n in y_names if n in db]
        ti = [db[n] for n in t_names if n in db]
        if not yi or not ti:
            print(f"Skipping {y_names} vs {t_names} — items not found")
            continue
        r = ml_evaluate_trade(yi, ti)
        print(f"\n{y_names} vs {t_names}")
        print(f"  Rule-based: {r['result']} | ML: {r['ml_label']} "
              f"(W:{r['ml_win_prob']:.2f} F:{r['ml_fair_prob']:.2f} L:{r['ml_lose_prob']:.2f})")
        print(f"  ML score: {r['ml_score']:+.1f}  confidence: {r['ml_confidence']}")
