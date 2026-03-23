# S&P 500 R&D Spending Analysis

Explores whether R&D investment correlates with financial performance across 251 S&P 500 companies from 2012 to 2015, using SEC 10-K filing data across five sectors.

## Tech Stack

- Python (pandas, matplotlib, seaborn)
- MySQL
- Data: Kaggle NYSE Fundamentals dataset (SEC 10-K filings, 2012-2015)

## How to Run

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your MySQL credentials
3. Apply the schema: `mysql -u root -p sp500_rd < schema.sql`
4. Load the data: `python load_data.py`
5. Run the analysis: `python analysis.py` (generates charts in `output/`)

## Key Features

- Normalized MySQL schema across four tables: sectors, companies, financials, and R&D spending
- ETL pipeline that cleans and loads 251 companies across 5 sectors and 4 years of filings
- R&D intensity classifications assigned per sector based on typical reporting behavior
- Revenue-based market cap tier derivation (Large, Mid, Small) used as a size proxy
- Seven analytical SQL queries covering sector trends, company rankings, and correlation analysis
- Four visualizations comparing R&D intensity vs. financial outcomes

## Key Findings

_Analysis in progress. This section will be updated after queries and visualizations are complete._

## What I Learned

_To be written after analysis is complete._
