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
        r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)",
        str(text),
        flags=re.IGNORECASE,
    )

    return sum(float(x.replace(",", "")) for x in matches)

def read_order_payments(uploaded_file):
    try:
        return pd.read_excel(uploaded_file, sheet_name="Order Payments", header=1)
    except:
        st.error("Could not read 'Order Payments' sheet.")
        st.stop()

# =====================================================
# PURCHASE COST MAP
# =====================================================

PURCHASE_COST_MAP = {
    clean_sku("MirrorBlue1"): 850,
    clean_sku("BH-221 Red NEW 1299"): 850,
    clean_sku("BH-221 Purple NEW 1299"): 850,
    clean_sku("HB-221 Red"): 850,
    clean_sku("HB-221 Purple"): 850,
    clean_sku("221 Red"): 850,
    clean_sku("221 Purple"): 850,

    clean_sku("HB-103 INDIGO"): 550,
    clean_sku("HB-103 INDIGO NEW"): 550,
    clean_sku("HB-103 RAMA"): 550,
    clean_sku("HB-103 RAMA NEW"): 550,
    clean_sku("HB-103 PINK"): 550,
    clean_sku("HB-103 PINK NEW"): 550,
    clean_sku("HB-103 YELLOW"): 550,
    clean_sku("HB-103 YELLOW NEW"): 550,

    clean_sku("PS124 Black"): 650,
    clean_sku("PS124 Pink"): 650,
    clean_sku("PS124 Rama"): 650,
}

# =====================================================
# FILES
# =====================================================

with st.sidebar:
    st.header("Uploads")
    orders_file = st.file_uploader("Upload Meesho PNL Excel", type=["xlsx"])
    claims_file = st.file_uploader("Upload Claims CSV (Optional)", type=["csv"])

if not orders_file:
    st.info("Upload your Meesho Excel file.")
    st.stop()

# =====================================================
# LOAD DATA
# =====================================================

df = read_order_payments(orders_file)

sku_col = "Supplier SKU"
product_col = "Product Name"
status_col = "Live Order Status"
settlement_col = "Final Settlement Amount"
payment_date_col = "Payment Date"
order_date_col = "Order Date"

require_columns(
    df,
    [sku_col, product_col, status_col, settlement_col],
    "Order Payments"
)

df = df.dropna(subset=[sku_col]).copy()

df[sku_col] = df[sku_col].astype(str).str.strip()
df[product_col] = df[product_col].fillna("").astype(str).str.strip()
df["Normalized Status"] = df[status_col].apply(normalize_status)

df[settlement_col] = pd.to_numeric(
    df[settlement_col],
    errors="coerce"
).fillna(0)

df[payment_date_col] = pd.to_datetime(df[payment_date_col], errors="coerce")
df[order_date_col] = pd.to_datetime(df[order_date_col], errors="coerce")

df["Purchase Cost"] = df[sku_col].apply(
    lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
)

# =====================================================
# FIXED COST LOGIC
# =====================================================
# Delivered / Shipped / Cancelled charge cost
# BUT if row is a large negative return adjustment,
# reverse purchase cost so no double charge happens.

base_cost_status = ["Delivered", "Shipped", "Cancelled"]

df["Cost Qty"] = df["Normalized Status"].isin(base_cost_status).astype(int)

# detect negative return reversal rows
# if negative value magnitude >= 70% of purchase cost
# assume this row represents returned item refund cycle

df["Reverse Cost Qty"] = (
    (df[settlement_col] < 0) &
    (
        abs(df[settlement_col]) >= (df["Purchase Cost"] * 0.70)
    ) &
    (df["Purchase Cost"] > 0)
).astype(int)

# final cost qty
df["Net Cost Qty"] = df["Cost Qty"] - df["Reverse Cost Qty"]

# never below zero
df["Net Cost Qty"] = df["Net Cost Qty"].clip(lower=0)

df["Total Purchase Cost"] = (
    df["Net Cost Qty"] * df["Purchase Cost"]
)

df["Actual Profit"] = (
    df[settlement_col] - df["Total Purchase Cost"]
)

# =====================================================
# TOTALS
# =====================================================

positive_settlement = df.loc[df[settlement_col] > 0, settlement_col].sum()
return_deduction = abs(df.loc[df[settlement_col] < 0, settlement_col].sum())
net_settlement = df[settlement_col].sum()
total_purchase_cost = df["Total Purchase Cost"].sum()
sales_actual_profit = df["Actual Profit"].sum()

# =====================================================
# KPI
# =====================================================

st.subheader("Executive Summary")

k1, k2, k3, k4 = st.columns(4)

k1.metric("Gross Positive", money(positive_settlement))
k2.metric("Negative Entries", money(return_deduction))
k3.metric("Purchase Cost", money(total_purchase_cost))
k4.metric("Net Profit", money(sales_actual_profit))

# =====================================================
# SKU TABLE
# =====================================================

status_counts = (
    df.pivot_table(
        index=sku_col,
        columns="Normalized Status",
        values=settlement_col,
        aggfunc="size",
        fill_value=0
    ).reset_index()
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
        Cost_Qty=("Net Cost Qty", "sum"),
        Total_Purchase_Cost=("Total Purchase Cost", "sum"),
        Actual_Profit=("Actual Profit", "sum"),
    )
    .reset_index()
)

sku_summary = sku_summary.merge(status_counts, on=sku_col, how="left")

sku_summary["Effective Delivered"] = (
    sku_summary["Delivered"] + sku_summary["Shipped"]
)

denominator = (
    sku_summary["Effective Delivered"]
    + sku_summary["Return"]
    + sku_summary["RTO"]
).replace(0, pd.NA)

sku_summary["Return %"] = (
    sku_summary["Return"] / denominator * 100
).fillna(0).round(2)

sku_summary["RTO %"] = (
    sku_summary["RTO"] / denominator * 100
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

st.subheader("SKU Profit Table")

st.dataframe(
    sku_summary[display_cols]
    .sort_values("Actual_Profit", ascending=False)
    .reset_index(drop=True),
    use_container_width=True
)

# =====================================================
# RAW DATA
# =====================================================

st.subheader("Processed Raw Data")

st.dataframe(df.reset_index(drop=True), use_container_width=True)
