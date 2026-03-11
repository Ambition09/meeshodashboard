import streamlit as st
import pandas as pd
import re
import matplotlib.pyplot as plt

st.set_page_config(page_title="Meesho Seller Dashboard", layout="wide")

# -----------------------------------------------------
# FONT
# -----------------------------------------------------

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)

# -----------------------------------------------------
# DARK THEME
# -----------------------------------------------------

st.markdown("""
<style>

/* GLOBAL FONT */
html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

/* BACKGROUND */
[data-testid="stAppViewContainer"] {
    background-color: #00022E;
}

/* HEADINGS */
h1, h2, h3, h4 {
    color: white !important;
}

/* FILE UPLOADER TEXT */
[data-testid="stFileUploader"] label {
    color: white !important;
    font-weight: 600;
}

[data-testid="stFileUploader"] span {
    color: #A8B2FF !important;
}

/* KPI CARDS */
[data-testid="stMetric"] {
    background: linear-gradient(145deg,#050845,#0b0f63);
    padding: 25px;
    border-radius: 14px;
    border: 1px solid #2b2fa3;
    transition: all 0.2s ease;
}

/* KPI HOVER EFFECT */
[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.4);
}

/* KPI LABEL */
[data-testid="stMetricLabel"] {
    color: #9CA3FF !important;
    font-size: 15px !important;
}

/* KPI VALUE */
[data-testid="stMetricValue"] {
    color: white !important;
    font-size: 36px !important;
    font-weight: 600;
}

/* TABLES */
[data-testid="stDataFrame"] {
    background-color: #050845;
    border-radius: 12px;
}

/* PAGE SPACING */
.block-container {
    padding-top: 2rem;
}

</style>
""", unsafe_allow_html=True)

st.title("📊 Meesho Seller Master Dashboard")

# =====================================================
# PURCHASE COST MAP
# =====================================================

def clean_sku(x):
    return str(x).strip().lower()

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
    clean_sku("221-Unstiched-Purple"): 450,
    clean_sku("221 Red XXL"): 850,
    clean_sku("221 Purple XXL"): 850,
    clean_sku("221 Red"): 850,
    clean_sku("221 Purple"): 850,
}

# =====================================================
# FILE UPLOADS
# =====================================================

orders_file = st.file_uploader("Upload Order Payments Excel", type=["xlsx"])
claims_file = st.file_uploader("Upload Claims CSV", type=["csv"])

summary = None

# =====================================================
# SALES
# =====================================================

