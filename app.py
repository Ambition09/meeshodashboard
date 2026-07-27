from pathlib import Path
import re

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Meesho Month Wise PNL", layout="wide")
st.title("Meesho Month Wise PNL Dashboard")


LOCAL_SAMPLE_FILE = Path(r"C:\Users\karwa\Downloads\MERGED.xlsx")


def clean_sku(value):
    return str(value).strip().lower()


def money(value):
    return f"Rs. {value:,.2f}"


def require_columns(dataframe, required_columns, source_name):
    missing = [column for column in required_columns if column not in dataframe.columns]
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
    """Extract all INR values shown in a claim update message."""
    if pd.isna(text):
        return 0.0
    matches = re.findall(
        r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)",
        str(text),
        flags=re.IGNORECASE,
    )
    return sum(float(amount.replace(",", "")) for amount in matches)


PURCHASE_COST_MAP = {
    clean_sku("MirrorBlue1"): 850,
    clean_sku("HIRVA-221 PURPLE NEW 1299"): 600,
    clean_sku("HB-221 Purple"): 600,
    clean_sku("HB-221 Red"): 600,
    clean_sku("HIRVA-221 RED NEW 1299"): 600,
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
    clean_sku("BH-221 Red NEW 1299"): 600,
    clean_sku("BH-221 Purple NEW 1299"): 600,
    clean_sku("221-Unstiched-Purple"): 450,
    clean_sku("221-Unstiched-Red"): 480,
    clean_sku("221 Red XXL"): 600,
    clean_sku("221 Purple XXL"): 600,
    clean_sku("221 Red"): 600,
    clean_sku("221 Purple"): 600,
    clean_sku("hb-221 purples"): 600,
    clean_sku("hb-221  b red"): 600,
    clean_sku("H-201 maroon"): 550,
    clean_sku("103-Unstiched-Yellow"): 450,
    clean_sku("103-Unstiched-Rama"): 450,
    clean_sku("221-Blouse-Red"): 250,
    clean_sku("221- blouse- purple"): 250,
    clean_sku("221-Blouse-Purple"): 250,
    clean_sku("221-RED-LATEST"): 250,
    clean_sku("645270438"): 250,
    clean_sku("2120167267"): 250,
    clean_sku("221 blou"): 250,
    clean_sku("221 bl"): 250,
    clean_sku("221-PURPLE-LATEST"): 600,
    clean_sku("103"): 200,
    clean_sku("103-Blouse-RAMA"): 200,
    clean_sku("2076572086"): 250,
    clean_sku("1418208170"): 600,
    clean_sku("1096510020"): 250,
    clean_sku("1987123931"): 250,
    clean_sku("342037333"): 250,
    clean_sku("227746947"): 250,
    clean_sku("68002677"): 250,
    clean_sku("221 blo"): 250,
}


ORDER_COLUMNS = [
    "Sub Order No",
    "Order Date",
    "Dispatch Date",
    "Product Name",
    "Supplier SKU",
    "Live Order Status",
    "Payment Date",
    "Final Settlement Amount",
    "Claims",
    "Recovery",
    "Claims Reason",
    "Recovery Reason",
]


def read_orders_workbook(file_or_path):
    excel = pd.ExcelFile(file_or_path)
    if "Order Payments" not in excel.sheet_names:
        st.error("The workbook must contain an 'Order Payments' sheet.")
        st.stop()

    orders = pd.read_excel(file_or_path, sheet_name="Order Payments", header=1)
    orders = orders.dropna(subset=["Supplier SKU"]).copy()
    orders["Source Month"] = pd.to_datetime(
        orders["Payment Date"], errors="coerce"
    ).dt.to_period("M").astype(str)
    return orders


