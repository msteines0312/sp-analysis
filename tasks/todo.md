# S&P 500 R&D Analysis - Project Todo

## Status: Data loaded. Moving to analysis.

---

## Phase 1 - SQL Analysis (queries/analysis.sql)
Write the core analytical queries that answer the project's central question:
does R&D spending correlate with financial performance?

- [ ] Q1: Average R&D spend and R&D % of revenue by sector (2012-2015)
- [ ] Q2: Year-over-year R&D growth by sector
- [ ] Q3: Top 20 companies by R&D % of revenue
- [ ] Q4: R&D intensity vs net income margin (by company, averaged across years)
- [ ] Q5: Revenue growth 2012-2015 for high vs low R&D spenders
- [ ] Q6: Market cap tier breakdown of R&D spending
- [ ] Q7: Companies with consistently high R&D (all 4 years above sector median)

---

## Phase 2 - Python Analysis Script (analysis.py)
Pull query results from MySQL and produce charts.

- [ ] Connect to DB and run each query from Phase 1
- [ ] Chart 1: Bar chart - avg R&D % of revenue by sector
- [ ] Chart 2: Line chart - R&D spend trend 2012-2015 by sector
- [ ] Chart 3: Scatter plot - R&D % of revenue vs net income margin
- [ ] Chart 4: Bar chart - top 15 companies by R&D % of revenue
- [ ] Save all charts to output/ folder as PNG files

---

## Phase 3 - README.md
Write a recruiter-ready README following the project template.

- [ ] Project overview (1-2 sentences, the "so what")
- [ ] Tech stack section
- [ ] How to run section (schema -> load -> analysis)
- [ ] Key findings section (fill in after analysis runs)
- [ ] What I learned section

---

## Phase 4 - Polish and GitHub Prep

- [ ] Verify .gitignore excludes data/ and any credentials
- [ ] Remove password from load_data.py (move to .env or prompt at runtime)
- [ ] Clean up any debug prints
- [ ] Add output/ folder with sample charts committed (so README images work)
- [ ] Final review: would a recruiter reading this on GitHub be impressed?
- [ ] Initialize git repo and push to GitHub

---

## Notes

- Data source: Kaggle - dgawlik/nyse (NYSE fundamentals, SEC 10-K filings 2012-2015)
- 251 companies, 5 sectors, 852 rows of financial + R&D data
- The password in load_data.py needs to be handled before any public commit
