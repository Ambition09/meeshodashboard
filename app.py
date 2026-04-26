from pathlib import Path
import re

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Meesho Month Wise PNL", layout="wide")
st.title("Meesho Month Wise PNL Dashboard")


LOCAL_SAMPLE_FILE = Path(r"C:\Users\karwa\Downloads\Trend_Creation_PNL_FINAL.xlsx")


def clean_sku(value):
    return str(value).strip().lower()


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


PURCHASE_COST_MAP = {
    clean_sku("MirrorBlue1"): 850,
    clean_sku("HIRVA-221 PURPLE NEW 1299"): 775,
    clean_sku("HB-221 Purple"): 775,
    clean_sku("HB-221 Red"): 775,
    clean_sku("HIRVA-221 RED NEW 1299"): 775,
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

    clean_sku("BH-221 Red NEW 1299"): 775,
    clean_sku("BH-221 Purple NEW 1299"): 775,

    clean_sku("221-Unstiched-Purple"): 450,
    clean_sku("221-Unstiched-Red"): 480,

    clean_sku("221 Red XXL"): 775,
    clean_sku("221 Purple XXL"): 775,
    clean_sku("221 Red"): 775,
    clean_sku("221 Purple"): 775,

    clean_sku("H-201 maroon"): 550,
    clean_sku("103-Unstiched-Yellow"): 450,
    clean_sku("103-Unstiched-Rama"): 450,
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
]


def read_orders_workbook(file_or_path):
    excel = pd.ExcelFile(file_or_path)

    if "Order Payments" in excel.sheet_names:
        orders = pd.read_excel(file_or_path, sheet_name="Order Payments", header=1)
        orders = orders.dropna(subset=["Supplier SKU"]).copy()
        orders["Source Month"] = pd.to_datetime(
            orders["Payment Date"], errors="coerce"
        ).dt.to_period("M").astype(str)
        return orders, ["Order Payments"]

    month_sheets = [
        sheet
        for sheet in excel.sheet_names
        if re.fullmatch(r"\d{4}-\d{2}", str(sheet).strip())
    ]

    if not month_sheets:
        month_sheets = [sheet for sheet in excel.sheet_names if sheet.lower() != "summary"]

    frames = []
    loaded_sheets = []

    for sheet in month_sheets:
        frame = pd.read_excel(file_or_path, sheet_name=sheet)
        if "Supplier SKU" not in frame.columns:
            continue
        frame = frame.dropna(subset=["Supplier SKU"]).copy()
        frame["Source Month"] = str(sheet)
        frames.append(frame)
        loaded_sheets.append(str(sheet))

    if not frames:
        st.error("No usable order-payment sheets were found in this workbook.")
        st.stop()

    return pd.concat(frames, ignore_index=True), loaded_sheets