def build_order_lifecycle(raw_orders, charge_exchange_cost):
    """Build order P&L without claim income, which comes only from the claims CSV."""
    orders = raw_orders.copy()
    require_columns(orders, ORDER_COLUMNS, "Order data")

    orders["Row Order"] = range(len(orders))
    orders["Sub Order No"] = orders["Sub Order No"].astype(str).str.strip()
    orders["Supplier SKU"] = orders["Supplier SKU"].astype(str).str.strip()
    orders["Product Name"] = orders["Product Name"].fillna("").astype(str).str.strip()

    for column in ["Final Settlement Amount", "Claims", "Recovery"]:
        orders[column] = pd.to_numeric(orders[column], errors="coerce").fillna(0)
    for column in ["Order Date", "Dispatch Date", "Payment Date"]:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")

    orders["Normalized Status"] = orders["Live Order Status"].apply(normalize_status)
    orders["Purchase Cost"] = orders["Supplier SKU"].apply(
        lambda sku: PURCHASE_COST_MAP.get(clean_sku(sku), 0)
    )

    # Claims are calculated from the separate claims CSV.  Remove only the Claims
    # component, not the whole row, so deductions on a mixed row are retained.
    orders["Order Settlement Amount"] = (
        orders["Final Settlement Amount"] - orders["Claims"]
    )
    orders["Has Claim Reason"] = (
        orders["Claims Reason"].fillna("").astype(str).str.strip().ne("")
    )
    orders["Has Recovery Reason"] = (
        orders["Recovery Reason"].fillna("").astype(str).str.strip().ne("")
    )

    orders["Latest Sort Date"] = (
        orders["Payment Date"]
        .fillna(orders["Dispatch Date"])
        .fillna(orders["Order Date"])
    )

    # Later claim/recovery transaction rows can have blank status.  The latest
    # non-blank status is the actual order status and is used for COGS decisions.
    status_rows = orders[orders["Normalized Status"] != "Blank"].copy()
    latest_status = (
        status_rows.sort_values(["Sub Order No", "Latest Sort Date", "Row Order"])
        .groupby("Sub Order No", as_index=False)
        .tail(1)
    )
    latest_any = (
        orders.sort_values(["Sub Order No", "Latest Sort Date", "Row Order"])
        .groupby("Sub Order No", as_index=False)
        .tail(1)[["Sub Order No", "Source Month"]]
        .rename(columns={"Source Month": "Final Month"})
    )

    # Defensive fallback for an order that has no status on any payment row.
    if latest_status["Sub Order No"].nunique() < orders["Sub Order No"].nunique():
        missing_ids = set(orders["Sub Order No"]) - set(latest_status["Sub Order No"])
        fallback = orders[orders["Sub Order No"].isin(missing_ids)].copy()
        fallback = (
            fallback.sort_values(["Sub Order No", "Latest Sort Date", "Row Order"])
            .groupby("Sub Order No", as_index=False)
            .tail(1)
        )
        latest_status = pd.concat([latest_status, fallback], ignore_index=True)

    settlement_totals = (
        orders.groupby("Sub Order No")
        .agg(
            Gross_Order_Settlement=(
                "Order Settlement Amount", lambda series: series[series > 0].sum()
            ),
            Order_Deductions=(
                "Order Settlement Amount", lambda series: abs(series[series < 0].sum())
            ),
            Net_Order_Settlement=("Order Settlement Amount", "sum"),
            Claim_Payments_Excluded=("Claims", "sum"),
            Recovery_Amount=("Recovery", "sum"),
            Row_Count=("Sub Order No", "count"),
        )
        .reset_index()
    )

    lifecycle = latest_status[
        [
            "Sub Order No",
            "Supplier SKU",
            "Product Name",
            "Order Date",
            "Dispatch Date",
            "Payment Date",
            "Live Order Status",
            "Normalized Status",
            "Purchase Cost",
        ]
    ].merge(settlement_totals, on="Sub Order No", how="left")
    lifecycle = lifecycle.merge(latest_any, on="Sub Order No", how="left")

    cost_statuses = ["Delivered", "Shipped"]
    if charge_exchange_cost:
        cost_statuses.append("Exchange")
    lifecycle["Order Cost Qty"] = lifecycle["Normalized Status"].isin(cost_statuses).astype(int)
    lifecycle["Order Purchase Cost"] = (
        lifecycle["Order Cost Qty"] * lifecycle["Purchase Cost"]
    )
    lifecycle["Order Profit"] = (
        lifecycle["Net_Order_Settlement"] - lifecycle["Order Purchase Cost"]
    )
    lifecycle["Is Duplicate Lifecycle"] = lifecycle["Row_Count"] > 1
    return orders, lifecycle


def build_claims_table(claims_file, lifecycle):
    if claims_file is None:
        return pd.DataFrame(), 0.0

    claims = pd.read_csv(claims_file)
    require_columns(
        claims,
        ["SKU", "Suborder Number", "Ticket ID", "Ticket Status", "Last Update"],
        "Claims CSV",
    )

    claims["SKU"] = claims["SKU"].astype(str).str.strip()
    claims["Suborder Number"] = claims["Suborder Number"].astype(str).str.strip()
    claims["Ticket Status"] = claims["Ticket Status"].fillna("").astype(str).str.strip()
    claims["Claim Amount"] = claims["Last Update"].apply(extract_claim_amount)
    claims["Purchase Cost"] = claims["SKU"].apply(
        lambda sku: PURCHASE_COST_MAP.get(clean_sku(sku), 0)
    )

    claims["Approved Qty"] = claims["Ticket Status"].str.contains(
        "approved", case=False, na=False
    ).astype(int)
    claims["Rejected Qty"] = claims["Ticket Status"].str.contains(
        "rejected", case=False, na=False
    ).astype(int)
    claims["Open Qty"] = claims["Ticket Status"].str.contains(
        "open", case=False, na=False
    ).astype(int)
    claims["Approved Claim Received"] = claims["Claim Amount"] * claims["Approved Qty"]
    claims["Approved Purchase Cost"] = claims["Purchase Cost"] * claims["Approved Qty"]
    claims["Rejected Purchase Cost"] = claims["Purchase Cost"] * claims["Rejected Qty"]
    claims["Net Claim Profit"] = (
        claims["Approved Claim Received"]
        - claims["Approved Purchase Cost"]
        - claims["Rejected Purchase Cost"]
    )

    order_keys = lifecycle[["Sub Order No", "Normalized Status"]].rename(
        columns={"Sub Order No": "Suborder Number", "Normalized Status": "Order Status"}
    )
    claims = claims.merge(order_keys, on="Suborder Number", how="left")
    claims["Matched To Order Payment"] = claims["Order Status"].notna()
    return claims, float(claims["Net Claim Profit"].sum())


