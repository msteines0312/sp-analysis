import os
import re
from pathlib import Path

import pandas as pd
import mysql.connector
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from dotenv import load_dotenv
from scipy import stats

load_dotenv()

# fixed database name, matching schema.sql and queries/analysis.sql
DB_NAME = "sp500_rd"
QUERIES_PATH = Path("queries") / "analysis.sql"


def get_conn():
    """Open a connection to the sp500_rd database.

    Credentials come from the .env file (see .env.example) so they never
    end up in the code.

    Returns
    -------
    mysql.connector.connection.MySQLConnection
        An open connection. The caller is responsible for closing it.
    """
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=DB_NAME
    )
    return conn


def run_query(query):
    """Run a SQL query and return the result as a DataFrame.

    Opens and closes its own connection, so each query is independent.

    Parameters
    ----------
    query : str
        SQL to run against sp500_rd.

    Returns
    -------
    pd.DataFrame
        One row per result row, columns named after the SELECT aliases.
    """
    conn = get_conn()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def load_queries(path=QUERIES_PATH):
    """Read the named queries from queries/analysis.sql.

    The .sql file is the single source of truth for every query, so the charts
    always use the same logic a reader sees when running the file directly.
    Each query starts with a "-- qN:" comment, which is used as its name.

    Parameters
    ----------
    path : str or Path
        Location of the SQL file.

    Returns
    -------
    dict of str to str
        Query name ("q1", "q2", ...) mapped to its SQL, without the trailing semicolon.
    """
    text = Path(path).read_text(encoding="utf-8")

    # split right before each "-- qN:" line with a zero-width lookahead, so the
    # header stays a complete sql comment. consuming it in the split would leave
    # the rest of the title line behind as invalid sql.
    # the first chunk is the file header and "use sp500_rd;", which isn't needed
    # because the connection already selects the database
    chunks = re.split(r"^(?=-- q\d+:)", text, flags=re.MULTILINE)[1:]
    queries = {}
    for chunk in chunks:
        name = re.match(r"-- (q\d+):", chunk).group(1)
        queries[name] = chunk.strip().rstrip(";")
    return queries


def correlate(group):
    """Pearson and Spearman correlation of R&D % vs revenue growth for one group.

    Spearman works on ranks, so it's less sensitive to extreme companies like
    Vertex (91.7% R&D) and to the many tied zeros from non-reporting companies.

    Parameters
    ----------
    group : pd.DataFrame
        Rows from q8 with avg_rd_pct and rev_growth columns.

    Returns
    -------
    pd.Series
        Company counts, both correlation coefficients, and their p-values.
        Coefficients are NaN when R&D doesn't vary (e.g. no company reports it).
    """
    # drop incomplete pairs first. scipy returns NaN if either input has one,
    # which would blank out the whole row instead of skipping one company
    group = group.dropna(subset=["avg_rd_pct", "rev_growth"])
    x = group["avg_rd_pct"].astype(float)
    y = group["rev_growth"].astype(float)
    result = {"companies": len(group), "report_rd": int(group["has_rd"].sum())}

    if len(group) < 3 or x.nunique() < 2:
        result.update(pearson_r=np.nan, pearson_p=np.nan,
                      spearman_r=np.nan, spearman_p=np.nan)
    else:
        pearson = stats.pearsonr(x, y)
        spearman = stats.spearmanr(x, y)
        result.update(pearson_r=pearson[0], pearson_p=pearson[1],
                      spearman_r=spearman[0], spearman_p=spearman[1])
    return pd.Series(result).round(3)


def rd_growth_correlation(df):
    """Correlation table by sector, overall, and for R&D reporters only.

    Saves the table to output/rd_growth_correlation.csv and prints it.
    """
    by_sector = df.groupby("sector_name").apply(correlate, include_groups=False)

    # extra rows: all companies, then only those that report r&d (has_rd = 1).
    # the second row matters because zero-r&d service companies (insurers, labs,
    # payment processors) grew fast and pull every sector's correlation negative
    reporters = df[df["has_rd"] == 1]
    by_sector.loc["All companies"] = correlate(df)
    by_sector.loc["All companies (R&D reporters only)"] = correlate(reporters)

    # reporters-only row for every sector, so the with/without comparison
    # can be checked for each one, not just Health Care
    for sector, group in reporters.groupby("sector_name"):
        by_sector.loc[f"{sector} (R&D reporters only)"] = correlate(group)

    by_sector.to_csv("output/rd_growth_correlation.csv")
    print("R&D % of revenue vs 2012-2015 revenue growth:")
    print(by_sector.to_string())
    print("correlation table saved.")


