import streamlit as st
import pandas as pd
import re
import matplotlib.pyplot as plt

st.set_page_config(page_title="Meesho Seller Dashboard", layout="wide")

st.title("📊 Meesho Seller Master Dashboard")


# =====================================================
# FILE UPLOADS
# =====================================================

orders_file = st.file_uploader("Upload Order Payments Excel", type=["xlsx"])
claims_file = st.file_uploader("Upload Claims CSV", type=["csv"])


# =====================================================
# ================= STAGE 1 — SALES ===================
# =====================================================

if orders_file:

    df = pd.read_excel(orders_file, sheet_name="Order Payments", header=1)

    sku_col = "Supplier SKU"
    status_col = "Live Order Status"
    settlement_col = "Final Settlement Amount"

    df = df.dropna(subset=[sku_col, status_col])
    df[settlement_col] = pd.to_numeric(df[settlement_col], errors="coerce").fillna(0)

    PURCHASE_COST = 850  # unchanged logic

    def calc_profit(row):
        if row[status_col] == "Delivered":
            return row[settlement_col] - PURCHASE_COST
        else:
            return row[settlement_col]

    df["Profit"] = df.apply(calc_profit, axis=1)

    counts = (
        df.pivot_table(index=sku_col,
                       columns=status_col,
                       aggfunc='size',
                       fill_value=0)
        .reset_index()
    )

    for col in ["Delivered", "Return", "RTO"]:
        if col not in counts.columns:
            counts[col] = 0

    counts["Return %"] = (
        counts["Return"] /
        (counts["Return"] + counts["Delivered"]).replace(0, 1)
    ) * 100

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

    summary = counts.merge(revenue, on=sku_col, how="left")
    summary = summary.merge(profit, on=sku_col, how="left")

    summary = summary.fillna(0).round(2)

    # =================================================
    # KPI ROW
    # =================================================

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Delivered", int(summary["Delivered"].sum()))
    c2.metric("Returns", int(summary["Return"].sum()))
    c3.metric("Revenue ₹", round(summary["Revenue"].sum(), 2))
    c4.metric("Net Profit ₹", round(summary["Net Profit"].sum(), 2))


    # =================================================
    # COMPACT CHARTS ROW (2 SIDE BY SIDE)
    # =================================================

    colA, colB = st.columns(2)

    # ---------- Donut ----------
    with colA:
        st.subheader("Order Mix")

        fig, ax = plt.subplots(figsize=(3, 3))

        vals = [
            summary["Delivered"].sum(),
            summary["Return"].sum(),
            summary["RTO"].sum()
        ]

        ax.pie(vals, labels=["Del", "Ret", "RTO"], autopct='%1.0f%%')
        st.pyplot(fig)

    # ---------- Profit bars ----------
    with colB:
        st.subheader("Profit by SKU")

        profit_df = summary.sort_values("Net Profit")

        fig, ax = plt.subplots(figsize=(5, 3))

        colors = ["green" if x > 0 else "red" for x in profit_df["Net Profit"]]

        ax.barh(profit_df[sku_col], profit_df["Net Profit"], color=colors)
        ax.set_xlabel("₹")

        st.pyplot(fig)


    # =================================================
    # TABLE
    # =================================================

    st.subheader("📋 SKU Performance Table")
    st.dataframe(summary.sort_values("Net Profit", ascending=False),
                 use_container_width=True)



# =====================================================
# ================= STAGE 2 — CLAIMS ==================
# =====================================================

if claims_file:

    st.divider()
    st.header("🧾 Claims Recovery Analysis")

    claims = pd.read_csv(claims_file)

    status_col = "Ticket Status"
    sku_col = "SKU"

    PURCHASE_COST_MAP = {
        "HB-221 Purple": 850,
        "MIRROR YELLOW": 850,
        "mirror - blue": 850,
        "HB-221 Red": 850,
        "PS124 Rama": 650,
        "PS124 Black": 650,
        "PS124 Pink": 650,
        "HB-103 YELLOW NEW": 550,
        "HB-103 INDIGO NEW": 550,
        "HB-103 PINK NEW": 550,
        "HB-103 RAMA NEW": 550,
        "HB-103 WINE NEW": 550
        
    }

    def get_cost(sku):
        return PURCHASE_COST_MAP.get(sku, 0)


    # =================================================
    # FIXED MONEY EXTRACTION (Rs / Rs.)
    # =================================================
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

    sku_claims["Purchase Cost"] = sku_claims[sku_col].map(get_cost)

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


    # =================================================
    # KPI ROW
    # =================================================

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Claim ₹", round(sku_claims["Claim_Received"].sum(), 2))
    c2.metric("Rejected Loss ₹", round(sku_claims["Rejected Loss"].sum(), 2))
    c3.metric("Net Claims ₹", round(sku_claims["Net Claim"].sum(), 2))


    # =================================================
    # COMPACT CHARTS ROW
    # =================================================

    colC, colD = st.columns(2)

    # ---------- Claims impact ----------
    with colC:
        st.subheader("Claims Impact")

        claims_chart = sku_claims.set_index(sku_col)

        fig, ax = plt.subplots(figsize=(5, 3))

        ax.bar(claims_chart.index, claims_chart["Approved Profit"], label="Recovered")
        ax.bar(claims_chart.index,
               claims_chart["Rejected Loss"],
               bottom=claims_chart["Approved Profit"],
               label="Loss")

        plt.xticks(rotation=45)
        ax.legend()

        st.pyplot(fig)

    # ---------- Net claim by SKU ----------
    with colD:
        st.subheader("Net Claim by SKU")

        fig, ax = plt.subplots(figsize=(5, 3))

        colors = ["green" if x > 0 else "red" for x in sku_claims["Net Claim"]]

        ax.barh(sku_claims[sku_col], sku_claims["Net Claim"], color=colors)

        st.pyplot(fig)


    # =================================================
    # TABLE
    # =================================================

    st.subheader("📋 Claims Table")
    st.dataframe(sku_claims.sort_values("Net Claim", ascending=False),
                 use_container_width=True)


    # =================================================
    # FINAL TOTAL
    # =================================================

    if orders_file:
        final_total = summary["Net Profit"].sum() + sku_claims["Net Claim"].sum()

        st.divider()
        st.header("🏁 FINAL TOTAL PROFIT")
        st.metric("Sales + Claims ₹", round(final_total, 2))