with st.sidebar:
    st.header("Inputs")
    orders_file = st.file_uploader("Upload Meesho order-payment Excel", type=["xlsx"])
    claims_file = st.file_uploader("Upload claims CSV", type=["csv"])
    charge_exchange_cost = st.checkbox(
        "Charge purchase cost on Exchange orders", value=False
    )
    use_local_sample = False
    if orders_file is None and LOCAL_SAMPLE_FILE.exists():
        use_local_sample = st.checkbox("Use local MERGED.xlsx", value=True)

if orders_file is None and not use_local_sample:
    st.info("Upload the Meesho order-payment Excel file to begin.")
    st.stop()

input_file = orders_file if orders_file is not None else LOCAL_SAMPLE_FILE
raw_orders = read_orders_workbook(input_file)
raw_orders, lifecycle = build_order_lifecycle(raw_orders, charge_exchange_cost)
claims, net_claim_profit = build_claims_table(claims_file, lifecycle)

order_profit = float(lifecycle["Order Profit"].sum())
net_order_settlement = float(lifecycle["Net_Order_Settlement"].sum())
order_purchase_cost = float(lifecycle["Order Purchase Cost"].sum())
order_deductions = float(lifecycle["Order_Deductions"].sum())
final_profit = order_profit + net_claim_profit

missing_cost = pd.concat(
    [
        lifecycle.loc[lifecycle["Purchase Cost"] == 0, ["Supplier SKU", "Product Name"]],
        claims.loc[claims["Purchase Cost"] == 0, ["SKU"]].rename(
            columns={"SKU": "Supplier SKU"}
        ),
    ],
    ignore_index=True,
).drop_duplicates()

st.caption(
    "Claims income is sourced from the claims CSV. The Excel Claims component is "
    "removed from order settlements; Recovery/Affiliate Fee rows remain included."
)
st.subheader("Total Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Final Profit", money(final_profit))
c2.metric("Order Profit", money(order_profit))
c3.metric("Claim Profit", money(net_claim_profit))
c4.metric("Order Settlement (excl. claims)", money(net_order_settlement))
c5, c6, c7, c8 = st.columns(4)
c5.metric("Order Purchase Cost", money(order_purchase_cost))
c6.metric("Order Deductions", money(order_deductions))
c7.metric("Final Orders", f"{len(lifecycle):,}")
c8.metric("Duplicate Orders Merged", f"{int(lifecycle['Is Duplicate Lifecycle'].sum()):,}")

if not missing_cost.empty:
    st.error("Unmapped SKU costs found. Their purchase cost is currently Rs. 0.")
    st.dataframe(missing_cost, use_container_width=True, hide_index=True)

tabs = st.tabs(
    [
        "Month Summary",
        "SKU Summary",
        "Claims",
        "Reconciliation",
        "Duplicate Orders",
        "Raw Data",
    ]
)

with tabs[0]:
    month_summary = (
        lifecycle.groupby("Final Month")
        .agg(
            Final_Orders=("Sub Order No", "count"),
            Gross_Order_Settlement=("Gross_Order_Settlement", "sum"),
            Order_Deductions=("Order_Deductions", "sum"),
            Net_Order_Settlement=("Net_Order_Settlement", "sum"),
            Order_Purchase_Cost=("Order Purchase Cost", "sum"),
            Order_Profit=("Order Profit", "sum"),
            Claims_Excluded_From_Excel=("Claim_Payments_Excluded", "sum"),
            Duplicate_Orders=("Is Duplicate Lifecycle", "sum"),
        )
        .reset_index()
        .sort_values("Final Month")
    )
    total_row = month_summary.drop(columns=["Final Month"]).sum(numeric_only=True).to_frame().T
    total_row.insert(0, "Final Month", "TOTAL")
    st.dataframe(
        pd.concat([month_summary, total_row], ignore_index=True),
        use_container_width=True,
        hide_index=True,
    )
    st.bar_chart(
        month_summary.set_index("Final Month")[
            ["Net_Order_Settlement", "Order_Purchase_Cost", "Order_Profit"]
        ]
    )

