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
    return f"₹{value:,.2f}"


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