def chart_sector_rd_pct(df):
    """Bar chart: avg R&D as % of revenue by sector."""
    # sort ascending so the highest bar appears at the top of a horizontal chart
    df = df.sort_values("avg_rd_pct_revenue")

    # averages only cover companies that report r&d, which is as few as one in
    # some sectors, so the sample size goes in each label to keep that visible
    labels = df["sector_name"] + " (n=" + df["companies_reporting_rd"].astype(str) + ")"

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels, df["avg_rd_pct_revenue"], color="steelblue")

    ax.set_title("Average R&D Spending as % of Revenue by Sector, R&D Reporters Only (2012-2015)")
    ax.set_xlabel("Avg R&D as % of Revenue")
    ax.set_ylabel("Sector")

    fig.savefig("output/chart1_sector_rd_pct.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("chart 1 saved.")


def chart_rd_trend(df):
    """Line chart: total R&D spend by sector, 2013-2015."""
    # q2 returns long-format data (one row per sector+year)
    # pivot to wide so each sector becomes its own column for easy line plotting
    wide = df.pivot(index="year", columns="sector_name", values="total_rd_billions")

    fig, ax = plt.subplots(figsize=(10, 6))
    for sector in wide.columns:
        ax.plot(wide.index, wide[sector], marker="o", label=sector)

    ax.set_title("Total R&D Spending by Sector, 2013-2015 ($ Billions)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Total R&D Spend ($ Billions)")
    ax.set_xticks([2013, 2014, 2015])
    ax.legend(title="Sector")

    fig.savefig("output/chart2_rd_trend.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("chart 2 saved.")


def chart_rd_vs_margin(df):
    """Scatter plot: R&D % of revenue vs net income margin, colored by sector.

    Vertex Pharmaceuticals (91.7% R&D, -56% margin) is a pre-profitability biotech
    outlier that would compress the rest of the chart into an unreadable cluster.
    The x-axis is clipped to 45% so the main distribution is visible, with a
    callout note so the outlier isn't silently dropped.
    """
    X_CLIP = 45  # anything beyond this is annotated, not plotted in the main view

    in_view = df[df["avg_rd_pct_revenue"] <= X_CLIP]
    outliers = df[df["avg_rd_pct_revenue"] > X_CLIP]

    sectors = df["sector_name"].unique()
    colors = cm.tab10(np.linspace(0, 1, len(sectors)))
    color_map = dict(zip(sectors, colors))

    fig, ax = plt.subplots(figsize=(11, 7))

    # plot each sector separately so they each get a legend entry
    for sector in sectors:
        subset = in_view[in_view["sector_name"] == sector]
        if subset.empty:
            continue
        ax.scatter(
            subset["avg_rd_pct_revenue"],
            subset["avg_net_margin_pct"],
            label=sector,
            color=color_map[sector],
            alpha=0.75,
            s=50
        )

    # horizontal line at y=0 marks the breakeven between profit and loss
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)

    # list clipped companies in a corner note so they're disclosed, not hidden
    if not outliers.empty:
        note_lines = ["Outliers (outside view):"]
        for _, row in outliers.iterrows():
            note_lines.append(
                f"  {row['ticker']}: {row['avg_rd_pct_revenue']}% R&D, "
                f"{row['avg_net_margin_pct']}% margin"
            )
        ax.text(
            0.98, 0.02, "\n".join(note_lines),
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="bottom",
            horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.8)
        )

    ax.set_title("R&D Intensity vs Net Income Margin by Company (2012-2015 Avg)")
    ax.set_xlabel("Avg R&D as % of Revenue")
    ax.set_ylabel("Avg Net Income Margin (%)")
    ax.set_xlim(left=0)
    ax.legend(title="Sector", loc="upper right")

    fig.savefig("output/chart3_rd_vs_margin.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("chart 3 saved.")


def chart_top_companies(df):
    """Bar chart: top 15 companies by avg R&D % of revenue."""
    # q3 comes back sorted high to low, so head(15) is the top 15.
    # re-sort ascending so the highest bar lands at the top of the chart
    df = df.head(15).sort_values("avg_rd_pct_revenue")

    # ticker plus company name makes each bar readable without a legend
    labels = df["ticker"] + " - " + df["name"]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(labels, df["avg_rd_pct_revenue"], color="steelblue")

    ax.set_title("Top 15 S&P 500 Companies by R&D Spending (% of Revenue, 2012-2015 Avg)")
    ax.set_xlabel("Avg R&D as % of Revenue")
    ax.set_ylabel("")

    fig.savefig("output/chart4_top_companies.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("chart 4 saved.")


def main():
    print("running queries...")
    queries = load_queries()
    df_q1 = run_query(queries["q1"])
    df_q2 = run_query(queries["q2"])
    df_q3 = run_query(queries["q3"])
    df_q4 = run_query(queries["q4"])
    df_q8 = run_query(queries["q8"])
    print("queries complete.\n")

    chart_sector_rd_pct(df_q1)
    chart_rd_trend(df_q2)
    chart_rd_vs_margin(df_q4)
    chart_top_companies(df_q3)
    rd_growth_correlation(df_q8)

    print("\nall outputs saved to output/")


if __name__ == "__main__":
    main()