with tabs[1]:
    sku_summary = (
        lifecycle.groupby("Supplier SKU")
        .agg(
            Product_Name=("Product Name", "first"),
            Final_Orders=("Sub Order No", "count"),
            Net_Order_Settlement=("Net_Order_Settlement", "sum"),
            Order_Purchase_Cost=("Order Purchase Cost", "sum"),
            Order_Profit=("Order Profit", "sum"),
        )
        .reset_index()
    )
    if not claims.empty:
        claim_by_sku = (
            claims.groupby("SKU")
            .agg(
                Approved_Claims=("Approved Qty", "sum"),
                Rejected_Claims=("Rejected Qty", "sum"),
                Open_Claims=("Open Qty", "sum"),
                Claim_Received=("Approved Claim Received", "sum"),
                Claim_Profit=("Net Claim Profit", "sum"),
            )
            .reset_index()
            .rename(columns={"SKU": "Supplier SKU"})
        )
        sku_summary = sku_summary.merge(claim_by_sku, on="Supplier SKU", how="outer").fillna(0)
        sku_summary["Final_Profit"] = sku_summary["Order_Profit"] + sku_summary["Claim_Profit"]
    st.dataframe(
        sku_summary.sort_values("Order_Profit", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

with tabs[2]:
    if claims.empty:
        st.info("Upload a claims CSV to calculate claim income and claim-related COGS.")
    else:
        claim1, claim2, claim3, claim4 = st.columns(4)
        claim1.metric("Approved Claim Received", money(claims["Approved Claim Received"].sum()))
        claim2.metric("Approved Claim COGS", money(claims["Approved Purchase Cost"].sum()))
        claim3.metric("Rejected Claim COGS", money(claims["Rejected Purchase Cost"].sum()))
        claim4.metric("Net Claim Profit", money(net_claim_profit))
        st.dataframe(
            claims.sort_values(["Ticket Status", "Suborder Number"]),
            use_container_width=True,
            hide_index=True,
        )

with tabs[3]:
    st.subheader("Claim / Payment Reconciliation")
    excel_claims = (
        raw_orders.groupby("Sub Order No", as_index=False)
        .agg(
            Excel_Claims_Component=("Claims", "sum"),
            Excel_Recovery_Component=("Recovery", "sum"),
        )
        .rename(columns={"Sub Order No": "Suborder Number"})
    )
    if claims.empty:
        st.info("Upload the claims CSV to compare CSV claims with the Excel claim component.")
    else:
        reconciliation = (
            claims.groupby("Suborder Number", as_index=False)
            .agg(
                Ticket_Status=("Ticket Status", lambda s: " | ".join(sorted(set(s)))),
                CSV_Approved_Amount=("Approved Claim Received", "sum"),
                CSV_Approved_COGS=("Approved Purchase Cost", "sum"),
                CSV_Rejected_COGS=("Rejected Purchase Cost", "sum"),
                In_Order_Payment_Export=("Matched To Order Payment", "max"),
            )
            .merge(excel_claims, on="Suborder Number", how="outer")
            .fillna(0)
        )
        reconciliation["CSV_vs_Excel_Claim_Difference"] = (
            reconciliation["CSV_Approved_Amount"]
            - reconciliation["Excel_Claims_Component"]
        )
        st.dataframe(
            reconciliation.sort_values("CSV_vs_Excel_Claim_Difference", key=abs, ascending=False),
            use_container_width=True,
            hide_index=True,
        )

with tabs[4]:
    duplicates = lifecycle[lifecycle["Is Duplicate Lifecycle"]].copy()
    if duplicates.empty:
        st.info("No duplicate order lifecycles were found.")
    else:
        st.dataframe(
            duplicates.sort_values("Sub Order No"), use_container_width=True, hide_index=True
        )

with tabs[5]:
    st.subheader("Final Order Lifecycle")
    st.dataframe(
        lifecycle.sort_values(["Final Month", "Sub Order No"]),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Raw Order Payments")
    st.dataframe(
        raw_orders.sort_values(["Source Month", "Sub Order No", "Payment Date"]),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download lifecycle CSV",
        lifecycle.to_csv(index=False).encode("utf-8"),
        file_name="meesho_final_order_lifecycle.csv",
        mime="text/csv",
    )
    if not claims.empty:
        st.download_button(
            "Download claims ledger CSV",
            claims.to_csv(index=False).encode("utf-8"),
            file_name="meesho_claims_ledger.csv",
            mime="text/csv",
        )
