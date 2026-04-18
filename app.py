import streamlit as st
import pandas as pd
import re

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(page_title="Meesho Seller Dashboard", layout="wide")
st.title("📊 Meesho Seller Master Dashboard")

# =====================================================
# HELPERS
# =====================================================

def clean_sku(x):
    return str(x).strip().lower()

# =====================================================
# PURCHASE COST MAP
# =====================================================

PURCHASE_COST_MAP = {
    clean_sku("MirrorBlue1"): 850,
    clean_sku("HIRVA-221 PURPLE NEW 1299"): 850,
    clean_sku("HB-221 Purple"): 850,
    clean_sku("HB-221 Red"): 850,
    clean_sku("HIRVA-221 RED NEW 1299"): 850,
    clean_sku("mirror - blue"): 850,
    clean_sku("MIRROR YELLOW"): 850,

    clean_sku("PS124 Black"): 650,
    clean_sku("PS124 Pink"): 650,
    clean_sku("PS124 Rama"): 650,

    clean_sku("HB-103 INDIGO NEW"): 550,
    clean_sku("HB-103 RAMA NEW"): 550,
    clean_sku("HB-103 WINE NEW"): 550,
    clean_sku("HB-103 PINK NEW"): 550,
    clean_sku("HB-103 YELLOW NEW"): 550,
    clean_sku("HB-103 RAMA"): 550,
    clean_sku("HB-103 YELLOW"): 550,
    clean_sku("HB-103 PURPLE"): 550,
    clean_sku("HB-103 PINK"): 550,
    clean_sku("HB-103 INDIGO"): 550,

    clean_sku("BH-221 Red NEW 1299"): 850,
    clean_sku("BH-221 Purple NEW 1299"): 850,

    clean_sku("221-Unstiched-Purple"): 450,
    clean_sku("221-Unstiched-Red"): 480,

    clean_sku("221 Red XXL"): 850,
    clean_sku("221 Purple XXL"): 850,
    clean_sku("221 Red"): 850,
    clean_sku("221 Purple"): 850,

    clean_sku("H-201 maroon"): 550,
    clean_sku("103-Unstiched-Yellow"): 450,
    clean_sku("103-Unstiched-Rama"): 450,
}

KNOWN_STATUS = {
    "Delivered",
    "Return",
    "RTO",
    "Shipped",
    "Cancelled",
    "Exchange"
}

# =====================================================
# FILE UPLOAD
# =====================================================

orders_file = st.file_uploader("Upload Order Payments Excel", type=["xlsx"])
claims_file = st.file_uploader("Upload Claims CSV (Optional)", type=["csv"])

summary = None

# =====================================================
# ORDER PAYMENTS
# =====================================================

