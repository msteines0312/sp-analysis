import os
import pandas as pd
import mysql.connector
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from dotenv import load_dotenv
from scipy import stats

load_dotenv()


def get_conn():
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    return conn


def run_query(query):
    conn = get_conn()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# q1: avg r&d spend and r&d % of revenue by sector
q1 = """
select
    s.sector_name,
    round(avg(r.rd_expense) / 1e9, 2)      as avg_rd_spend_billions,
    round(avg(r.rd_pct_revenue) * 100, 2)  as avg_rd_pct_revenue
from sectors s
join companies c   on c.sector_id   = s.sector_id
join rd_spending r on r.company_id  = c.company_id
group by s.sector_name
order by avg_rd_pct_revenue desc
"""

# q2: year-over-year r&d growth by sector (2013-2015 only)
# 2012 data is incomplete (~119 of 251 companies), so growth is scoped to 2013+
q2 = """
with sector_yearly as (
    select
        s.sector_name,
        r.year,
        sum(r.rd_expense) as total_rd
    from sectors s
    join companies c   on c.sector_id   = s.sector_id
    join rd_spending r on r.company_id  = c.company_id
    where r.rd_expense is not null
      and r.year >= 2013
    group by s.sector_name, r.year
)
select
    sector_name,
    year,
    round(total_rd / 1e9, 2) as total_rd_billions,
    round(
        (total_rd - lag(total_rd) over (partition by sector_name order by year))
        / lag(total_rd) over (partition by sector_name order by year) * 100,
        2
    ) as yoy_growth_pct
from sector_yearly
order by sector_name, year
"""

# q3: top 20 companies by r&d % of revenue (averaged across all years)
q3 = """
select
    c.ticker,
    c.name,
    s.sector_name,
    c.market_cap_tier,
    round(avg(r.rd_pct_revenue) * 100, 2) as avg_rd_pct_revenue
from companies c
join sectors s     on s.sector_id   = c.sector_id
join rd_spending r on r.company_id  = c.company_id
where r.rd_pct_revenue is not null
group by c.ticker, c.name, s.sector_name, c.market_cap_tier
order by avg_rd_pct_revenue desc
limit 20
"""

# q4: r&d intensity vs net income margin, one row per company (feeds scatter plot)
q4 = """
select
    c.ticker,
    c.name,
    s.sector_name,
    round(avg(r.rd_pct_revenue) * 100, 2)           as avg_rd_pct_revenue,
    round(avg(f.net_income / f.revenue) * 100, 2)   as avg_net_margin_pct
from companies c
join sectors s     on s.sector_id   = c.sector_id
join rd_spending r on r.company_id  = c.company_id and r.rd_pct_revenue is not null
join financials f  on f.company_id  = c.company_id and f.year = r.year
where f.revenue > 0
group by c.ticker, c.name, s.sector_name
order by avg_rd_pct_revenue desc
"""

# q8: company-level r&d intensity vs 2012-2015 revenue growth (feeds correlation table)
# same definitions as q5, so only the ~118 companies with 2012 revenue are included
q8 = """
with company_rd as (
    select company_id, avg(rd_pct_revenue) as avg_rd_pct
    from rd_spending
    group by company_id
),
revenue_endpoints as (
    select
        company_id,
        max(case when year = 2012 then revenue end) as rev_2012,
        max(case when year = 2015 then revenue end) as rev_2015
    from financials
    group by company_id
)
select
    c.ticker,
    s.sector_name,
    rd.avg_rd_pct,
    (re.rev_2015 - re.rev_2012) / re.rev_2012   as rev_growth,
    rd.avg_rd_pct > 0                           as has_rd
from companies c
join sectors s            on s.sector_id   = c.sector_id
join company_rd rd        on rd.company_id = c.company_id
join revenue_endpoints re on re.company_id = c.company_id
where re.rev_2012 > 0 and re.rev_2015 is not null
order by s.sector_name, c.ticker
"""


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
    x = group["avg_rd_pct"].astype(float)
    y = group["rev_growth"].astype(float)
    result = {"companies": len(group), "report_rd": int((x > 0).sum())}

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
    by_sector.loc["Health Care (R&D reporters only)"] = correlate(
        reporters[reporters["sector_name"] == "Health Care"]
    )

    by_sector.to_csv("output/rd_growth_correlation.csv")
    print("R&D % of revenue vs 2012-2015 revenue growth:")
    print(by_sector.to_string())
    print("correlation table saved.")


def chart_sector_rd_pct(df):
    """Bar chart: avg R&D as % of revenue by sector."""
    # sort ascending so the highest bar appears at the top of a horizontal chart
    df = df.sort_values("avg_rd_pct_revenue")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(df["sector_name"], df["avg_rd_pct_revenue"], color="steelblue")

    ax.set_title("Average R&D Spending as % of Revenue by Sector (2012-2015)")
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
    
    df = df.head(15).sort_values("avg_rd_pct_revenue")

    
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
    df_q1 = run_query(q1)
    df_q2 = run_query(q2)
    df_q3 = run_query(q3)
    df_q4 = run_query(q4)
    df_q8 = run_query(q8)
    print("queries complete.\n")

    chart_sector_rd_pct(df_q1)
    chart_rd_trend(df_q2)
    chart_rd_vs_margin(df_q4)
    chart_top_companies(df_q3)
    rd_growth_correlation(df_q8)

    print("\nall outputs saved to output/")


if __name__ == "__main__":
    main()