def build_order_lifecycle(raw_orders, charge_cancelled_cost):
    orders = raw_orders.copy()
    require_columns(orders, ORDER_COLUMNS, "Order data")

    orders["Row Order"] = range(len(orders))
    orders["Sub Order No"] = orders["Sub Order No"].astype(str).str.strip()
    orders["Supplier SKU"] = orders["Supplier SKU"].astype(str).str.strip()
    orders["Product Name"] = orders["Product Name"].fillna("").astype(str).str.strip()
    orders["Final Settlement Amount"] = pd.to_numeric(
        orders["Final Settlement Amount"], errors="coerce"
    ).fillna(0)

    for date_col in ["Order Date", "Dispatch Date", "Payment Date"]:
        orders[date_col] = pd.to_datetime(orders[date_col], errors="coerce")

    orders["Normalized Status"] = orders["Live Order Status"].apply(normalize_status)
    orders["Purchase Cost"] = orders["Supplier SKU"].apply(
        lambda sku: PURCHASE_COST_MAP.get(clean_sku(sku), 0)
    )

    latest_sort_date = (
        orders["Payment Date"]
        .fillna(orders["Dispatch Date"])
        .fillna(orders["Order Date"])
    )
    orders["Latest Sort Date"] = latest_sort_date

    latest_rows = (
        orders.sort_values(["Sub Order No", "Latest Sort Date", "Row Order"])
        .groupby("Sub Order No", as_index=False)
        .tail(1)
    )

    settlement_totals = (
        orders.groupby("Sub Order No")
        .agg(
            Gross_Positive_Settlement=(
                "Final Settlement Amount",
                lambda s: s[s > 0].sum(),
            ),
            Return_Deduction=(
                "Final Settlement Amount",
                lambda s: abs(s[s < 0].sum()),
            ),
            Net_Settlement=("Final Settlement Amount", "sum"),
            Row_Count=("Sub Order No", "count"),
        )
        .reset_index()
    )

    lifecycle = latest_rows[
        [
            "Sub Order No",
            "Supplier SKU",
            "Product Name",
            "Source Month",
            "Order Date",
            "Dispatch Date",
            "Payment Date",
            "Live Order Status",
            "Normalized Status",
            "Purchase Cost",
        ]
    ].merge(settlement_totals, on="Sub Order No", how="left")

    cost_statuses = ["Delivered", "Shipped"]
    if charge_cancelled_cost:
        cost_statuses.append("Cancelled")

    lifecycle["Cost Qty"] = lifecycle["Normalized Status"].isin(cost_statuses).astype(int)
    lifecycle["Total Purchase Cost"] = lifecycle["Cost Qty"] * lifecycle["Purchase Cost"]
    lifecycle["Actual Profit"] = (
        lifecycle["Net_Settlement"] - lifecycle["Total Purchase Cost"]
    )
    lifecycle["Final Month"] = lifecycle["Source Month"]
    lifecycle["Is Duplicate Lifecycle"] = lifecycle["Row_Count"] > 1

    return orders, lifecycle


