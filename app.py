import re
import pandas as pd
import streamlit as st

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(page_title="Meesho Seller PNL Dashboard", layout="wide")
st.title("📊 Meesho Seller PNL Dashboard")

# =====================================================
# HELPERS
# =====================================================

def clean_sku(x):
    return str(x).strip().lower()

def money(x):
    return f"₹{x:,.2f}"

def normalize_status(value):
    txt = str(value).strip().lower()

    if txt == "" or txt == "nan":
        return "Blank"
    if "deliver" in txt:
        return "Delivered"
    if "ship" in txt:
        return "Shipped"
    if "return" in txt:
        return "Return"
    if "rto" in txt:
        return "RTO"
    if "cancel" in txt:
        return "Cancelled"
    if "exchange" in txt:
        return "Exchange"

    return str(value).strip()

# latest status priority
STATUS_PRIORITY = {
    "Return": 6,
    "Delivered": 5,
    "Shipped": 4,
    "Exchange": 3,
    "Cancelled": 2,
    "RTO": 1,
    "Blank": 0
}

def final_status(series):
    vals = [normalize_status(x) for x in series]
    vals = sorted(vals, key=lambda x: STATUS_PRIORITY.get(x, 0), reverse=True)
    return vals[0]

# =====================================================
# PURCHASE COST MAP
# =====================================================

PURCHASE_COST_MAP = {
    clean_sku("MirrorBlue1"): 850,
    clean_sku("mirror - blue"): 850,
    clean_sku("MIRROR YELLOW"): 850,
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
    clean_sku("HB-103 PURPLE"): 550,

    clean_sku("PS124 Black"): 650,
    clean_sku("PS124 Pink"): 650,
    clean_sku("PS124 Rama"): 650,

    clean_sku("221-Unstiched-Purple"): 450,
    clean_sku("221-Unstiched-Red"): 480,
}

# =====================================================
# FILE UPLOAD
# =====================================================

uploaded_file = st.file_uploader("Upload Meesho Excel", type=["xlsx"])

if not uploaded_file:
    st.stop()

# =====================================================
# LOAD FILE
# =====================================================

df = pd.read_excel(
    uploaded_file,
    sheet_name="Order Payments",
    header=1
)

# columns
sku_col = "Supplier SKU"
status_col = "Live Order Status"
settlement_col = "Final Settlement Amount"
suborder_col = "Sub Order No"

required = [sku_col, status_col, settlement_col, suborder_col]

for col in required:
    if col not in df.columns:
        st.error(f"Missing column: {col}")
        st.stop()

df = df.dropna(subset=[sku_col, suborder_col]).copy()

df[sku_col] = df[sku_col].astype(str).str.strip()
df[suborder_col] = df[suborder_col].astype(str).str.strip()

df[status_col] = df[status_col].fillna("").astype(str).str.strip()
df["Normalized Status"] = df[status_col].apply(normalize_status)

df[settlement_col] = pd.to_numeric(
    df[settlement_col],
    errors="coerce"
).fillna(0)

df["Purchase Cost"] = df[sku_col].apply(
    lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
)

# =====================================================
# DUPLICATE ORDER MERGE
# =====================================================
# combine same Sub Order No
# sum settlement
# take final strongest status

merged = (
    df.groupby(suborder_col)
    .agg(
        Supplier_SKU=(sku_col, "first"),
        Final_Status=("Normalized Status", final_status),
        Net_Settlement=(settlement_col, "sum"),
        Purchase_Cost=("Purchase Cost", "max")
    )
    .reset_index()
)

# =====================================================
# REVENUE / RETURNS
# =====================================================

merged["Revenue"] = merged["Net_Settlement"].apply(
    lambda x: x if x > 0 else 0
)

merged["Returns"] = merged["Net_Settlement"].apply(
    lambda x: abs(x) if x < 0 else 0
)

# =====================================================
# COST LOGIC
# =====================================================
# Return / RTO = no cost
# Delivered / Shipped / Cancelled / Exchange = charge cost

def cost_qty(status):
    if status in ["Delivered", "Shipped", "Cancelled", "Exchange"]:
        return 1
    return 0

merged["Cost Qty"] = merged["Final_Status"].apply(cost_qty)

merged["Total Purchase"] = (
    merged["Cost Qty"] * merged["Purchase_Cost"]
)

# =====================================================
# PROFIT
# =====================================================

merged["Net Profit"] = (
    merged["Net_Settlement"] - merged["Total Purchase"]
)

# =====================================================
# TOP KPIs
# =====================================================

total_revenue = merged["Revenue"].sum()
total_returns = merged["Returns"].sum()
total_settlement = merged["Net_Settlement"].sum()
total_purchase = merged["Total Purchase"].sum()
total_profit = merged["Net Profit"].sum()

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Net Settlement", money(total_settlement))
c2.metric("Total Revenue", money(total_revenue))
c3.metric("Total Returns", money(total_returns))
c4.metric("Total Purchase", money(total_purchase))
c5.metric("Net Profit", money(total_profit))

# =====================================================
# SKU SUMMARY
# =====================================================

sku = (
    merged.groupby("Supplier_SKU")
    .agg(
        Delivered=("Final_Status", lambda x: (x == "Delivered").sum()),
        Shipped=("Final_Status", lambda x: (x == "Shipped").sum()),
        Return=("Final_Status", lambda x: (x == "Return").sum()),
        RTO=("Final_Status", lambda x: (x == "RTO").sum()),
        Cancelled=("Final_Status", lambda x: (x == "Cancelled").sum()),
        Exchange=("Final_Status", lambda x: (x == "Exchange").sum()),
        Revenue=("Revenue", "sum"),
        Returns=("Returns", "sum"),
        Purchase_Cost=("Purchase_Cost", "max"),
        Total_Purchase=("Total Purchase", "sum"),
        Net_Profit=("Net Profit", "sum"),
        Net_Settlement=("Net_Settlement", "sum")
    )
    .reset_index()
)

den = (
    sku["Delivered"] +
    sku["Shipped"] +
    sku["Return"]
).replace(0, pd.NA)

sku["Return %"] = (
    sku["Return"] / den * 100
).fillna(0).round(2)

# =====================================================
# TABLE
# =====================================================

st.subheader("📋 SKU Summary")

show_cols = [
    "Supplier_SKU",
    "Delivered",
    "Shipped",
    "Return",
    "RTO",
    "Cancelled",
    "Exchange",
    "Revenue",
    "Returns",
    "Purchase_Cost",
    "Total_Purchase",
    "Net_Settlement",
    "Net_Profit",
    "Return %"
]

st.dataframe(
    sku[show_cols]
    .sort_values("Net_Profit", ascending=False)
    .reset_index(drop=True),
    use_container_width=True
)

# =====================================================
# RAW MERGED DATA
# =====================================================

st.subheader("🔍 Merged Order Level Data")

st.dataframe(
    merged.sort_values("Net Profit", ascending=False),
    use_container_width=True
)
