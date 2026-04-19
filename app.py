import re

import pandas as pd
import streamlit as st


# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(page_title="Meesho Seller PNL Dashboard", layout="wide")

st.title("Meesho Seller PNL Dashboard")


# =====================================================
# HELPERS
# =====================================================

def clean_sku(x):
    return str(x).strip().lower()


def money(value):
    return f"Rs. {value:,.2f}"


def require_columns(dataframe, required_columns, source_name):
    missing = [col for col in required_columns if col not in dataframe.columns]
    if missing:
        st.error(f"{source_name} is missing required columns: {', '.join(missing)}")
        st.stop()


def normalize_status(value):
    text = str(value).strip().lower()

    if not text or text == "nan":
        return "Blank"
    if "deliver" in text:
        return "Delivered"
    if "ship" in text:
        return "Shipped"
    if "return" in text:
        return "Return"
    if "rto" in text:
        return "RTO"
    if "cancel" in text:
        return "Cancelled"
    if "exchange" in text:
        return "Exchange"

    return str(value).strip()


def extract_claim_amount(text):
    if pd.isna(text):
        return 0.0

    matches = re.findall(
        r"(?:Rs\.?|INR|\u20b9)\s*([\d,]+(?:\.\d+)?)",
        str(text),
        flags=re.IGNORECASE,
    )

    return sum(float(amount.replace(",", "")) for amount in matches)


def read_order_payments(uploaded_file):
    try:
        return pd.read_excel(uploaded_file, sheet_name="Order Payments", header=1)
    except ValueError:
        st.error("Could not find the 'Order Payments' sheet in this Excel file.")
        st.stop()


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
# FILE UPLOADERS
# =====================================================

with st.sidebar:
    st.header("Uploads")
    orders_file = st.file_uploader("Upload Meesho PNL Excel", type=["xlsx"])
    claims_file = st.file_uploader("Upload Claims CSV (Optional)", type=["csv"])

    st.caption("Ads and referral sheets are ignored as requested.")


if not orders_file:
    st.info("Upload your Meesho PNL Excel file to begin.")
    st.stop()


# =====================================================
# ORDER PAYMENTS
# =====================================================

df = read_order_payments(orders_file)

sku_col = "Supplier SKU"
product_col = "Product Name"
status_col = "Live Order Status"
settlement_col = "Final Settlement Amount"
payment_date_col = "Payment Date"
order_date_col = "Order Date"

required_order_columns = [
    sku_col,
    product_col,
    status_col,
    settlement_col,
    payment_date_col,
    order_date_col,
]

require_columns(df, required_order_columns, "Order Payments sheet")

df = df.dropna(subset=[sku_col]).copy()

df[sku_col] = df[sku_col].astype(str).str.strip()
df[product_col] = df[product_col].fillna("").astype(str).str.strip()
df["Normalized Status"] = df[status_col].apply(normalize_status)
df[settlement_col] = pd.to_numeric(df[settlement_col], errors="coerce").fillna(0)
df[payment_date_col] = pd.to_datetime(df[payment_date_col], errors="coerce")
df[order_date_col] = pd.to_datetime(df[order_date_col], errors="coerce")

df["Purchase Cost"] = df[sku_col].apply(lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0))

# Business rule from user:
# Delivered, Shipped, and Cancelled consume purchase cost.
# Shipped is treated as delivered because it is a Meesho status glitch.
# RTO is count-only. Returns reduce settlement but do not add another purchase cost here.
cost_statuses = ["Delivered", "Shipped", "Cancelled"]
df["Cost Qty"] = df["Normalized Status"].isin(cost_statuses).astype(int)
df["Total Purchase Cost"] = df["Cost Qty"] * df["Purchase Cost"]
df["Actual Profit"] = df[settlement_col] - df["Total Purchase Cost"]

df["Effective Delivered Qty"] = df["Normalized Status"].isin(["Delivered", "Shipped"]).astype(int)
df["Return Qty"] = (df["Normalized Status"] == "Return").astype(int)
df["RTO Qty"] = (df["Normalized Status"] == "RTO").astype(int)
df["Cancelled Qty"] = (df["Normalized Status"] == "Cancelled").astype(int)
df["Exchange Qty"] = (df["Normalized Status"] == "Exchange").astype(int)
df["Blank Status Qty"] = (df["Normalized Status"] == "Blank").astype(int)

positive_settlement = df.loc[df[settlement_col] > 0, settlement_col].sum()
return_deduction = abs(df.loc[df[settlement_col] < 0, settlement_col].sum())
net_settlement = df[settlement_col].sum()
total_purchase_cost = df["Total Purchase Cost"].sum()
sales_actual_profit = df["Actual Profit"].sum()


