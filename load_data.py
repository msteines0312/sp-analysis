"""
load_data.py
------------
Cleans the NYSE fundamentals dataset and loads it into MySQL.

Run this after schema.sql has been applied:
    mysql -u root -p < schema.sql
    python load_data.py

Expected files (adjust DATA_DIR if needed):
    data/fundamentals.csv
    data/securities.csv
"""

import os
import pandas as pd
import mysql.connector
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- config -----------------------------------------------------------
DATA_DIR = Path("data")
DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME", "sp500_rd"),
)

SECTORS_IN_SCOPE = [
    "Information Technology",
    "Health Care",
    "Industrials",
    "Consumer Staples",
    "Financials",
]

# R&D intensity is a judgment call based on how much R&D these sectors
# typically report as a share of revenue. Assigned manually here.
SECTOR_RD_INTENSITY = {
    "Information Technology": "High",
    "Health Care":            "High",
    "Industrials":            "Medium",
    "Consumer Staples":       "Low",
    "Financials":             "Low",
}


# --- load raw files ---------------------------------------------------
def load_raw():
    fund = pd.read_csv(DATA_DIR / "fundamentals.csv")
    sec  = pd.read_csv(DATA_DIR / "securities.csv")

    # normalize column name so the merge works cleanly
    sec = sec.rename(columns={"Ticker symbol": "Ticker Symbol"})

    print(f"fundamentals.csv: {fund.shape[0]} rows, {fund.shape[1]} cols")
    print(f"securities.csv:   {sec.shape[0]} rows")
    return fund, sec


# --- clean ------------------------------------------------------------
def clean(fund, sec):
    # drop the one bad-year row (For Year = 1215, data entry error)
    fund = fund[fund["For Year"].between(2010, 2020)].copy()

    # keep only complete years (2016 is partial - only ~85 rows)
    fund = fund[fund["For Year"].isin([2012, 2013, 2014, 2015])].copy()
    fund["year"] = fund["For Year"].astype(int)

    # merge sector info from securities.csv
    df = fund.merge(
        sec[["Ticker Symbol", "Security", "GICS Sector"]],
        on="Ticker Symbol",
        how="left",
    )

    # keep only target sectors
    df = df[df["GICS Sector"].isin(SECTORS_IN_SCOPE)].copy()

    # rename columns to match schema
    df = df.rename(columns={
        "Ticker Symbol":     "ticker",
        "Security":          "name",
        "GICS Sector":       "sector_name",
        "Total Revenue":     "revenue",
        "Net Income":        "net_income",
        "Operating Income":  "operating_income",
        "Research and Development": "rd_expense",
    })

    # cast financial columns to nullable integers (some rows have floats/NaN)
    for col in ["revenue", "net_income", "operating_income", "rd_expense"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(0)

    # compute R&D as % of revenue
    # where revenue is 0 or null, leave pct as null to avoid divide-by-zero
    df["rd_pct_revenue"] = df.apply(
        lambda r: round(r["rd_expense"] / r["revenue"], 4)
        if pd.notna(r["rd_expense"]) and pd.notna(r["revenue"]) and r["revenue"] != 0
        else None,
        axis=1,
    )

    print(f"\nAfter cleaning: {df.shape[0]} rows across {df['ticker'].nunique()} companies")
    print(df.groupby("sector_name")["ticker"].nunique().to_string())
    return df


# --- derive market_cap_tier -------------------------------------------
def assign_market_cap_tier(df):
    """
    Uses average annual revenue per company as a size proxy.
    Large  = avg revenue > $10B
    Mid    = $1B - $10B
    Small  = < $1B
    """
    avg_rev = df.groupby("ticker")["revenue"].mean()

    def tier(avg):
        if pd.isna(avg):
            return "Mid"          # fallback for missing revenue
        elif avg > 10_000_000_000:
            return "Large"
        elif avg > 1_000_000_000:
            return "Mid"
        else:
            return "Small"

    tier_map = avg_rev.apply(tier).to_dict()
    df["market_cap_tier"] = df["ticker"].map(tier_map)
    return df


# --- database helpers -------------------------------------------------
def get_connection():
    return mysql.connector.connect(**DB)


def insert_sectors(cursor):
    """Insert the 5 sectors with their R&D intensity classifications."""
    rows = [(name, SECTOR_RD_INTENSITY[name]) for name in SECTORS_IN_SCOPE]
    cursor.executemany(
        "insert ignore into sectors (sector_name, rd_intensity) values (%s, %s)",
        rows,
    )
    print(f"\nInserted {cursor.rowcount} sectors")

    # return a lookup: sector_name -> sector_id
    cursor.execute("select sector_id, sector_name from sectors")
    return {name: sid for sid, name in cursor.fetchall()}


def insert_companies(cursor, df, sector_lookup):
    """One row per unique ticker. De-duplicated from the multi-year frame."""
    companies = (
        df[["ticker", "name", "sector_name", "market_cap_tier"]]
        .drop_duplicates(subset="ticker")
        .copy()
    )
    companies["sector_id"] = companies["sector_name"].map(sector_lookup)

    rows = [
        (r.ticker, r.name, int(r.sector_id), r.market_cap_tier)
        for r in companies.itertuples()
    ]
    cursor.executemany(
        "insert ignore into companies (ticker, name, sector_id, market_cap_tier) values (%s, %s, %s, %s)",
        rows,
    )
    print(f"Inserted {cursor.rowcount} companies")

    # return a lookup: ticker -> company_id
    cursor.execute("select company_id, ticker from companies")
    return {ticker: cid for cid, ticker in cursor.fetchall()}


def insert_financials(cursor, df, company_lookup):
    rows = []
    for r in df.itertuples():
        cid = company_lookup.get(r.ticker)
        if cid is None:
            continue
        rows.append((
            cid,
            int(r.year),
            int(r.revenue)        if pd.notna(r.revenue)         else None,
            int(r.net_income)     if pd.notna(r.net_income)      else None,
            int(r.operating_income) if pd.notna(r.operating_income) else None,
        ))

    cursor.executemany(
        """insert ignore into financials
           (company_id, year, revenue, net_income, operating_income)
           values (%s, %s, %s, %s, %s)""",
        rows,
    )
    print(f"Inserted {cursor.rowcount} financials rows")


def insert_rd_spending(cursor, df, company_lookup):
    rows = []
    for r in df.itertuples():
        cid = company_lookup.get(r.ticker)
        if cid is None:
            continue
        rows.append((
            cid,
            int(r.year),
            int(r.rd_expense)    if pd.notna(r.rd_expense)     else None,
            float(r.rd_pct_revenue) if pd.notna(r.rd_pct_revenue) else None,
        ))

    cursor.executemany(
        """insert ignore into rd_spending
           (company_id, year, rd_expense, rd_pct_revenue)
           values (%s, %s, %s, %s)""",
        rows,
    )
    print(f"Inserted {cursor.rowcount} rd_spending rows")


# --- main -------------------------------------------------------------
def main():
    print("Loading raw files...")
    fund, sec = load_raw()

    print("\nCleaning data...")
    df = clean(fund, sec)
    df = assign_market_cap_tier(df)

    print("\nConnecting to MySQL...")
    conn = get_connection()
    cursor = conn.cursor()

    sector_lookup  = insert_sectors(cursor)
    company_lookup = insert_companies(cursor, df, sector_lookup)
    insert_financials(cursor, df, company_lookup)
    insert_rd_spending(cursor, df, company_lookup)

    conn.commit()
    cursor.close()
    conn.close()
    print("\nDone. Run verification queries to confirm row counts.")


if __name__ == "__main__":
    main()