def build_claims_table(claims_file):
    if not claims_file:
        return pd.DataFrame(), 0.0

    claims = pd.read_csv(claims_file)
    require_columns(claims, ["SKU", "Ticket Status", "Last Update"], "Claims CSV")

    claims["SKU"] = claims["SKU"].astype(str).str.strip()
    claims["Ticket Status"] = claims["Ticket Status"].fillna("").astype(str).str.strip()
    claims["Claim Amount"] = claims["Last Update"].apply(extract_claim_amount)

    approved = claims[
        claims["Ticket Status"].str.contains("approved", case=False, na=False)
    ].copy()
    rejected = claims[
        claims["Ticket Status"].str.contains("rejected", case=False, na=False)
    ].copy()

    approved_grp = (
        approved.groupby("SKU")
        .agg(Approved_Qty=("SKU", "count"), Claim_Received=("Claim Amount", "sum"))
        .reset_index()
    )
    rejected_grp = (
        rejected.groupby("SKU")
        .agg(Rejected_Qty=("SKU", "count"))
        .reset_index()
    )

    sku_claims = approved_grp.merge(rejected_grp, on="SKU", how="outer").fillna(0)
    sku_claims["Purchase Cost"] = sku_claims["SKU"].apply(
        lambda sku: PURCHASE_COST_MAP.get(clean_sku(sku), 0)
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

    return sku_claims, float(sku_claims["Net Claim"].sum())


with st.sidebar:
    st.header("Inputs")
    orders_file = st.file_uploader("Upload month-wise PNL Excel", type=["xlsx"])
    claims_file = st.file_uploader("Upload Claims CSV (optional)", type=["csv"])
    charge_cancelled_cost = st.checkbox(
        "Charge purchase cost on cancelled final status",
        value=True,
    )

    use_local_sample = False
    if orders_file is None and LOCAL_SAMPLE_FILE.exists():
        use_local_sample = st.checkbox(
            "Use local Trend_Creation_PNL_FINAL.xlsx",
            value=True,
        )

if orders_file is None and not use_local_sample:
    st.info("Upload the month-wise Meesho PNL Excel file to begin.")
    st.stop()

input_file = orders_file if orders_file is not None else LOCAL_SAMPLE_FILE
raw_orders, loaded_sheets = read_orders_workbook(input_file)
raw_orders, lifecycle = build_order_lifecycle(raw_orders, charge_cancelled_cost)
sku_claims, net_claim = build_claims_table(claims_file)

sales_profit = float(lifecycle["Actual Profit"].sum())
net_settlement = float(lifecycle["Net_Settlement"].sum())
purchase_cost = float(lifecycle["Total Purchase Cost"].sum())
return_deduction = float(lifecycle["Return_Deduction"].sum())
final_profit = sales_profit + net_claim


st.caption(f"Loaded sheets: {', '.join(loaded_sheets)}")

st.subheader("Total Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Final Profit", money(final_profit))
c2.metric("Sales Profit", money(sales_profit))
c3.metric("Money Received", money(net_settlement))
c4.metric("Purchase Cost", money(purchase_cost))

c5, c6, c7, c8 = st.columns(4)
c5.metric("Return Deductions", money(return_deduction))
c6.metric("Net Claims", money(net_claim))
c7.metric("Final Orders", f"{len(lifecycle):,}")
c8.metric("Duplicate Orders Merged", f"{int(lifecycle['Is Duplicate Lifecycle'].sum()):,}")


missing_cost = lifecycle[lifecycle["Purchase Cost"] == 0][
    ["Supplier SKU", "Product Name"]
].drop_duplicates()
if not missing_cost.empty:
    st.warning("Some SKUs do not have purchase cost mapped. Their cost is counted as Rs. 0.")
    st.dataframe(missing_cost, use_container_width=True, hide_index=True)


tabs = st.tabs(
    [
        "Month Summary",
        "SKU Summary",
        "Duplicate Orders",
        "Status Breakdown",
        "Claims",
        "Raw Data",
    ]
)


with tabs[0]:
    st.subheader("Month Wise Final PNL")

    month_summary = (
        lifecycle.groupby("Final Month")
        .agg(
            Final_Orders=("Sub Order No", "count"),
            Gross_Positive_Settlement=("Gross_Positive_Settlement", "sum"),
            Return_Deduction=("Return_Deduction", "sum"),
            Net_Settlement=("Net_Settlement", "sum"),
            Purchase_Cost=("Total Purchase Cost", "sum"),
            Sales_Profit=("Actual Profit", "sum"),
            Duplicate_Orders=("Is Duplicate Lifecycle", "sum"),
        )
        .reset_index()
        .sort_values("Final Month")
    )

    total_row = pd.DataFrame(
        [
            {
                "Final Month": "TOTAL",
                "Final_Orders": month_summary["Final_Orders"].sum(),
                "Gross_Positive_Settlement": month_summary[
                    "Gross_Positive_Settlement"
                ].sum(),
                "Return_Deduction": month_summary["Return_Deduction"].sum(),
                "Net_Settlement": month_summary["Net_Settlement"].sum(),
                "Purchase_Cost": month_summary["Purchase_Cost"].sum(),
                "Sales_Profit": month_summary["Sales_Profit"].sum(),
                "Duplicate_Orders": month_summary["Duplicate_Orders"].sum(),
            }
        ]
    )
    month_summary_with_total = pd.concat(
        [month_summary, total_row],
        ignore_index=True,
    )

    st.dataframe(month_summary_with_total, use_container_width=True, hide_index=True)

    chart_data = month_summary.set_index("Final Month")[
        ["Net_Settlement", "Purchase_Cost", "Sales_Profit"]
    ]
    st.bar_chart(chart_data)

    raw_month_summary = (
        raw_orders.groupby("Source Month")
        .agg(
            Raw_Rows=("Sub Order No", "count"),
            Raw_Money_Received=("Final Settlement Amount", "sum"),
        )
        .reset_index()
        .sort_values("Source Month")
    )
    st.subheader("Raw Money by Excel Month")
    st.dataframe(raw_month_summary, use_container_width=True, hide_index=True)


with tabs[1]:
    st.subheader("SKU Wise Final PNL")

    status_counts = (
        lifecycle.pivot_table(
            index="Supplier SKU",
            columns="Normalized Status",
            values="Sub Order No",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )
    status_counts.columns.name = None

    for col in ["Delivered", "Shipped", "Return", "RTO", "Cancelled", "Exchange", "Blank"]:
        if col not in status_counts.columns:
            status_counts[col] = 0

    sku_summary = (
        lifecycle.groupby("Supplier SKU")
        .agg(
            Product_Name=("Product Name", "first"),
            Final_Orders=("Sub Order No", "count"),
            Gross_Positive_Settlement=("Gross_Positive_Settlement", "sum"),
            Return_Deduction=("Return_Deduction", "sum"),
            Net_Settlement=("Net_Settlement", "sum"),
            Purchase_Cost_Per_Piece=("Purchase Cost", "max"),
            Cost_Qty=("Cost Qty", "sum"),
            Total_Purchase_Cost=("Total Purchase Cost", "sum"),
            Actual_Profit=("Actual Profit", "sum"),
        )
        .reset_index()
        .merge(status_counts, on="Supplier SKU", how="left")
    )

    denominator = (
        sku_summary["Delivered"]
        + sku_summary["Shipped"]
        + sku_summary["Return"]
        + sku_summary["RTO"]
    )
    safe_denominator = denominator.where(denominator != 0)
    sku_summary["Return %"] = (
        sku_summary["Return"] / safe_denominator * 100
    ).fillna(0).round(2)
    sku_summary["RTO %"] = (
        sku_summary["RTO"] / safe_denominator * 100
    ).fillna(0).round(2)

    st.dataframe(
        sku_summary.sort_values("Actual_Profit", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


with tabs[2]:
    st.subheader("Merged Duplicate Orders")

    duplicate_orders = lifecycle[lifecycle["Is Duplicate Lifecycle"]].copy()
    if duplicate_orders.empty:
        st.info("No duplicate order lifecycles were found.")
    else:
        st.dataframe(
            duplicate_orders[
                [
                    "Final Month",
                    "Sub Order No",
                    "Supplier SKU",
                    "Product Name",
                    "Normalized Status",
                    "Row_Count",
                    "Gross_Positive_Settlement",
                    "Return_Deduction",
                    "Net_Settlement",
                    "Purchase Cost",
                    "Total Purchase Cost",
                    "Actual Profit",
                ]
            ].sort_values(["Final Month", "Sub Order No"]),
            use_container_width=True,
            hide_index=True,
        )

        selected_order = st.selectbox(
            "View raw rows for duplicate order",
            duplicate_orders["Sub Order No"].sort_values().tolist(),
        )
        st.dataframe(
            raw_orders[raw_orders["Sub Order No"] == selected_order]
            .sort_values(["Payment Date", "Row Order"])
            [
                [
                    "Source Month",
                    "Sub Order No",
                    "Supplier SKU",
                    "Live Order Status",
                    "Normalized Status",
                    "Payment Date",
                    "Final Settlement Amount",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


with tabs[3]:
    st.subheader("Final Status Breakdown")

    status_summary = (
        lifecycle.groupby("Normalized Status")
        .agg(
            Final_Orders=("Sub Order No", "count"),
            Net_Settlement=("Net_Settlement", "sum"),
            Purchase_Cost=("Total Purchase Cost", "sum"),
            Actual_Profit=("Actual Profit", "sum"),
        )
        .reset_index()
        .sort_values("Final_Orders", ascending=False)
    )
    st.dataframe(status_summary, use_container_width=True, hide_index=True)


with tabs[4]:
    st.subheader("Claims Analysis")

    if sku_claims.empty:
        st.info("Upload a claims CSV to calculate approved profit, rejected loss, and net claim.")
    else:
        claim1, claim2, claim3 = st.columns(3)
        claim1.metric("Claim Received", money(sku_claims["Claim_Received"].sum()))
        claim2.metric("Rejected Loss", money(sku_claims["Rejected Loss"].sum()))
        claim3.metric("Net Claim", money(net_claim))

        st.dataframe(
            sku_claims.sort_values("Net Claim", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


with tabs[5]:
    st.subheader("Final Order Lifecycle Data")
    st.dataframe(
        lifecycle.sort_values(["Final Month", "Sub Order No"]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Raw Uploaded Rows")
    st.dataframe(
        raw_orders.sort_values(["Source Month", "Sub Order No", "Payment Date"]),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download Month Summary CSV",
        month_summary_with_total.to_csv(index=False).encode("utf-8"),
        file_name="meesho_month_summary.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download Final Lifecycle CSV",
        lifecycle.to_csv(index=False).encode("utf-8"),
        file_name="meesho_final_order_lifecycle.csv",
        mime="text/csv",
    )