# =====================================================
# CLAIMS SECTION
# =====================================================

sku_claims = pd.DataFrame()
net_claim = 0.0

if claims_file:
    claims = pd.read_csv(claims_file)

    claim_sku_col = "SKU"
    claim_status_col = "Ticket Status"
    claim_update_col = "Last Update"

    require_columns(
        claims,
        [claim_sku_col, claim_status_col, claim_update_col],
        "Claims CSV",
    )

    claims[claim_sku_col] = claims[claim_sku_col].astype(str).str.strip()
    claims[claim_status_col] = claims[claim_status_col].fillna("").astype(str).str.strip()
    claims["Claim Amount"] = claims[claim_update_col].apply(extract_claim_amount)

    approved = claims[
        claims[claim_status_col].str.contains("approved", case=False, na=False)
    ].copy()
    rejected = claims[
        claims[claim_status_col].str.contains("rejected", case=False, na=False)
    ].copy()

    approved_grp = (
        approved.groupby(claim_sku_col)
        .agg(
            Approved_Qty=(claim_sku_col, "count"),
            Claim_Received=("Claim Amount", "sum"),
        )
        .reset_index()
    )

    rejected_grp = (
        rejected.groupby(claim_sku_col)
        .agg(Rejected_Qty=(claim_sku_col, "count"))
        .reset_index()
    )

    sku_claims = approved_grp.merge(
        rejected_grp,
        on=claim_sku_col,
        how="outer",
    ).fillna(0)

    sku_claims["Purchase Cost"] = sku_claims[claim_sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    sku_claims["Approved Profit"] = (
        sku_claims["Claim_Received"]
        - sku_claims["Approved_Qty"] * sku_claims["Purchase Cost"]
    )

    sku_claims["Rejected Loss"] = (
        sku_claims["Rejected_Qty"] * sku_claims["Purchase Cost"]
    )

    sku_claims["Net Claim"] = (
        sku_claims["Approved Profit"] - sku_claims["Rejected Loss"]
    )

    net_claim = sku_claims["Net Claim"].sum()


final_profit = sales_actual_profit + net_claim


# =====================================================
# EXECUTIVE SUMMARY
# =====================================================

st.subheader("Executive Summary")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Final Profit", money(final_profit))
kpi2.metric("Money Received", money(net_settlement))
kpi3.metric("Purchase Cost", money(total_purchase_cost))
kpi4.metric("Net Claims", money(net_claim))

kpi5, kpi6, kpi7, kpi8 = st.columns(4)
kpi5.metric("Gross Positive Settlement", money(positive_settlement))
kpi6.metric("Return Deductions", money(return_deduction))
kpi7.metric("Sales Profit Before Claims", money(sales_actual_profit))
kpi8.metric("Total Orders", f"{len(df):,}")


# =====================================================
# WARNINGS
# =====================================================

missing_cost = df[df["Purchase Cost"] == 0][[sku_col, product_col]].drop_duplicates()
blank_status_count = int(df["Blank Status Qty"].sum())

if not missing_cost.empty:
    st.warning("Some SKUs do not have purchase cost mapped. Their cost is currently counted as ₹0.")
    st.dataframe(missing_cost, use_container_width=True)

if blank_status_count:
    st.warning(f"{blank_status_count} rows have blank order status. They are included in settlement but not in purchase cost.")


# =====================================================
# SKU PERFORMANCE
# =====================================================

st.subheader("SKU Profit Table")

status_counts = (
    df.pivot_table(
        index=sku_col,
        columns="Normalized Status",
        values=settlement_col,
        aggfunc="size",
        fill_value=0,
    )
    .reset_index()
)

status_counts.columns.name = None

for col in ["Delivered", "Shipped", "Return", "RTO", "Cancelled", "Exchange", "Blank"]:
    if col not in status_counts.columns:
        status_counts[col] = 0

sku_summary = (
    df.groupby(sku_col)
    .agg(
        Product_Name=(product_col, "first"),
        Gross_Positive_Settlement=(settlement_col, lambda s: s[s > 0].sum()),
        Return_Deduction=(settlement_col, lambda s: abs(s[s < 0].sum())),
        Net_Settlement=(settlement_col, "sum"),
        Purchase_Cost_Per_Piece=("Purchase Cost", "max"),
        Total_Purchase_Cost=("Total Purchase Cost", "sum"),
        Actual_Profit=("Actual Profit", "sum"),
        Cost_Qty=("Cost Qty", "sum"),
    )
    .reset_index()
)

sku_summary = sku_summary.merge(status_counts, on=sku_col, how="left")
sku_summary["Effective Delivered"] = sku_summary["Delivered"] + sku_summary["Shipped"]

denominator = (
    sku_summary["Effective Delivered"]
    + sku_summary["Return"]
    + sku_summary["RTO"]
)

safe_denominator = denominator.where(denominator != 0)

sku_summary["Return %"] = (
    (sku_summary["Return"] / safe_denominator) * 100
).fillna(0).round(2)

sku_summary["RTO %"] = (
    (sku_summary["RTO"] / safe_denominator) * 100
).fillna(0).round(2)

display_cols = [
    sku_col,
    "Product_Name",
    "Effective Delivered",
    "Delivered",
    "Shipped",
    "Return",
    "RTO",
    "Cancelled",
    "Exchange",
    "Blank",
    "Gross_Positive_Settlement",
    "Return_Deduction",
    "Net_Settlement",
    "Purchase_Cost_Per_Piece",
    "Cost_Qty",
    "Total_Purchase_Cost",
    "Actual_Profit",
    "Return %",
    "RTO %",
]

st.dataframe(
    sku_summary[display_cols]
    .sort_values("Actual_Profit", ascending=False)
    .reset_index(drop=True),
    use_container_width=True,
)


# =====================================================
# STATUS BREAKDOWN
# =====================================================

st.subheader("Status Breakdown")

status_summary = (
    df.groupby("Normalized Status")
    .agg(
        Orders=(sku_col, "count"),
        Net_Settlement=(settlement_col, "sum"),
        Purchase_Cost=("Total Purchase Cost", "sum"),
        Actual_Profit=("Actual Profit", "sum"),
    )
    .reset_index()
    .sort_values("Orders", ascending=False)
)

st.dataframe(status_summary, use_container_width=True)


# =====================================================
# MONTHLY TREND
# =====================================================

st.subheader("Monthly Trend by Payment Date")

trend = df.dropna(subset=[payment_date_col]).copy()
trend["Payment Month"] = trend[payment_date_col].dt.to_period("M").astype(str)

monthly_trend = (
    trend.groupby("Payment Month")
    .agg(
        Orders=(sku_col, "count"),
        Net_Settlement=(settlement_col, "sum"),
        Purchase_Cost=("Total Purchase Cost", "sum"),
        Actual_Profit=("Actual Profit", "sum"),
    )
    .reset_index()
)

if monthly_trend.empty:
    st.info("No payment dates were found for monthly trend.")
else:
    st.line_chart(
        monthly_trend.set_index("Payment Month")[["Net_Settlement", "Actual_Profit"]]
    )
    st.dataframe(monthly_trend, use_container_width=True)


# =====================================================
# CLAIMS ANALYSIS
# =====================================================

st.subheader("Claims Analysis")

if claims_file:
    claim_kpi1, claim_kpi2, claim_kpi3 = st.columns(3)
    claim_kpi1.metric("Claim Received", money(sku_claims["Claim_Received"].sum()))
    claim_kpi2.metric("Rejected Loss", money(sku_claims["Rejected Loss"].sum()))
    claim_kpi3.metric("Net Claim", money(net_claim))

    st.dataframe(
        sku_claims.sort_values("Net Claim", ascending=False).reset_index(drop=True),
        use_container_width=True,
    )

    missing_claim_cost = sku_claims[sku_claims["Purchase Cost"] == 0][claim_sku_col].drop_duplicates()
    if not missing_claim_cost.empty:
        st.warning("Some claim SKUs do not have purchase cost mapped.")
        st.dataframe(missing_claim_cost, use_container_width=True)
else:
    st.info("Upload a claims CSV to calculate approved profit, rejected loss, and net claim.")


# =====================================================
# RAW DATA AND DOWNLOADS
# =====================================================

st.subheader("Raw Processed Order Data")

processed_cols = [
    sku_col,
    product_col,
    order_date_col,
    payment_date_col,
    status_col,
    "Normalized Status",
    settlement_col,
    "Purchase Cost",
    "Cost Qty",
    "Total Purchase Cost",
    "Actual Profit",
]

st.dataframe(df[processed_cols].reset_index(drop=True), use_container_width=True)

st.download_button(
    "Download SKU Summary CSV",
    sku_summary.to_csv(index=False).encode("utf-8"),
    file_name="meesho_sku_summary.csv",
    mime="text/csv",
)

st.download_button(
    "Download Processed Orders CSV",
    df[processed_cols].to_csv(index=False).encode("utf-8"),
    file_name="meesho_processed_orders.csv",
    mime="text/csv",
)
