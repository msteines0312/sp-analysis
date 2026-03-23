-- =============================================================
-- S&P 500 R&D and Financial Performance Analysis
-- Schema: 4 normalized tables, joined on company_id
-- Source: NYSE Fundamentals dataset (Kaggle, dgawlik/nyse)
--         SEC 10-K filings, 2012-2015
-- =============================================================

create database if not exists sp500_rd;
use sp500_rd;

-- -------------------------------------------------------------
-- sectors
-- One row per GICS sector in scope.
-- rd_intensity is assigned based on sector-level R&D behavior
-- (populated manually after load_data.py runs).
-- -------------------------------------------------------------
create table if not exists sectors (
    sector_id       int             not null auto_increment,
    sector_name     varchar(100)    not null,
    rd_intensity    enum('High', 'Medium', 'Low') not null,
    primary key (sector_id),
    unique key uq_sector_name (sector_name)
);

-- -------------------------------------------------------------
-- companies
-- One row per S&P 500 company in our 5 target sectors.
-- market_cap_tier is derived from average annual revenue:
--   Large  = avg revenue > $10B
--   Mid    = $1B - $10B
--   Small  = < $1B
-- -------------------------------------------------------------
create table if not exists companies (
    company_id      int             not null auto_increment,
    ticker          varchar(10)     not null,
    name            varchar(200),
    sector_id       int             not null,
    market_cap_tier enum('Large', 'Mid', 'Small') not null,
    primary key (company_id),
    unique key uq_ticker (ticker),
    constraint fk_companies_sector
        foreign key (sector_id) references sectors (sector_id)
);

-- -------------------------------------------------------------
-- financials
-- Annual income statement data per company per year.
-- Values are in USD (raw from 10-K filings).
-- -------------------------------------------------------------
create table if not exists financials (
    financial_id    int             not null auto_increment,
    company_id      int             not null,
    year            smallint        not null,
    revenue         bigint,
    net_income      bigint,
    operating_income bigint,
    primary key (financial_id),
    unique key uq_company_year (company_id, year),
    constraint fk_financials_company
        foreign key (company_id) references companies (company_id)
);

-- -------------------------------------------------------------
-- rd_spending
-- R&D expense per company per year, plus R&D as a % of revenue.
-- rd_pct_revenue is computed at load time to avoid recalculating
-- it across every analytical query.
-- Zero values = company did not separately report R&D expense
-- (common in Financials and Consumer Staples).
-- -------------------------------------------------------------
create table if not exists rd_spending (
    rd_id           int             not null auto_increment,
    company_id      int             not null,
    year            smallint        not null,
    rd_expense      bigint,
    rd_pct_revenue  decimal(8, 4),      -- e.g. 0.1523 = 15.23%
    primary key (rd_id),
    unique key uq_rd_company_year (company_id, year),
    constraint fk_rd_company
        foreign key (company_id) references companies (company_id)
);
