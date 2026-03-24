-- s&p 500 r&d analysis queries
-- run against sp500_rd after load_data.py has been run

use sp500_rd;


-- q1: avg r&d spend and r&d % of revenue by sector
-- avg() skips nulls automatically, so sectors that rarely report r&d
-- (financials, consumer staples) will have a smaller effective sample
select
    s.sector_name,
    round(avg(r.rd_expense) / 1e9, 2)      as avg_rd_spend_billions,
    round(avg(r.rd_pct_revenue) * 100, 2)  as avg_rd_pct_revenue
from sectors s
join companies c   on c.sector_id   = s.sector_id
join rd_spending r on r.company_id  = c.company_id
group by s.sector_name
order by avg_rd_pct_revenue desc;


-- q2: year-over-year r&d growth by sector (2013-2015 only)
-- 2012 only has ~119 of 251 companies due to incomplete source data,
-- so including it would make 2013 look like a 500%+ growth year.
-- filtering to 2013+ gives a consistent sample and two clean YoY comparisons.
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
order by sector_name, year;


-- q3: top 20 companies by r&d % of revenue (averaged across all 4 years)
-- filters out companies that never reported r&d
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
limit 20;


-- q4: r&d intensity vs net income margin, one row per company
-- this feeds the scatter plot, so sector is included for coloring
-- skips rows where revenue is 0 to avoid divide-by-zero
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
order by avg_rd_pct_revenue desc;


-- q5: revenue growth 2012-2015 for high vs low r&d spenders
-- "high" = avg rd_pct_revenue >= 5% across all years (judgment call)
-- note: only 119 of 251 companies have 2012 revenue data (source limitation),
-- so this result is based on that subset, not the full dataset.
-- pivoting 2012 and 2015 revenue into one row per company to compute growth
with company_rd_class as (
    select
        company_id,
        case
            when avg(rd_pct_revenue) >= 0.05 then 'High R&D'
            else 'Low R&D'
        end as rd_class
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
    rc.rd_class,
    count(*)                                                            as company_count,
    round(avg((re.rev_2015 - re.rev_2012) / re.rev_2012) * 100, 2)   as avg_revenue_growth_pct
from company_rd_class rc
join revenue_endpoints re on re.company_id = rc.company_id
where re.rev_2012 > 0 and re.rev_2015 is not null
group by rc.rd_class
order by rc.rd_class;


-- q6: r&d spending broken down by market cap tier
-- field() forces the order large > mid > small instead of alphabetical
select
    c.market_cap_tier,
    count(distinct c.company_id)           as company_count,
    round(avg(r.rd_expense) / 1e9, 2)      as avg_rd_spend_billions,
    round(avg(r.rd_pct_revenue) * 100, 2)  as avg_rd_pct_revenue
from companies c
join rd_spending r on r.company_id = c.company_id
where r.rd_pct_revenue is not null
group by c.market_cap_tier
order by field(c.market_cap_tier, 'Large', 'Mid', 'Small');


-- q7: companies that were above their sector median in r&d % every single year
-- mysql doesn't have median(), so i'm using row_number + count to find
-- the middle row(s) per sector-year, then averaging them for even-sized groups
with ranked as (
    select
        c.company_id,
        c.ticker,
        c.name,
        s.sector_name,
        r.year,
        r.rd_pct_revenue,
        row_number() over (partition by s.sector_id, r.year order by r.rd_pct_revenue) as rn,
        count(*)     over (partition by s.sector_id, r.year)                           as total
    from companies c
    join sectors s     on s.sector_id  = c.sector_id
    join rd_spending r on r.company_id = c.company_id
    where r.rd_pct_revenue is not null
),
sector_medians as (
    select
        sector_name,
        year,
        avg(rd_pct_revenue) as median_rd_pct
    from ranked
    where rn in (floor((total + 1) / 2), ceil((total + 1) / 2))
    group by sector_name, year
),
above_median as (
    select
        r.company_id,
        r.ticker,
        r.name,
        r.sector_name
    from ranked r
    join sector_medians m on m.sector_name = r.sector_name and m.year = r.year
    where r.rd_pct_revenue > m.median_rd_pct
    group by r.company_id, r.ticker, r.name, r.sector_name
    having count(*) = 4
)
select *
from above_median
order by sector_name, ticker;