if orders_file:

    df = pd.read_excel(orders_file, sheet_name="Order Payments", header=1)

    sku_col = "Supplier SKU"
    status_col = "Live Order Status"
    settlement_col = "Final Settlement Amount"
    order_col = "Sub Order No"

    df = df.dropna(subset=[sku_col, status_col, order_col])
    df[settlement_col] = pd.to_numeric(df[settlement_col], errors="coerce").fillna(0)

    order_counts = df[order_col].value_counts()

    single_orders = order_counts[order_counts == 1].index
    duplicate_orders = order_counts[order_counts > 1].index

    single_df = df[df[order_col].isin(single_orders)].copy()
    duplicate_df = df[df[order_col].isin(duplicate_orders)].copy()

    # SINGLE ORDERS

    def single_profit(row):
        purchase_cost = PURCHASE_COST_MAP.get(clean_sku(row[sku_col]), 0)

        if row[status_col] in ["Delivered", "Shipped"]:
            return row[settlement_col] - purchase_cost
        else:
            return row[settlement_col]

    single_df["Profit"] = single_df.apply(single_profit, axis=1)

    # DUPLICATE ORDERS

    duplicate_grouped = (
        duplicate_df
        .groupby(order_col)
        .agg({
            settlement_col: "sum",
            sku_col: "first",
            status_col: "last"
        })
        .reset_index()
    )

    def duplicate_profit(row):
        purchase_cost = PURCHASE_COST_MAP.get(clean_sku(row[sku_col]), 0)

        if row[status_col] in ["Delivered", "Shipped"]:
            return row[settlement_col] - purchase_cost
        else:
            return row[settlement_col]

    duplicate_grouped["Profit"] = duplicate_grouped.apply(duplicate_profit, axis=1)

    st.subheader("🔁 Duplicate Orders")
    st.dataframe(duplicate_grouped, use_container_width=True)

    st.subheader("📄 Single Orders")
    st.dataframe(
        single_df[[order_col, sku_col, status_col, settlement_col, "Profit"]],
        use_container_width=True
    )

    final_df = pd.concat([
        single_df[[sku_col, status_col, settlement_col, "Profit"]],
        duplicate_grouped[[sku_col, status_col, settlement_col, "Profit"]]
    ])

    sale_mask = final_df[status_col].isin(["Delivered", "Shipped"])

    counts = (
        final_df.pivot_table(
            index=sku_col,
            columns=status_col,
            aggfunc='size',
            fill_value=0
        ).reset_index()
    )

    for col in ["Delivered", "Return", "RTO", "Shipped"]:
        if col not in counts.columns:
            counts[col] = 0

    revenue = (
        final_df[sale_mask]
        .groupby(sku_col)[settlement_col]
        .sum()
        .reset_index(name="Revenue")
    )

    profit = (
        final_df.groupby(sku_col)["Profit"]
        .sum()
        .reset_index(name="Net Profit")
    )

    summary = counts.merge(revenue, on=sku_col, how="left")
    summary = summary.merge(profit, on=sku_col, how="left")

    summary = summary.fillna(0).round(2)

    summary["Purchase Cost"] = summary[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    summary["Total Purchase"] = (
        (summary["Delivered"] + summary["Shipped"]) *
        summary["Purchase Cost"]
    )

    # KPIs

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Delivered + Shipped",
              int(summary["Delivered"].sum() + summary["Shipped"].sum()))

    c2.metric("Returns",
              int(summary["Return"].sum()))

    c3.metric("Revenue ₹",
              round(summary["Revenue"].sum(), 2))

    c4.metric("Net Profit ₹",
              round(summary["Net Profit"].sum(), 2))

    # CHARTS

    colA, colB = st.columns(2)

    with colA:

        st.subheader("Order Mix")

        fig, ax = plt.subplots(figsize=(3,3))

        vals = [
            summary["Delivered"].sum() + summary["Shipped"].sum(),
            summary["Return"].sum(),
            summary["RTO"].sum()
        ]

        ax.pie(
            vals,
            labels=["Sales","Return","RTO"],
            autopct='%1.0f%%',
            colors=["#4DA3FF","#FF6B6B","#FFD166"]
        )

        st.pyplot(fig)

    with colB:

        st.subheader("Profit by SKU")

        profit_df = summary.sort_values("Net Profit")

        fig, ax = plt.subplots(figsize=(5,3))

        colors = ["#4CAF50" if x > 0 else "#FF4B4B"
                  for x in profit_df["Net Profit"]]

        ax.barh(
            profit_df[sku_col],
            profit_df["Net Profit"],
            color=colors
        )

        ax.set_xlabel("₹")

        st.pyplot(fig)

    st.subheader("📋 SKU Performance Table")

    st.dataframe(
        summary.sort_values("Net Profit", ascending=False),
        use_container_width=True
    )

# =====================================================
# CLAIMS
# =====================================================

if claims_file:

    st.divider()
    st.header("🧾 Claims Recovery Analysis")

    claims = pd.read_csv(claims_file)

    status_col = "Ticket Status"
    sku_col = "SKU"

    def extract_amount(text):
        if pd.isna(text):
            return 0
        nums = re.findall(r'Rs\.?\s*(\d+(?:\.\d+)?)', str(text))
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

    sku_claims = approved_grp.merge(rejected_grp, on=sku_col, how="outer").fillna(0)

    sku_claims["Purchase Cost"] = sku_claims[sku_col].apply(
        lambda x: PURCHASE_COST_MAP.get(clean_sku(x), 0)
    )

    sku_claims["Approved Profit"] = (
        sku_claims["Claim_Received"]
        - (sku_claims["Approved_Qty"] * sku_claims["Purchase Cost"])
    )

    sku_claims["Rejected Loss"] = (
        sku_claims["Rejected_Qty"] * sku_claims["Purchase Cost"]
    )

    sku_claims["Net Claim"] = (
        sku_claims["Approved Profit"] - sku_claims["Rejected Loss"]
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Claim ₹", round(sku_claims["Claim_Received"].sum(), 2))
    c2.metric("Rejected Loss ₹", round(sku_claims["Rejected Loss"].sum(), 2))
    c3.metric("Net Claims ₹", round(sku_claims["Net Claim"].sum(), 2))

    st.subheader("📋 Claims Table")

    st.dataframe(
        sku_claims.sort_values("Net Claim", ascending=False),
        use_container_width=True
    )

    if summary is not None:

        final_total = summary["Net Profit"].sum() + sku_claims["Net Claim"].sum()

        st.divider()
        st.header("🏁 FINAL TOTAL PROFIT")

        st.metric("Sales + Claims ₹", round(final_total, 2))



