"""Reference (pandas) implementation of the ProductIQ medallion pipeline.

This module mirrors, step by step, the PySpark logic in
``fabric/notebooks/01_bronze_to_silver.ipynb`` and ``02_silver_to_gold.ipynb``
so that we can:

* validate the scenario signals inside the data generator "like an analyst
  would" (from the cleaned / derived data, not from generator internals);
* compute golden evaluation answers (``eval/build_golden.py``);
* execute the Fabric data-agent example queries locally (SQLite over the gold
  frames) to make sure they actually work against the schema.

The text rules (topic keywords, sentiment lexicon, pet keywords, region
aliases ...) below are the single source of truth.  The Fabric notebook 01
embeds an identical copy; ``eval/build_golden.py`` checks they did not drift.

Only the Python standard library, numpy and pandas are used.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW_START = "2024-11-01"
WINDOW_END = "2026-10-31"

# --------------------------------------------------------------------------------------
# Shared cleaning / enrichment rules (copied verbatim into notebook 01)
# --------------------------------------------------------------------------------------
# BEGIN SHARED RULES
REGION_ALIASES = {
    "JPN": "JP", "JAPAN": "JP", "USA": "US", "U.S.": "US", "GB": "UK", "GBR": "UK",
    "DEU": "DE", "GER": "DE", "FRA": "FR", "KOR": "KR", "CHN": "CN", "SGP": "SG",
    "AUS": "AU", "CAN": "CA",
}

TRUE_VALUES = ["true", "t", "yes", "y", "1"]
FALSE_VALUES = ["false", "f", "no", "n", "0"]

# Ordered keyword rules: the first matching topic wins.  Patterns are Java/Python
# compatible regular expressions applied to the lower-cased "title + text".
TOPIC_RULES = [
    ("hair_tangling", [r"tangl", r"(?:wrap|wound|wind)\w* around", r"hair.{0,40}brush",
                       r"brush.{0,40}hair", r"\bfur\b.{0,40}brush", r"brush.{0,40}\bfur\b",
                       "絡ま", "絡み", "ブラシに髪", "ブラシに毛"]),
    ("dock_emptying", [r"self-empt", r"auto-empt", r"emptying", r"dust bag", r"empty station",
                       r"dock.{0,30}(?:clog|jam|full|empt)", "ゴミ収集", "紙パック"]),
    ("navigation", [r"navigat", r"\bbump", r"stuck under", r"\bmaps?\b", r"mapping", r"obstacle",
                    r"lidar", r"gets lost", r"got lost", r"cliff sensor", "マップ", "マッピング",
                    "ぶつか", "障害物", "段差"]),
    ("battery_life", [r"batter", r"runtime", r"run time", r"one charge", r"recharg",
                      r"holding charge", "バッテリー", "電池", "充電"]),
    ("suction", [r"suction", r"pick(?:s|ed|ing)? up", r"leaves debris", "吸引", "吸い込"]),
    ("filter", [r"filter", r"\bhepa\b", "フィルター"]),
    ("noise", [r"noise", r"noisy", r"\bloud", r"quiet", r"decibel", r"rattl", r"whin(?:e|ing)",
               "うるさい", "騒音", "音が大き", "静か"]),
    ("app_connectivity", [r"\bapp\b", r"wi-?fi", r"connect", r"firmware", r"pairing",
                          r"bluetooth", "アプリ", "接続"]),
    ("water_leak", [r"leak", r"puddle", "水漏れ"]),
    ("cooking_quality", [r"\brice\b", r"cook", r"heats unevenly", r"uneven heating", r"reheat",
                         r"defrost", r"undercooked", r"burnt", "炊", "ご飯", "加熱", "温め"]),
    ("cooling", [r"cooling", r"not cold", r"warm inside", r"temperature", r"freez",
                 r"ice maker", r"frost", "冷え", "冷蔵", "冷凍"]),
    ("wash_performance", [r"stain", r"rinse", r"spots on", r"residue", r"still dirty",
                          r"wash cycle", r"wash results", r"spotless", "汚れが落ち", "洗浄",
                          "すすぎ"]),
    ("durability", [r"\bbroke", r"stopped working", r"died after", r"fell apart", r"crack",
                    r"defect", r"durab", r"sturdy", r"build quality", r"well built", "壊れ",
                    "故障", "丈夫", "しっかり"]),
    ("price", [r"price", r"pricey", r"expensive", r"overpriced", r"value for money",
               r"worth the money", r"\bcheap", "価格", "値段", "コスパ"]),
    ("delivery", [r"deliver", r"shipping", r"courier", r"arrived", r"packag", r"parcel",
                  "配送", "届", "梱包"]),
    ("ease_of_use", [r"easy to use", r"easy to set up", r"set ?up", r"intuitive", r"controls",
                     r"manual", r"confusing", r"buttons", "使いやす", "操作", "説明書"]),
]
DEFAULT_TOPIC = "other"

# Sentiment lexicon (presence of each term counts once).
POS_TERMS = [r"\bgreat\b", r"\bexcellent\b", r"\blove[sd]?\b", r"\bperfect(?:ly)?\b",
             r"\bamazing\b", r"\bimpressed\b", r"\brecommend", r"\bfantastic\b",
             r"\bsatisfied\b", r"\bhappy\b", r"\bflawless(?:ly)?\b", r"\breliable\b",
             r"\bawesome\b", r"\bsuperb\b", r"\bgame changer\b",
             "満足", "最高", "素晴らしい", "便利", "気に入", "おすすめ", "買ってよかった", "助か"]
NEG_TERMS = [r"\bdisappoint", r"\bterrible\b", r"\bawful\b", r"\bpoor(?:ly)?\b",
             r"\bbroken?\b", r"\buseless\b", r"\bannoying\b", r"\bfrustrat", r"\bworst\b",
             r"\bwaste\b", r"\brefund", r"\breturn(?:ed|ing)?\b", r"\bhate\b", r"\bavoid\b",
             r"\bproblems?\b", r"\bissues?\b", r"\bweak\b", r"\bfail(?:s|ed|ing)?\b",
             "残念", "がっかり", "最悪", "不満", "返品", "困", "大変", "ひどい"]

# Mentions that identify a pet-owning customer in free text.
PET_TERMS = [r"\bdogs?\b", r"\bcats?\b", r"\bpets?\b", r"\bpupp(?:y|ies)\b", r"\bkittens?\b",
             "ペット", "犬", "猫"]

# Any Hiragana / Katakana / CJK ideograph => Japanese text.
JA_CHAR_PATTERN = r"[\u3040-\u30ff\u4e00-\u9fff]"

# Sentiment = 0.75 * rating component + 0.25 * lexicon score; tickets have no
# rating and use TICKET_RATING_COMPONENT (they are complaints by nature).
RATING_WEIGHT = 0.75
LEXICON_WEIGHT = 0.25
TICKET_RATING_COMPONENT = -0.5
POSITIVE_THRESHOLD = 0.25
NEGATIVE_THRESHOLD = -0.25

# kg CO2e per tonne-km by transport mode (used when the source value is missing).
EMISSION_FACTORS_KG_PER_TKM = {"ocean": 0.016, "rail": 0.028, "truck": 0.105, "air": 0.602}
# END SHARED RULES


def combined_pattern(patterns: list[str]) -> str:
    """Join a list of regexes into one alternation (same string used by Spark rlike)."""
    return "|".join(f"(?:{p})" for p in patterns)


TOPIC_PATTERNS = [(t, combined_pattern(p)) for t, p in TOPIC_RULES]
PET_PATTERN = combined_pattern(PET_TERMS)


def classify_topic_text(text: str) -> str:
    """Scalar topic classifier (used by the generator self-checks)."""
    low = (text or "").lower()
    for topic, pat in TOPIC_PATTERNS:
        if re.search(pat, low):
            return topic
    return DEFAULT_TOPIC


# --------------------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------------------
def round_half_up(x, digits: int = 2):
    """Replicates Spark's F.round on doubles: BigDecimal of the shortest decimal repr, HALF_UP.

    numpy/pandas round half-to-even on the binary value, which differs in a few cents.
    """
    quantum = Decimal(1).scaleb(-digits)
    arr = np.asarray(x, dtype="float64")
    flat = [float(Decimal(repr(v)).quantize(quantum, rounding=ROUND_HALF_UP)) if np.isfinite(v) else v
            for v in arr.ravel().tolist()]
    return np.array(flat, dtype="float64").reshape(arr.shape)


def read_bronze(bronze_dir: Path, name: str) -> pd.DataFrame:
    """Read a bronze CSV with everything as string; empty fields -> null (like Spark)."""
    path = Path(bronze_dir) / name / f"{name}.csv"
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8")


def trim(s: pd.Series) -> pd.Series:
    return s.str.strip(" ")


def norm_region(s: pd.Series) -> pd.Series:
    up = trim(s).str.upper()
    return up.map(lambda v: REGION_ALIASES.get(v, v) if isinstance(v, str) else v)


def to_bool(s: pd.Series) -> pd.Series:
    low = trim(s).str.lower()
    out = pd.Series(pd.NA, index=s.index, dtype="boolean")
    out[low.isin(TRUE_VALUES)] = True
    out[low.isin(FALSE_VALUES)] = False
    return out


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.str.slice(0, 10), format="%Y-%m-%d", errors="coerce")


def to_ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%Y-%m-%dT%H:%M:%S", errors="coerce")


def year_month(d: pd.Series) -> pd.Series:
    return d.dt.strftime("%Y-%m")


def date_key(d: pd.Series) -> pd.Series:
    return d.dt.strftime("%Y%m%d").astype("Int64")


def contains(text: pd.Series, pattern: str) -> pd.Series:
    return text.str.contains(pattern, regex=True, na=False)


def derive_topic(text_lower: pd.Series) -> pd.Series:
    out = pd.Series(DEFAULT_TOPIC, index=text_lower.index, dtype=object)
    done = pd.Series(False, index=text_lower.index)
    for topic, pat in TOPIC_PATTERNS:
        m = contains(text_lower, pat) & ~done
        out[m] = topic
        done |= m
    return out


def lexicon_score(text_lower: pd.Series) -> pd.Series:
    pos = sum(contains(text_lower, p).astype(int) for p in POS_TERMS)
    neg = sum(contains(text_lower, p).astype(int) for p in NEG_TERMS)
    return (pos - neg) / np.maximum(pos + neg, 1)


def sentiment(rating_component: pd.Series, lex: pd.Series):
    raw = RATING_WEIGHT * rating_component + LEXICON_WEIGHT * lex
    label = np.where(raw > POSITIVE_THRESHOLD, "positive",
                     np.where(raw < NEGATIVE_THRESHOLD, "negative", "neutral"))
    return pd.Series(round_half_up(raw, 4), index=raw.index), pd.Series(label, index=raw.index)


def concat_ws(*cols: pd.Series) -> pd.Series:
    """Spark concat_ws(' ', ...) – nulls are skipped."""
    frame = pd.concat(cols, axis=1)
    return frame.apply(lambda r: " ".join(str(v) for v in r if isinstance(v, str)), axis=1)


# --------------------------------------------------------------------------------------
# Bronze -> Silver
# --------------------------------------------------------------------------------------
def build_silver(bronze_dir: Path) -> dict[str, pd.DataFrame]:
    b = lambda n: read_bronze(bronze_dir, n)  # noqa: E731
    s: dict[str, pd.DataFrame] = {}

    # ---- reference data ----------------------------------------------------------
    reg = b("erp_regions")
    reg["region_code"] = norm_region(reg["region_code"])
    reg["fx_to_usd"] = to_num(reg["fx_to_usd"])
    s["silver_regions"] = reg.drop_duplicates("region_code").reset_index(drop=True)

    al = b("erp_product_aliases")
    al["alias_code"] = trim(al["alias_code"]).str.upper()
    al["product_code"] = trim(al["product_code"]).str.upper()
    s["silver_product_aliases"] = al.drop_duplicates("alias_code").reset_index(drop=True)
    alias_map = dict(zip(s["silver_product_aliases"]["alias_code"],
                         s["silver_product_aliases"]["product_code"]))

    prod = b("erp_products")
    prod["product_code"] = trim(prod["product_code"]).str.upper()
    prod["launch_date"] = to_date(prod["launch_date"])
    prod["discontinue_date"] = to_date(prod["discontinue_date"])
    prod["list_price_usd"] = to_num(prod["list_price_usd"])
    prod["weight_kg"] = to_num(prod["weight_kg"])
    for c in ["has_lidar", "has_self_empty_dock", "has_mop", "is_pet_edition"]:
        prod[c] = to_bool(prod[c]).fillna(False).astype(bool)
    s["silver_products"] = prod.drop_duplicates("product_code").reset_index(drop=True)
    valid_products = set(s["silver_products"]["product_code"])

    def norm_product(col: pd.Series) -> pd.Series:
        up = trim(col).str.upper()
        return up.map(lambda v: alias_map.get(v, v) if isinstance(v, str) else v)

    pl = b("erp_plants")
    pl["plant_code"] = trim(pl["plant_code"]).str.upper()
    pl["monthly_capacity_units"] = to_int(pl["monthly_capacity_units"])
    pl["opened_year"] = to_int(pl["opened_year"])
    s["silver_plants"] = pl.drop_duplicates("plant_code").reset_index(drop=True)

    sup = b("erp_suppliers")
    sup["supplier_id"] = trim(sup["supplier_id"]).str.upper()
    sup["quality_rating"] = to_num(sup["quality_rating"])
    sup["esg_score"] = to_int(sup["esg_score"])
    sup["status"] = trim(sup["status"]).str.lower()
    sup["onboarded_date"] = to_date(sup["onboarded_date"])
    s["silver_suppliers"] = sup.drop_duplicates("supplier_id").reset_index(drop=True)

    comp = b("plm_components")
    comp["component_code"] = trim(comp["component_code"]).str.upper()
    comp["primary_supplier_id"] = trim(comp["primary_supplier_id"]).str.upper()
    comp["standard_cost_usd"] = to_num(comp["standard_cost_usd"])
    comp["recyclable_pct"] = to_num(comp["recyclable_pct"])
    comp["weight_g"] = to_int(comp["weight_g"])
    comp["is_critical"] = to_bool(comp["is_critical"]).fillna(False).astype(bool)
    s["silver_components"] = comp.drop_duplicates("component_code").reset_index(drop=True)

    bom = b("plm_bom")
    bom["product_code"] = norm_product(bom["product_code"])
    bom["component_code"] = trim(bom["component_code"]).str.upper()
    bom["quantity"] = to_num(bom["quantity"])
    bom["bom_version"] = to_int(bom["bom_version"])
    bom["effective_from"] = to_date(bom["effective_from"])
    bom["effective_to"] = to_date(bom["effective_to"])
    bom = bom.drop_duplicates(["product_code", "component_code", "bom_version"])
    s["silver_bom"] = bom[bom["product_code"].isin(valid_products)].reset_index(drop=True)

    # ---- CRM customers -----------------------------------------------------------
    cu = b("crm_customer_segments")
    cu["customer_id"] = trim(cu["customer_id"]).str.upper()
    cu["region_code"] = norm_region(cu["region_code"])
    cu["pet_owner"] = to_bool(cu["pet_owner"])
    cu["household_size"] = to_int(cu["household_size"])
    cu["signup_date"] = to_date(cu["signup_date"])
    cu["segment"] = trim(cu["segment"]).str.lower()
    s["silver_customers"] = cu.drop_duplicates("customer_id").reset_index(drop=True)
    crm_pet = dict(zip(s["silver_customers"]["customer_id"], s["silver_customers"]["pet_owner"]))

    def derive_pet(flag: pd.Series, text_lower: pd.Series, customer: pd.Series):
        explicit = to_bool(flag)
        text_pet = contains(text_lower, PET_PATTERN)
        crm = customer.map(lambda c: crm_pet.get(c, pd.NA) if isinstance(c, str) else pd.NA)
        crm = crm.astype("boolean")
        pet = explicit.copy()
        src = pd.Series(np.where(explicit.notna(), "profile_flag", None), index=flag.index, dtype=object)
        m = pet.isna() & text_pet
        pet[m] = True
        src[m] = "text"
        m = pet.isna() & crm.notna()
        pet[m] = crm[m]
        src[m] = "crm"
        m = pet.isna()
        pet[m] = False
        src[m] = "default"
        return pet.astype(bool), src

    # ---- sales -------------------------------------------------------------------
    so = b("erp_sales_orders").drop_duplicates("order_line_id")
    so["order_date"] = to_date(so["order_date"])
    so["product_code"] = norm_product(so["product_code"])
    so["region_code"] = norm_region(so["region_code"])
    so["channel"] = trim(so["channel"]).str.lower().fillna("unknown")
    so["plant_code"] = trim(so["plant_code"]).str.upper()
    so["units"] = to_int(so["units"])
    so["unit_price_local"] = to_num(so["unit_price_local"])
    so["gross_revenue_local"] = to_num(so["gross_revenue_local"])
    so["discount_pct"] = to_num(so["discount_pct"]).fillna(0.0)
    so["net_revenue_usd"] = to_num(so["net_revenue_usd"])
    so["currency"] = trim(so["currency"]).str.upper()
    fx = dict(zip(s["silver_regions"]["region_code"], s["silver_regions"]["fx_to_usd"]))
    so["gross_revenue_usd"] = round_half_up(so["gross_revenue_local"] * so["region_code"].map(fx), 2)
    so["net_revenue_usd"] = so["net_revenue_usd"].fillna(
        pd.Series(round_half_up(so["gross_revenue_usd"] * (1 - so["discount_pct"] / 100.0), 2), index=so.index))
    so = so[so["product_code"].isin(valid_products) & so["order_date"].notna() & (so["units"] > 0)]
    s["silver_sales"] = so.sort_values("order_line_id").reset_index(drop=True)

    # ---- reviews -----------------------------------------------------------------
    rv = b("ecommerce_reviews").drop_duplicates("review_id")
    rv["review_date"] = to_date(rv["review_date"])
    rv["product_code"] = norm_product(rv["product_code"])
    rv["region_code"] = norm_region(rv["region_code"])
    rv["customer_id"] = trim(rv["customer_id"]).str.upper()
    rv["platform"] = trim(rv["platform"])
    rv["rating"] = to_int(rv["rating"])
    rv["helpful_votes"] = to_int(rv["helpful_votes"]).fillna(0)
    rv["verified_purchase"] = to_bool(rv["verified_purchase"]).fillna(False).astype(bool)
    text = concat_ws(rv["title"], rv["review_text"])
    low = text.str.lower()
    rv["language"] = trim(rv["language"]).str.lower()
    rv["language"] = rv["language"].fillna(pd.Series(np.where(contains(text, JA_CHAR_PATTERN), "ja", "en"), index=rv.index))
    rv["pet_owner"], rv["pet_owner_source"] = derive_pet(rv["pet_owner"], low, rv["customer_id"])
    rv["topic"] = derive_topic(low)
    rc = ((rv["rating"].astype("float64") - 3.0) / 2.0).fillna(0.0)
    rv["sentiment_score"], rv["sentiment_label"] = sentiment(rc, lexicon_score(low))
    rv = rv[rv["product_code"].isin(valid_products) & rv["review_date"].notna()]
    s["silver_reviews"] = rv.sort_values("review_id").reset_index(drop=True)

    # ---- support tickets ---------------------------------------------------------
    tk = b("cs_tickets").drop_duplicates("ticket_id")
    tk["created_at"] = to_ts(tk["created_at"])
    tk["closed_at"] = to_ts(tk["closed_at"])
    tk["product_code"] = norm_product(tk["product_code"])
    tk["region_code"] = norm_region(tk["region_code"])
    tk["customer_id"] = trim(tk["customer_id"]).str.upper()
    tk["contact_channel"] = trim(tk["contact_channel"]).str.lower()
    tk["issue_category"] = trim(tk["issue_category"]).str.lower().fillna("unclassified")
    tk["priority"] = trim(tk["priority"]).str.lower()
    tk["status"] = trim(tk["status"]).str.lower()
    tk["csat_score"] = to_int(tk["csat_score"])
    text = concat_ws(tk["subject"], tk["description"])
    low = text.str.lower()
    tk["language"] = trim(tk["language"]).str.lower()
    tk["language"] = tk["language"].fillna(pd.Series(np.where(contains(text, JA_CHAR_PATTERN), "ja", "en"), index=tk.index))
    tk["pet_owner"], tk["pet_owner_source"] = derive_pet(tk["pet_owner"], low, tk["customer_id"])
    tk["topic"] = derive_topic(low)
    rc = pd.Series(TICKET_RATING_COMPONENT, index=tk.index)
    tk["sentiment_score"], tk["sentiment_label"] = sentiment(rc, lexicon_score(low))
    tk = tk[tk["product_code"].isin(valid_products) & tk["created_at"].notna()]
    s["silver_tickets"] = tk.sort_values("ticket_id").reset_index(drop=True)

    # ---- warranty ----------------------------------------------------------------
    wc = b("warranty_claims").drop_duplicates("claim_id")
    wc["claim_date"] = to_date(wc["claim_date"])
    wc["purchase_date"] = to_date(wc["purchase_date"])
    wc["product_code"] = norm_product(wc["product_code"])
    wc["region_code"] = norm_region(wc["region_code"])
    wc["customer_id"] = trim(wc["customer_id"]).str.upper()
    wc["failed_component_code"] = trim(wc["failed_component_code"]).str.upper()
    wc["failure_mode"] = trim(wc["failure_mode"]).str.lower()
    wc["repair_action"] = trim(wc["repair_action"]).str.lower()
    wc["claim_status"] = trim(wc["claim_status"]).str.lower()
    wc["claim_cost_usd"] = to_num(wc["claim_cost_usd"])
    wc["days_in_service"] = to_int(wc["days_in_service"])
    derived_purchase = wc["claim_date"] - pd.to_timedelta(wc["days_in_service"].astype("float64"), unit="D")
    wc["purchase_date"] = wc["purchase_date"].fillna(derived_purchase)
    wc["days_in_service"] = wc["days_in_service"].fillna(
        (wc["claim_date"] - wc["purchase_date"]).dt.days.astype("Int64"))
    pet = wc["customer_id"].map(lambda c: crm_pet.get(c, pd.NA) if isinstance(c, str) else pd.NA)
    wc["pet_owner"] = pet.astype("boolean").fillna(False).astype(bool)
    wc = wc[wc["product_code"].isin(valid_products) & wc["claim_date"].notna()]
    s["silver_warranty"] = wc.sort_values("claim_id").reset_index(drop=True)

    # ---- supplier capacity (monthly) --------------------------------------------
    cap = b("scm_supplier_capacity")
    cap["month"] = pd.to_datetime(trim(cap["month"]).str.slice(0, 7) + "-01", format="%Y-%m-%d", errors="coerce")
    cap["supplier_id"] = trim(cap["supplier_id"]).str.upper()
    cap["component_code"] = trim(cap["component_code"]).str.upper()
    for c in ["capacity_units", "committed_units", "lead_time_days", "alt_supplier_qualification_days"]:
        cap[c] = to_int(cap[c])
    cap["alt_supplier_candidate_id"] = trim(cap["alt_supplier_candidate_id"]).str.upper()
    cap["utilisation_pct"] = to_num(cap["utilisation_pct"])
    recomputed = pd.Series(round_half_up(100.0 * cap["committed_units"].astype("float64") /
                                         cap["capacity_units"].astype("float64"), 1), index=cap.index)
    cap["utilisation_pct"] = cap["utilisation_pct"].fillna(recomputed)
    cap = cap.drop_duplicates(["month", "supplier_id", "component_code"])
    s["silver_supplier_capacity"] = cap.sort_values(["month", "component_code", "supplier_id"]).reset_index(drop=True)

    # ---- component costs (monthly) ----------------------------------------------
    cc = b("scm_component_costs")
    cc["month"] = to_date(cc["month"])
    cc["component_code"] = trim(cc["component_code"]).str.upper()
    cc["primary_supplier_id"] = trim(cc["primary_supplier_id"]).str.upper()
    cc["unit_cost_usd"] = to_num(cc["unit_cost_usd"])
    cc = cc.drop_duplicates(["month", "component_code"])
    s["silver_component_costs"] = cc.sort_values(["month", "component_code"]).reset_index(drop=True)

    # ---- logistics ---------------------------------------------------------------
    sh = b("logistics_shipments").drop_duplicates("shipment_id")
    sh["ship_date"] = to_date(sh["ship_date"])
    sh["delivery_date"] = to_date(sh["delivery_date"])
    sh["origin_plant_code"] = trim(sh["origin_plant_code"]).str.upper()
    sh["destination_region_code"] = norm_region(sh["destination_region_code"])
    sh["product_code"] = norm_product(sh["product_code"])
    sh["transport_mode"] = trim(sh["transport_mode"]).str.lower()
    for c in ["units", "planned_transit_days"]:
        sh[c] = to_int(sh[c])
    for c in ["weight_kg", "distance_km", "freight_cost_usd", "co2e_kg"]:
        sh[c] = to_num(sh[c])
    factor = sh["transport_mode"].map(EMISSION_FACTORS_KG_PER_TKM).astype("float64")
    sh["co2e_kg"] = sh["co2e_kg"].fillna(pd.Series(round_half_up(sh["weight_kg"] / 1000.0 * sh["distance_km"] * factor, 2), index=sh.index))
    sh = sh[sh["product_code"].isin(valid_products) & sh["ship_date"].notna()]
    s["silver_shipments"] = sh.sort_values("shipment_id").reset_index(drop=True)

    # ---- market signals (keep latest revision) ---------------------------------
    ms = b("market_signals")
    ms["month"] = to_date(ms["month"])
    ms["region_code"] = norm_region(ms["region_code"])
    ms["category"] = trim(ms["category"]).str.lower()
    ms["metric"] = trim(ms["metric"]).str.lower()
    ms["value"] = to_num(ms["value"])
    ms["published_date"] = to_date(ms["published_date"])
    ms = ms.sort_values(["month", "region_code", "category", "metric", "published_date"])
    ms = ms.drop_duplicates(["month", "region_code", "category", "metric"], keep="last")
    s["silver_market_signals"] = ms.reset_index(drop=True)
    return s


# --------------------------------------------------------------------------------------
# Silver -> Gold
# --------------------------------------------------------------------------------------
def season_event(d: dt.date) -> str:
    """Retail event calendar used by dim_date (identical code in notebook 02)."""
    nov1 = dt.date(d.year, 11, 1)
    thanksgiving = nov1 + dt.timedelta(days=(3 - nov1.weekday()) % 7 + 21)
    black_friday = thanksgiving + dt.timedelta(days=1)
    if black_friday <= d <= black_friday + dt.timedelta(days=3):
        return "black_friday"
    if d.month == 11 and d.day <= 11:
        return "singles_day"
    if d.month == 12 and d.day >= 15:
        return "year_end"
    if (d.month == 4 and d.day >= 29) or (d.month == 5 and d.day <= 5):
        return "golden_week"
    if d.month in (7, 8):
        return "summer"
    return "none"


def build_dim_date_rows(start: str = WINDOW_START, end: str = WINDOW_END) -> list[dict]:
    d0 = dt.date.fromisoformat(start)
    d1 = dt.date.fromisoformat(end)
    rows = []
    d = d0
    while d <= d1:
        fy = d.year if d.month >= 4 else d.year - 1
        fq = ((d.month - 4) % 12) // 3 + 1
        rows.append({
            "date_key": int(d.strftime("%Y%m%d")), "date": d.isoformat(), "year": d.year,
            "quarter": (d.month - 1) // 3 + 1, "month": d.month, "month_name": d.strftime("%B"),
            "year_month": d.strftime("%Y-%m"), "week_of_year": d.isocalendar()[1],
            "day_of_week": d.isoweekday(), "day_name": d.strftime("%A"),
            "is_weekend": d.isoweekday() >= 6, "fiscal_year": f"FY{fy}", "fiscal_quarter": f"FY{fy}-Q{fq}",
            "season_event": season_event(d),
        })
        d += dt.timedelta(days=1)
    return rows


def build_gold(s: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    g: dict[str, pd.DataFrame] = {}

    dd = pd.DataFrame(build_dim_date_rows())
    dd["date"] = pd.to_datetime(dd["date"])
    g["dim_date"] = dd

    p = s["silver_products"]
    g["dim_product"] = pd.DataFrame({
        "product_id": p["product_code"], "product_name": p["product_name"], "category": p["category"],
        "subcategory": p["subcategory"], "series": p["series"], "launch_date": p["launch_date"],
        "discontinue_date": p["discontinue_date"],
        "is_active": p["discontinue_date"].isna() | (p["discontinue_date"] > pd.Timestamp(WINDOW_END)),
        "list_price_usd": p["list_price_usd"], "target_segment": p["target_segment"],
        "primary_plant_id": p["primary_plant_code"], "has_lidar": p["has_lidar"],
        "has_self_empty_dock": p["has_self_empty_dock"], "has_mop": p["has_mop"],
        "is_pet_edition": p["is_pet_edition"],
    })

    c = s["silver_components"]
    g["dim_component"] = pd.DataFrame({
        "component_id": c["component_code"], "component_name": c["component_name"],
        "component_category": c["component_category"], "unit_of_measure": c["unit_of_measure"],
        "standard_cost_usd": c["standard_cost_usd"], "is_critical": c["is_critical"],
        "recyclable_pct": c["recyclable_pct"], "weight_g": c["weight_g"],
        "primary_supplier_id": c["primary_supplier_id"],
    })

    su = s["silver_suppliers"]
    g["dim_supplier"] = pd.DataFrame({
        "supplier_id": su["supplier_id"], "supplier_name": su["supplier_name"], "country": su["country"],
        "supplier_tier": su["tier"], "supply_category": su["supply_category"],
        "quality_rating": su["quality_rating"], "esg_score": su["esg_score"], "status": su["status"],
        "onboarded_date": su["onboarded_date"],
    })

    pl = s["silver_plants"]
    g["dim_plant"] = pd.DataFrame({
        "plant_id": pl["plant_code"], "plant_name": pl["plant_name"], "plant_type": pl["plant_type"],
        "country": pl["country"], "city": pl["city"], "monthly_capacity_units": pl["monthly_capacity_units"],
        "opened_year": pl["opened_year"],
    })

    r = s["silver_regions"]
    g["dim_region"] = pd.DataFrame({
        "region_code": r["region_code"], "region_name": r["region_name"], "country": r["country"],
        "market_cluster": r["market_cluster"], "currency": r["currency"], "fx_to_usd": r["fx_to_usd"],
    })

    # ---- fact_feedback (reviews + tickets) ----------------------------------------
    rv = s["silver_reviews"]
    f_rev = pd.DataFrame({
        "feedback_id": rv["review_id"], "source": "review", "feedback_date": rv["review_date"],
        "product_id": rv["product_code"], "region_code": rv["region_code"],
        "customer_id": rv["customer_id"], "channel": rv["platform"], "language": rv["language"],
        "rating": rv["rating"], "is_pet_owner": rv["pet_owner"], "pet_owner_source": rv["pet_owner_source"],
        "topic": rv["topic"], "sentiment_score": rv["sentiment_score"], "sentiment_label": rv["sentiment_label"],
        "title": rv["title"], "feedback_text": rv["review_text"], "verified_purchase": rv["verified_purchase"],
        "helpful_votes": rv["helpful_votes"], "ticket_priority": None, "ticket_status": None,
        "csat_score": pd.Series(pd.NA, index=rv.index, dtype="Int64"),
    })
    tk = s["silver_tickets"]
    f_tk = pd.DataFrame({
        "feedback_id": tk["ticket_id"], "source": "ticket", "feedback_date": tk["created_at"].dt.normalize(),
        "product_id": tk["product_code"], "region_code": tk["region_code"],
        "customer_id": tk["customer_id"], "channel": tk["contact_channel"], "language": tk["language"],
        "rating": pd.Series(pd.NA, index=tk.index, dtype="Int64"), "is_pet_owner": tk["pet_owner"],
        "pet_owner_source": tk["pet_owner_source"], "topic": tk["topic"],
        "sentiment_score": tk["sentiment_score"], "sentiment_label": tk["sentiment_label"],
        "title": tk["subject"], "feedback_text": tk["description"], "verified_purchase": None,
        "helpful_votes": pd.Series(pd.NA, index=tk.index, dtype="Int64"),
        "ticket_priority": tk["priority"], "ticket_status": tk["status"], "csat_score": tk["csat_score"],
    })
    ff = pd.concat([f_rev, f_tk], ignore_index=True)
    ff["date_key"] = date_key(ff["feedback_date"])
    ff["year_month"] = year_month(ff["feedback_date"])
    ff["is_negative"] = ff["sentiment_label"] == "negative"
    g["fact_feedback"] = ff[[
        "feedback_id", "source", "feedback_date", "date_key", "year_month", "product_id", "region_code",
        "customer_id", "channel", "language", "rating", "is_pet_owner", "pet_owner_source", "topic",
        "sentiment_score", "sentiment_label", "is_negative", "title", "feedback_text", "verified_purchase",
        "helpful_votes", "ticket_priority", "ticket_status", "csat_score"]]

    # ---- fact_sales ---------------------------------------------------------------
    so = s["silver_sales"]
    g["fact_sales"] = pd.DataFrame({
        "order_line_id": so["order_line_id"], "sales_date": so["order_date"],
        "date_key": date_key(so["order_date"]), "year_month": year_month(so["order_date"]),
        "product_id": so["product_code"], "region_code": so["region_code"], "channel": so["channel"],
        "plant_id": so["plant_code"], "units_sold": so["units"], "unit_price_local": so["unit_price_local"],
        "currency": so["currency"], "gross_revenue_usd": so["gross_revenue_usd"],
        "discount_pct": so["discount_pct"], "net_revenue_usd": so["net_revenue_usd"],
    })

    # ---- fact_bom_cost (product x component x month) -------------------------------
    months = pd.DataFrame({"month": pd.date_range(WINDOW_START, WINDOW_END, freq="MS")})
    months["month_end"] = months["month"] + pd.offsets.MonthEnd(0)
    bom = s["silver_bom"].merge(
        p[["product_code", "launch_date", "discontinue_date"]], on="product_code", how="inner")
    x = bom.merge(months, how="cross")
    x = x[(x["effective_from"] <= x["month"]) & (x["effective_to"].isna() | (x["effective_to"] >= x["month"]))
          & (x["launch_date"] <= x["month_end"])
          & (x["discontinue_date"].isna() | (x["discontinue_date"] >= x["month"]))]
    cc = s["silver_component_costs"][["month", "component_code", "unit_cost_usd", "primary_supplier_id"]]
    x = x.merge(cc, on=["month", "component_code"], how="left")
    x = x.sort_values(["month", "product_code", "component_code"])
    g["fact_bom_cost"] = pd.DataFrame({
        "month": x["month"], "year_month": year_month(x["month"]), "product_id": x["product_code"],
        "component_id": x["component_code"], "supplier_id": x["primary_supplier_id"],
        "bom_version": x["bom_version"], "quantity_per_unit": x["quantity"],
        "unit_cost_usd": x["unit_cost_usd"],
        "extended_cost_usd": round_half_up(x["quantity"] * x["unit_cost_usd"], 4),
    }).reset_index(drop=True)

    # ---- fact_supplier_capacity ----------------------------------------------------
    cap = s["silver_supplier_capacity"].copy()
    active = cap["committed_units"].fillna(0) > 0
    counts = cap[active].groupby(["month", "component_code"]).size().rename("supplier_count_for_component")
    cap = cap.merge(counts.reset_index(), on=["month", "component_code"], how="left")
    cap["supplier_count_for_component"] = cap["supplier_count_for_component"].fillna(0).astype(int)
    cap["is_single_source"] = cap["supplier_count_for_component"] == 1
    u = cap["utilisation_pct"]
    cap["risk_level"] = np.where((u >= 90) | (cap["is_single_source"] & (u >= 80)), "high",
                                 np.where((u >= 75) | cap["is_single_source"], "medium", "low"))
    g["fact_supplier_capacity"] = pd.DataFrame({
        "month": cap["month"], "year_month": year_month(cap["month"]), "supplier_id": cap["supplier_id"],
        "component_id": cap["component_code"], "capacity_units": cap["capacity_units"],
        "committed_units": cap["committed_units"], "utilisation_pct": cap["utilisation_pct"],
        "lead_time_days": cap["lead_time_days"],
        "alt_supplier_qualification_days": cap["alt_supplier_qualification_days"],
        "alt_supplier_candidate_id": cap["alt_supplier_candidate_id"],
        "supplier_count_for_component": cap["supplier_count_for_component"],
        "is_single_source": cap["is_single_source"], "risk_level": cap["risk_level"],
    })

    # ---- fact_logistics ------------------------------------------------------------
    sh = s["silver_shipments"]
    transit = (sh["delivery_date"] - sh["ship_date"]).dt.days.astype("Int64")
    on_time = pd.Series(pd.NA, index=sh.index, dtype="boolean")
    has = transit.notna()
    on_time[has] = (transit[has] <= sh["planned_transit_days"][has]).astype(bool)
    g["fact_logistics"] = pd.DataFrame({
        "shipment_id": sh["shipment_id"], "ship_date": sh["ship_date"], "date_key": date_key(sh["ship_date"]),
        "year_month": year_month(sh["ship_date"]), "delivery_date": sh["delivery_date"],
        "origin_plant_id": sh["origin_plant_code"], "destination_region_code": sh["destination_region_code"],
        "product_id": sh["product_code"], "transport_mode": sh["transport_mode"],
        "carrier_name": sh["carrier_name"], "units": sh["units"], "weight_kg": sh["weight_kg"],
        "distance_km": sh["distance_km"], "freight_cost_usd": sh["freight_cost_usd"],
        "freight_cost_per_kg_usd": round_half_up(sh["freight_cost_usd"] / sh["weight_kg"], 4),
        "freight_cost_per_unit_usd": round_half_up(sh["freight_cost_usd"] / sh["units"].astype("float64"), 4),
        "co2e_kg": sh["co2e_kg"], "planned_transit_days": sh["planned_transit_days"],
        "actual_transit_days": transit, "delay_days": transit - sh["planned_transit_days"],
        "is_on_time": on_time, "shipment_status": np.where(sh["delivery_date"].isna(), "in_transit", "delivered"),
    })

    # ---- fact_market_signal --------------------------------------------------------
    ms = s["silver_market_signals"]
    g["fact_market_signal"] = pd.DataFrame({
        "month": ms["month"], "year_month": year_month(ms["month"]), "region_code": ms["region_code"],
        "category": ms["category"], "metric": ms["metric"], "value": ms["value"], "unit": ms["unit"],
        "source": ms["source"],
    })

    # ---- fact_warranty -------------------------------------------------------------
    wc = s["silver_warranty"]
    g["fact_warranty"] = pd.DataFrame({
        "claim_id": wc["claim_id"], "claim_date": wc["claim_date"], "date_key": date_key(wc["claim_date"]),
        "year_month": year_month(wc["claim_date"]), "product_id": wc["product_code"],
        "region_code": wc["region_code"], "customer_id": wc["customer_id"], "is_pet_owner": wc["pet_owner"],
        "component_id": wc["failed_component_code"], "failure_mode": wc["failure_mode"],
        "repair_action": wc["repair_action"], "claim_status": wc["claim_status"],
        "claim_cost_usd": wc["claim_cost_usd"], "purchase_date": wc["purchase_date"],
        "days_in_service": wc["days_in_service"],
    })
    return {k: v.reset_index(drop=True) for k, v in g.items()}


# --------------------------------------------------------------------------------------
# SQLite helpers (to execute the Spark SQL example queries locally)
# --------------------------------------------------------------------------------------
def to_sqlite(gold: dict[str, pd.DataFrame], conn) -> None:
    """Load gold frames into SQLite: dates -> 'YYYY-MM-DD' text, booleans -> 0/1."""
    for name, df in gold.items():
        out = df.copy()
        for col in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[col]):
                out[col] = out[col].dt.strftime("%Y-%m-%d")
            elif pd.api.types.is_bool_dtype(out[col]) or str(out[col].dtype) == "boolean":
                out[col] = out[col].astype("Int64")
            elif out[col].dtype == object:
                vals = out[col].dropna()
                if len(vals) and vals.map(lambda v: isinstance(v, (bool, np.bool_))).all():
                    out[col] = out[col].map(lambda v: None if v is None or v is pd.NA else int(v))
        out.to_sql(name, conn, index=False, if_exists="replace")


def build_all(bronze_dir: Path):
    silver = build_silver(Path(bronze_dir))
    gold = build_gold(silver)
    return silver, gold
