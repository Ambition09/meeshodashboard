import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re

st.set_page_config(layout="wide")
st.title("📊 Meesho Seller Dashboard")


# =====================================================
# HELPERS
# =====================================================

def clean_sku(x):
    """Normalize SKU to avoid mismatch issues"""
    return str(x).strip().lower()


def read_orders_file(file):
    """Safely read CSV or Excel"""
    name = file.name.lower()

    if name.endswith(".csv"):
        return pd.read_csv(file)

    return pd.read_excel(file, header=1, engine="openpyxl")


def extract_amount(text):
    """Extract Rs / Rs. amounts from claims text"""
    nums = re.findall(r'Rs\.?\s*(\d+(?:\.\d+)?)', str(text))
    return sum(float(x) for x in nums)


# =====================================================
# PURCHASE COST MAP
# =====================================================

PURCHASE_COST_MAP = {
    clean_sku("HB-221 Purple"): 850,
    clean_sku("MIRROR YELLOW"): 850,
    clean_sku("mirror - blue"): 850,
    clean_sku("HB-221 Red"): 850,
    clean_sku("PS124 Rama"): 650,
    clean_sku("PS124 Black"): 650,
    clean_sku("PS124 Pink"): 650,
    clean_sku("HB-103 YELLOW NEW"): 550,
    clean_sku("HB-103 INDIGO NEW"): 550,
    clean_sku("HB-103 PINK NEW"): 550,
    clean_sku("HB-103 RAMA NEW"): 550,
    clean_sku("HB-103 WINE NEW"): 550
}


# =====================================================
# FILE UPLOADS
# =====================================================

orders_file = st.file_uploader("Upload Orders File (.xlsx or .csv)")
claims_file = st.file_uploader("Upload Claims File (.csv)")


# =====================================================
# ================= STAGE 1 — SALES ===================
# =====================================================

summary = None

if orders_file:

    df = read_orders_file(orders_file)

    sku_col = "Supplier SKU"
    status_col = "Live Order Status"
    settlement_col = "Final Settlement Amount"

    df = df.dropna(subset=[sku_col])
    df[settlement_col] = pd.to_numeric(df[settlement_col], errors="coerce").fillna(0)

    df["clean_sku"] = df[sku_col].apply(clean_sku)
    df["Purchase Cost"] = df["clean_sku"].map(PURCHASE_COST_MAP).fillna(0)

    # Profit
    df["Profit"] = df.apply(
        lambda r: r[settlement_col] - r["Purchase Cost"]
        if r[status_col] == "Delivered"
        else r[settlement_col],
        axis=1
    )

    # counts
    counts = (
        df.pivot_table(index=sku_col,
                       columns=status_col,
                       aggfunc="size",
                       fill_value=0)
        .reset_index()
    )

    revenue = (
        df[df[status_col] == "Delivered"]
        .groupby(sku_col)[settlement_col]
        .sum()
        .reset_index(name="Revenue")
    )

    profit = (
        df.groupby(sku_col)["Profit"]
        .sum()
        .reset_index(name="Net Profit")
    )

    purchase = (
        df.groupby(sku_col)["Purchase Cost"]
        .first()
        .reset_index()
    )

    summary = counts.merge(revenue, on=sku_col, how="left")
    summary = summary.merge(profit, on=sku_col, how="left")
    summary = summary.merge(purchase, on=sku_col, how="left")

    summary["Total Purchase"] = summary["Delivered"] * summary["Purchase Cost"]
    summary = summary.fillna(0)

    # ================= KPIs =================

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Delivered", int(summary["Delivered"].sum()))
    c2.metric("Revenue ₹", round(summary["Revenue"].sum(), 2))
    c3.metric("Purchase ₹", round(summary["Total Purchase"].sum(), 2))
    c4.metric("Profit ₹", round(summary["Net Profit"].sum(), 2))


    # ================= Charts =================

    col1, col2 = st.columns(2)

    with col1:
        fig, ax = plt.subplots(figsize=(3, 3))
        ax.pie(
            [
                summary["Delivered"].sum(),
                summary.get("Return", 0).sum(),
                summary.get("RTO", 0).sum()
            ],
            labels=["Delivered", "Return", "RTO"],
            autopct="%1.0f%%"
        )
        st.pyplot(fig)

    with col2:
        fig, ax = plt.subplots(figsize=(5, 3))
        colors = ["green" if x > 0 else "red" for x in summary["Net Profit"]]
        ax.barh(summary[sku_col], summary["Net Profit"], color=colors)
        st.pyplot(fig)


    st.subheader("📋 Sales Table")
    st.dataframe(
        summary[[sku_col, "Delivered", "Purchase Cost",
                 "Total Purchase", "Revenue", "Net Profit"]],
        use_container_width=True
    )


# =====================================================
# ================= STAGE 2 — CLAIMS ==================
# =====================================================

if claims_file:

    st.divider()
    st.header("🧾 Claims Analysis")

    claims = pd.read_csv(claims_file)

    claims["Claim Amount"] = claims["Last Update"].apply(extract_amount)
    claims["clean_sku"] = claims["SKU"].apply(clean_sku)
    claims["Purchase Cost"] = claims["clean_sku"].map(PURCHASE_COST_MAP).fillna(0)

    approved = claims[claims["Ticket Status"] == "Approved"]
    rejected = claims[claims["Ticket Status"] == "Rejected"]

    approved_grp = (
        approved.groupby("SKU")
        .agg(Approved_Qty=("SKU", "count"),
             Claim_Received=("Claim Amount", "sum"))
        .reset_index()
    )

    rejected_grp = (
        rejected.groupby("SKU")
        .agg(Rejected_Qty=("SKU", "count"))
        .reset_index()
    )

    sku_claims = approved_grp.merge(rejected_grp, on="SKU", how="outer").fillna(0)

    sku_claims["clean_sku"] = sku_claims["SKU"].apply(clean_sku)
    sku_claims["Purchase Cost"] = sku_claims["clean_sku"].map(PURCHASE_COST_MAP).fillna(0)

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

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Claim ₹", round(sku_claims["Claim_Received"].sum(), 2))
    c2.metric("Loss ₹", round(sku_claims["Rejected Loss"].sum(), 2))
    c3.metric("Net ₹", round(sku_claims["Net Claim"].sum(), 2))

    st.subheader("📋 Claims Table")
    st.dataframe(
        sku_claims[["SKU", "Approved_Qty", "Rejected_Qty",
                    "Purchase Cost", "Claim_Received", "Net Claim"]],
        use_container_width=True
    )