if orders_file:

    df = pd.read_excel(
        orders_file,
        sheet_name="Order Payments",
        header=1
    )

    sku_col = "Supplier SKU"
    status_col = "Live Order Status"
    settlement_col = "Final Settlement Amount"

    df = df.dropna(subset=[sku_col]).copy()

    df[sku_col] = df[sku_col].astype(str).str.strip()
    df[status_col] = df[status_col].fillna("").astype(str).str.strip()
    df[settlement_col] = pd.to_numeric(
        df[settlement_col],
        errors="coerce"
    ).fillna(0)

    # =================================================
    # KPI TOTALS
    # =================================================

    positive_total = df[df[settlement_col] > 0][settlement_col].sum()
    negative_total = abs(df[df[settlement_col] < 0][settlement_col].sum())
    net_total = df[settlement_col].sum()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Revenue ₹", round(positive_total, 2))
    c2.metric("Returns ₹", round(negative_total, 2))
    c3.metric("Net Settlement ₹", round(net_total, 2))

    if round(positive_total - negative_total, 2) == round(net_total, 2):
        c4.metric("Validation", "Matched ✅")
    else:
        c4.metric("Validation", "Mismatch ❌")

    # =================================================
    # SKU LEVEL SUMMARY
    # =================================================

    revenue = (
        df[df[settlement_col] > 0]
        .groupby(sku_col)[settlement_col]
        .sum()
        .reset_index(name="Revenue")
    )

    returns = (
        df[df[settlement_col] < 0]
        .groupby(sku_col)[settlement_col]
        .sum()
        .abs()
        .reset_index(name="Returns")
    )

    payout = (
        df.groupby(sku_col)[settlement_col]
        .sum()
        .reset_index(name="Net Settlement")
    )

    # =================================================
    # COUNTS
    # =================================================

    counts = (
        df.pivot_table(
            index=sku_col,
            columns=status_col,
            aggfunc="size",
            fill_value=0
        )
        .reset_index()
    )

    counts.columns.name = None

    needed_cols = [
        "Delivered",
        "Return",
        "RTO",
        "Shipped",
        "Cancelled",
        "Exchange"
    ]

    for col in needed_cols:
        if col not in counts.columns:
            counts[col] = 0

    # =================================================
    # MERGE
    # =================================================

    summary = counts.merge(revenue, on=sku_col, how="left")
    summary = summary.merge(returns, on=sku_col, how="left")
    summary = summary.merge(payout, on=sku_col, how="left")
    summary = summary.fillna(0)

    # =================================================
    # PURCHASE COST
    # =================================================

    summary["Purchase Cost"] = summary[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    # cancelled now charged purchase cost also
    summary["Total Purchase"] = (
        (
            summary["Delivered"] +
            summary["Shipped"] +
            summary["Cancelled"]
        )
        * summary["Purchase Cost"]
    )

    # =================================================
    # REAL PROFIT
    # =================================================

    summary["Net Profit"] = (
        summary["Net Settlement"] -
        summary["Total Purchase"]
    )

    # =================================================
    # RETURN %
    # =================================================

    summary["Return %"] = (
        summary["Return"] /
        (
            summary["Delivered"] +
            summary["Shipped"] +
            summary["Return"]
        )
    ).replace([float("inf")], 0).fillna(0) * 100

    summary["Return %"] = summary["Return %"].round(2)

    # =================================================
    # VALIDATION
    # =================================================

    summary["Check"] = (
        round(summary["Revenue"] - summary["Returns"], 2)
        == round(summary["Net Settlement"], 2)
    )

    summary["Check"] = summary["Check"].map(
        {True: "✅", False: "❌"}
    )

    # =================================================
    # UNKNOWN SKU CHECK
    # =================================================

    summary["SKU Known"] = summary[sku_col].apply(
        lambda x: "✅"
        if clean_sku(x) in PURCHASE_COST_MAP
        else "⚠️ Unknown SKU"
    )

    # =================================================
    # UNKNOWN STATUS CHECK
    # =================================================

    unknown_status_df = df[
        (~df[status_col].isin(KNOWN_STATUS)) &
        (df[status_col] != "")
    ][[sku_col, status_col]].drop_duplicates()

    # =================================================
    # DISPLAY
    # =================================================

    st.subheader("📋 SKU Performance Table")

    st.dataframe(
        summary.sort_values(
            "Net Profit",
            ascending=False
        ).reset_index(drop=True),
        use_container_width=True
    )

    # =================================================
    # ALERTS
    # =================================================

    unknown_skus = summary[
        summary["SKU Known"] != "✅"
    ][[sku_col, "SKU Known"]]

    if len(unknown_skus) > 0:
        st.warning("⚠️ Unknown SKUs found. Please add purchase cost.")
        st.dataframe(unknown_skus, use_container_width=True)

    if len(unknown_status_df) > 0:
        st.warning("⚠️ Unknown statuses found. Please review.")
        st.dataframe(unknown_status_df, use_container_width=True)

# =====================================================
# CLAIMS
# =====================================================

if claims_file:

    st.divider()
    st.header("🧾 Claims Recovery Analysis")

    claims = pd.read_csv(claims_file)

    sku_col = "SKU"
    status_col = "Ticket Status"

    def extract_amount(text):
        if pd.isna(text):
            return 0

        nums = re.findall(
            r'Rs\.?\s*(\d+(?:\.\d+)?)',
            str(text)
        )

        return sum(float(x) for x in nums)

    claims["Claim Amount"] = claims["Last Update"].apply(extract_amount)

    approved = claims[claims[status_col] == "Approved"]
    rejected = claims[claims[status_col] == "Rejected"]

    approved_grp = (
        approved.groupby(sku_col)
        .agg(
            Approved_Qty=("SKU", "count"),
            Claim_Received=("Claim Amount", "sum")
        )
        .reset_index()
    )

    rejected_grp = (
        rejected.groupby(sku_col)
        .agg(
            Rejected_Qty=("SKU", "count")
        )
        .reset_index()
    )

    sku_claims = approved_grp.merge(
        rejected_grp,
        on=sku_col,
        how="outer"
    ).fillna(0)

    sku_claims["Purchase Cost"] = sku_claims[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    sku_claims["Approved Profit"] = (
        sku_claims["Claim_Received"]
        - (
            sku_claims["Approved_Qty"]
            * sku_claims["Purchase Cost"]
        )
    )

    sku_claims["Rejected Loss"] = (
        sku_claims["Rejected_Qty"]
        * sku_claims["Purchase Cost"]
    )

    sku_claims["Net Claim"] = (
        sku_claims["Approved Profit"]
        - sku_claims["Rejected Loss"]
    )

    st.subheader("📋 Claims Table")

    st.dataframe(
        sku_claims.sort_values(
            "Net Claim",
            ascending=False
        ).reset_index(drop=True),
        use_container_width=True
    )

    if summary is not None:

        final_total = (
            summary["Net Profit"].sum()
            + sku_claims["Net Claim"].sum()
        )

        st.divider()
        st.header("🏁 FINAL TOTAL PROFIT")
        st.metric("Sales + Claims ₹", round(final_total, 2))
