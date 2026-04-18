import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Meesho Seller Dashboard", layout="wide")

# =====================================================
# UI
# =====================================================

st.title("📊 Meesho Seller Master Dashboard")

# =====================================================
# HELPERS
# =====================================================

def clean_sku(x):
    return str(x).strip().lower()

def clean_status(x):
    return str(x).strip()

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

# =====================================================
# FILE UPLOAD
# =====================================================

orders_file = st.file_uploader("Upload Order Payments Excel", type=["xlsx"])

# =====================================================
# MAIN
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
    order_col = "Sub Order No"

    df = df.dropna(subset=[sku_col, order_col]).copy()

    df[status_col] = df[status_col].fillna("").astype(str).str.strip()
    df[settlement_col] = pd.to_numeric(df[settlement_col], errors="coerce").fillna(0)

    # =================================================
    # STATUS PRIORITY
    # =================================================

    priority = [
        "Delivered",
        "Shipped",
        "Return",
        "RTO",
        "Cancelled",
        "Exchange"
    ]

    def pick_status(series):
        vals = [x for x in series if x != ""]
        for p in priority:
            if p in vals:
                return p
        return "Unknown"

    # =================================================
    # GROUP BY SUB ORDER NO
    # THIS FIXES YOUR REVENUE ISSUE
    # =================================================

    final_df = (
        df.groupby(order_col)
        .agg({
            sku_col: "first",
            settlement_col: "sum",
            status_col: pick_status
        })
        .reset_index()
    )

    # =================================================
    # PROFIT
    # =================================================

    def calc_profit(row):
        sku = clean_sku(row[sku_col])
        status = row[status_col]
        settlement = row[settlement_col]
        cost = PURCHASE_COST_MAP.get(sku, 0)

        if status in ["Delivered", "Shipped"]:
            return settlement - cost
        else:
            return settlement

    final_df["Profit"] = final_df.apply(calc_profit, axis=1)

    # =================================================
    # COUNTS
    # =================================================

    counts = (
        final_df.pivot_table(
            index=sku_col,
            columns=status_col,
            aggfunc="size",
            fill_value=0
        )
        .reset_index()
    )

    counts.columns.name = None

    for col in ["Delivered", "Shipped", "Return", "RTO", "Cancelled", "Exchange"]:
        if col not in counts.columns:
            counts[col] = 0

    # =================================================
    # REVENUE FIXED
    # =================================================
    # Revenue = ONLY positive settlement from Delivered/Shipped
    # negative return adjustments excluded

    revenue = (
        final_df[
            (final_df[status_col].isin(["Delivered", "Shipped"])) &
            (final_df[settlement_col] > 0)
        ]
        .groupby(sku_col)[settlement_col]
        .sum()
        .reset_index(name="Revenue")
    )

    # =================================================
    # PROFIT
    # =================================================

    profit = (
        final_df.groupby(sku_col)["Profit"]
        .sum()
        .reset_index(name="Net Profit")
    )

    # =================================================
    # MERGE
    # =================================================

    summary = counts.merge(revenue, on=sku_col, how="left")
    summary = summary.merge(profit, on=sku_col, how="left")
    summary = summary.fillna(0).round(2)

    # =================================================
    # PURCHASE
    # =================================================

    summary["Purchase Cost"] = summary[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    summary["Total Purchase"] = (
        (summary["Delivered"] + summary["Shipped"]) *
        summary["Purchase Cost"]
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
    # KPIs
    # =================================================

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Delivered + Shipped",
        int(summary["Delivered"].sum() + summary["Shipped"].sum())
    )

    c2.metric(
        "Returns",
        int(summary["Return"].sum())
    )

    c3.metric(
        "Revenue ₹",
        round(summary["Revenue"].sum(), 2)
    )

    c4.metric(
        "Net Profit ₹",
        round(summary["Net Profit"].sum(), 2)
    )

    # =================================================
    # TABLE
    # =====================================================

    st.subheader("📋 SKU Performance Table")

    st.dataframe(
        summary.sort_values("Net Profit", ascending=False).reset_index(drop=True),
        use_container_width=True
    )
