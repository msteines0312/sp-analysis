# S&P 500 R&D Spending Analysis

Explores whether R&D investment correlates with financial performance across 251 S&P 500 companies from 2012 to 2015, using SEC 10-K filing data across five sectors.

## Tech Stack

- Python (pandas, matplotlib, scipy)
- MySQL
- Data: Kaggle NYSE Fundamentals dataset (SEC 10-K filings, 2012-2015)

## Key Features

- Normalized MySQL schema across four tables: sectors, companies, financials, and R&D spending
- ETL pipeline that cleans and loads 251 companies across 5 sectors and 4 years of filings
- R&D intensity classifications assigned per sector based on typical reporting behavior
- Revenue-based market cap tier derivation (Large, Mid, Small) used as a size proxy
- Eight analytical SQL queries covering sector trends, company rankings, and R&D vs. growth comparisons
- Pearson and Spearman correlations (with p-values) between R&D intensity and revenue growth, by sector
- Four visualizations comparing R&D intensity vs. financial outcomes

## Key Findings

- IT and Healthcare both spent around 10-11% of revenue on R&D. Every other sector was under 1%. Financials reported essentially zero.
- IT total R&D grew from $70B to $81B between 2013 and 2015. Healthcare went from $46B to $54B. Industrials pulled back slightly in 2015.
- Spending more on R&D doesn't guarantee better margins. Companies at 10%+ R&D intensity showed wide margin variance, with many right around breakeven.
- Low R&D companies grew revenue faster on average (16% vs 13% from 2012 to 2015), though that's likely a sector composition effect rather than a real tradeoff.
- R&D intensity had no positive link to 2012-2015 revenue growth across the 118 companies with data for both years (Pearson r = -0.12, p = 0.19). Dropping Vertex alone moves that to -0.02.
- Health Care was the one sector with a significant relationship, and it was negative (Spearman rho = -0.51, p = 0.009). Big pharma (Pfizer, Merck, Lilly, Bristol-Myers) spent 15-27% of revenue on R&D while sales shrank through the patent cliff, while zero-R&D service companies like Centene and DaVita were among the fastest growers.
- The IT and Industrials correlations look negative at first but drop to roughly zero once companies that don't report R&D are excluded, so they reflect business model differences more than R&D itself.
- Vertex Pharmaceuticals had the highest R&D intensity at 91.7% of revenue with a -56% net margin. They're a pre-profitability biotech, so that's expected behavior, not a data problem.

## What I Learned

First personal project where I got to choose my own dataset and pull insights that weren't already decided by a professor. As someone with a business background, it was a good return to financial numbers, and on the technical side, connecting a Python pipeline directly to a MySQL database was something I hadn't done before outside of coursework.
