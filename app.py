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

def find_date_column(df):
    possible = [
        "Payment Date",
        "Settlement Date",
        "Date",
        "Payment Initiation Date",
        "Payment Date "
    ]
    for col in possible:
        if col in df.columns:
            return col
    return None

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

# statuses where purchase cost should be charged
COST_STATUSES = [
    "Delivered",
    "Shipped",
    "Cancelled",
    "Exchange"
]

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

    date_col = find_date_column(df)

    df = df.dropna(subset=[sku_col]).copy()

    df[sku_col] = df[sku_col].astype(str).str.strip()
    df[status_col] = df[status_col].fillna("").astype(str).str.strip()
    df[settlement_col] = pd.to_numeric(
        df[settlement_col],
        errors="coerce"
    ).fillna(0)

    if date_col:
        df[date_col] = pd.to_datetime(
            df[date_col],
            errors="coerce"
        ).dt.date

    # =================================================
    # TOP KPI BOXES
    # =================================================

    total_revenue = df[df[settlement_col] > 0][settlement_col].sum()
    total_returns = abs(
        df[df[settlement_col] < 0][settlement_col].sum()
    )

    net_settlement = df[settlement_col].sum()

    # total purchase based on statuses
    df["Purchase Cost"] = df[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    df["Charge Cost"] = df[status_col].isin(COST_STATUSES)

    total_purchase = df[df["Charge Cost"]]["Purchase Cost"].sum()

    net_profit = (
        total_revenue -
        total_returns -
        total_purchase
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Net Settlement ₹", round(net_settlement, 2))
    c2.metric("Total Revenue ₹", round(total_revenue, 2))
    c3.metric("Total Returns ₹", round(total_returns, 2))
    c4.metric("Total Purchase ₹", round(total_purchase, 2))
    c5.metric("Net Profit ₹", round(net_profit, 2))

    # =================================================
    # SKU TABLE
    # =================================================

    counts = (
        df.pivot_table(
            index=sku_col,
            columns=status_col,
            aggfunc="size",
            fill_value=0
        ).reset_index()
    )

    counts.columns.name = None

    for col in [
        "Delivered",
        "RTO",
        "Return",
        "Shipped",
        "Cancelled",
        "Exchange"
    ]:
        if col not in counts.columns:
            counts[col] = 0

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

    summary = counts.merge(revenue, on=sku_col, how="left")
    summary = summary.merge(returns, on=sku_col, how="left")
    summary = summary.fillna(0)

    summary["Purchase Cost"] = summary[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    summary["Total Purchase"] = (
        (
            summary["Delivered"] +
            summary["Shipped"] +
            summary["Cancelled"] +
            summary["Exchange"]
        )
        * summary["Purchase Cost"]
    )

    summary["Net Profit"] = (
        summary["Revenue"] -
        summary["Returns"] -
        summary["Total Purchase"]
    )

    summary["Return %"] = (
        summary["Return"] /
        (
            summary["Delivered"] +
            summary["Shipped"] +
            summary["Return"]
        )
    ).replace([float("inf")], 0).fillna(0) * 100

    summary["Return %"] = summary["Return %"].round(2)

    final_cols = [
        sku_col,
        "Delivered",
        "RTO",
        "Return",
        "Shipped",
        "Revenue",
        "Returns",
        "Purchase Cost",
        "Total Purchase",
        "Net Profit",
        "Return %"
    ]

    st.subheader("📋 SKU Performance Table")

    st.dataframe(
        summary[final_cols]
        .sort_values("Net Profit", ascending=False)
        .reset_index(drop=True),
        use_container_width=True
    )

    # =================================================
    # DATE WISE SETTLEMENT
    # =================================================

    if date_col:

        date_summary = (
            df.groupby(date_col)[settlement_col]
            .sum()
            .reset_index(name="Net Settlement")
            .sort_values(date_col)
        )

        st.subheader("📅 Date Wise Net Settlement")

        st.dataframe(
            date_summary,
            use_container_width=True
        )

        # =============================================
        # VALIDATION
        # =============================================

        sku_total = summary["Net Profit"].sum()
        date_total = date_summary["Net Settlement"].sum()

        st.subheader("✅ Validation")

        if round(net_settlement, 2) == round(date_total, 2):
            st.success(
                f"Matched: SKU/Data Total = ₹{round(date_total,2)}"
            )
        else:
            st.error(
                f"Mismatch: SKU Total ₹{round(net_settlement,2)} vs Date Total ₹{round(date_total,2)}"
            )
