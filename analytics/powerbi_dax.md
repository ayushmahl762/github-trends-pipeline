# Power BI setup and DAX

## 1. Connect
Get Data > PostgreSQL database. Server `localhost:5433` (the `WAREHOUSE_HOST_PORT` in `.env`),
database `github_trends`, Import mode. Select the four `marts` tables:
`dim_repositories`, `dim_languages`, `fact_repo_activity`, `fact_contributor_activity`.

## 2. Date table (Modeling > New table)
```dax
DimDate =
ADDCOLUMNS(
    CALENDAR(
        MIN(fact_repo_activity[activity_date]),
        MAX(fact_repo_activity[activity_date])
    ),
    "Year",      YEAR([Date]),
    "Month",     FORMAT([Date], "MMM yyyy"),
    "MonthSort", YEAR([Date]) * 100 + MONTH([Date]),
    "Week",      WEEKNUM([Date], 2)
)
```
Mark `DimDate` as a date table on `[Date]`.

## 3. Relationships (all many-to-one, single direction)
| From (many) | To (one) |
|---|---|
| `fact_repo_activity[repo_id]` | `dim_repositories[repo_id]` |
| `fact_repo_activity[language_key]` | `dim_languages[language_key]` |
| `fact_repo_activity[activity_date]` | `DimDate[Date]` |
| `fact_contributor_activity[repo_id]` | `dim_repositories[repo_id]` |
| `fact_contributor_activity[activity_date]` | `DimDate[Date]` |
| `dim_repositories[language_key]` | `dim_languages[language_key]` |

## 4. Measures
```dax
-- Repositories and stars (snapshot measures)
Repo Count      = DISTINCTCOUNT(dim_repositories[repo_id])
Total Stars     = SUM(dim_repositories[stars])
Total Forks     = SUM(dim_repositories[forks])
Org Count       = CALCULATE(DISTINCTCOUNT(dim_repositories[owner_login]), dim_repositories[is_org_owned] = TRUE())

-- Activity (event measures)
Commits         = SUM(fact_repo_activity[commits])
New Stars       = SUM(fact_repo_activity[new_stars])
PRs Opened      = SUM(fact_repo_activity[prs_opened])
PRs Merged      = SUM(fact_repo_activity[prs_merged])
Issues Opened   = SUM(fact_repo_activity[issues_opened])
Activity Score  = SUM(fact_repo_activity[activity_score])

Commits 7D Avg =
AVERAGEX(
    DATESINPERIOD(DimDate[Date], MAX(DimDate[Date]), -7, DAY),
    [Commits]
)

Commits WoW % =
VAR _cur  = CALCULATE([Commits], DATESINPERIOD(DimDate[Date], MAX(DimDate[Date]), -7, DAY))
VAR _prev = CALCULATE([Commits], DATESINPERIOD(DimDate[Date], MAX(DimDate[Date]) - 7, -7, DAY))
RETURN DIVIDE(_cur - _prev, _prev)
```

## 5. Panels

### Most Starred Repositories (clustered bar)
- Axis: `dim_repositories[full_name]`; Values: `[Total Stars]`
- Visual-level filter: Top N = 15 by `[Total Stars]`; sort descending
- Legend (optional): `dim_repositories[language]`
```dax
Star Rank = RANKX(ALL(dim_repositories[full_name]), [Total Stars], , DESC, DENSE)
```

### Top Languages in Repositories (donut)
- Legend: `dim_languages[language_name]`; Values: `[Repo Count]`
```dax
Language Share % =
DIVIDE([Repo Count], CALCULATE([Repo Count], ALL(dim_languages)))

Star Share % =
DIVIDE([Total Stars], CALCULATE([Total Stars], ALL(dim_languages)))
```
Set a Top N of 8 languages and group the rest as "Other" via a visual group.

### Developer Activity Over Time (line)
- X axis: `DimDate[Date]`; Y axis: `[Commits]`, `[Commits 7D Avg]`; Legend: `dim_languages[language_name]`
- Add slicers on `DimDate[Date]` (between) and `dim_languages[language_name]`

### Top Contributors & Active Organizations (tables)
```dax
Contributor Commits      = SUM(fact_contributor_activity[commits])
Contributor PRs Merged   = SUM(fact_contributor_activity[prs_merged])
Contributions            = SUM(fact_contributor_activity[contributions])
Repos Contributed To     = DISTINCTCOUNT(fact_contributor_activity[repo_id])

Contributor Rank =
RANKX(ALL(fact_contributor_activity[actor_login]), [Contributions], , DESC, DENSE)

Org Activity Score =
CALCULATE([Activity Score], dim_repositories[is_org_owned] = TRUE())

Org Rank =
RANKX(
    FILTER(ALL(dim_repositories[owner_login]), CALCULATE(MAX(dim_repositories[is_org_owned])) = TRUE()),
    [Org Activity Score], , DESC, DENSE
)
```
- Contributors table: `actor_login`, `[Contributions]`, `[Contributor Commits]`, `[Contributor PRs Merged]`,
  `[Repos Contributed To]`; Top N = 25 by `[Contributions]`
- Organizations table: `dim_repositories[owner_login]`, `[Org Activity Score]`, `[Commits]`, `[PRs Merged]`,
  `[Repo Count]`; filter `is_org_owned = TRUE`; Top N = 25 by `[Org Activity Score]`

## 6. Refresh
Schedule refresh after the Airflow DAG (daily at 00:00 UTC). With a gateway, point it at the host and
`WAREHOUSE_HOST_PORT`.
