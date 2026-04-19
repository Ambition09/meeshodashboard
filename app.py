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
