-- =====================================================================
-- GitHub Developer Trends Dashboard: panel queries (PostgreSQL, schema "marts")
-- Use as Power BI "Import" queries (Get Data > PostgreSQL > Advanced options > SQL statement)
-- or in any BI tool. Replace the :params with your tool's parameter syntax.
-- =====================================================================

-- ---------------------------------------------------------------------
-- KPI cards
-- ---------------------------------------------------------------------
SELECT
    COUNT(*)                         AS tracked_repositories,
    SUM(stars)                       AS total_stars,
    COUNT(DISTINCT language)         AS languages,
    COUNT(DISTINCT owner_login) FILTER (WHERE is_org_owned) AS organizations
FROM marts.dim_repositories;

-- ---------------------------------------------------------------------
-- Panel 1: Most Starred Repositories (bar chart)
-- ---------------------------------------------------------------------
SELECT
    full_name,
    language,
    stars,
    forks,
    star_rank
FROM marts.dim_repositories
ORDER BY stars DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Panel 2: Top Languages in Repositories (donut / distribution)
-- ---------------------------------------------------------------------
SELECT
    language_name,
    repo_count,
    total_stars,
    pct_of_repos,
    pct_of_stars
FROM marts.dim_languages
ORDER BY repo_count DESC, total_stars DESC;

-- ---------------------------------------------------------------------
-- Panel 3: Developer Activity Over Time (line chart)
-- Daily series with 7-day moving average; filter by language in the BI tool.
-- ---------------------------------------------------------------------
WITH daily AS (
    SELECT
        a.activity_date,
        l.language_name,
        SUM(a.commits)       AS commits,
        SUM(a.new_stars)     AS new_stars,
        SUM(a.prs_opened)    AS prs_opened,
        SUM(a.prs_merged)    AS prs_merged,
        SUM(a.issues_opened) AS issues_opened
    FROM marts.fact_repo_activity a
    JOIN marts.dim_languages l USING (language_key)
    GROUP BY a.activity_date, l.language_name
)
SELECT
    activity_date,
    language_name,
    commits,
    new_stars,
    prs_opened,
    prs_merged,
    issues_opened,
    ROUND(AVG(commits) OVER (
        PARTITION BY language_name
        ORDER BY activity_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS commits_7d_avg
FROM daily
ORDER BY activity_date, language_name;

-- ---------------------------------------------------------------------
-- Panel 4a: Top Contributors (ranked table)
-- ---------------------------------------------------------------------
SELECT
    RANK() OVER (ORDER BY SUM(contributions) DESC) AS rank,
    actor_login                                    AS contributor,
    SUM(commits)                                   AS commits,
    SUM(prs_opened)                                AS prs_opened,
    SUM(prs_merged)                                AS prs_merged,
    SUM(issues_opened)                             AS issues_opened,
    COUNT(DISTINCT repo_id)                        AS repositories,
    SUM(contributions)                             AS total_contributions
FROM marts.fact_contributor_activity
GROUP BY actor_login
ORDER BY total_contributions DESC
LIMIT 25;

-- ---------------------------------------------------------------------
-- Panel 4b: Most Active Organizations (ranked table)
-- ---------------------------------------------------------------------
SELECT
    RANK() OVER (ORDER BY SUM(a.activity_score) DESC) AS rank,
    r.owner_login                                     AS organization,
    COUNT(DISTINCT r.repo_id)                         AS repositories,
    SUM(a.commits)                                    AS commits,
    SUM(a.prs_merged)                                 AS prs_merged,
    SUM(a.new_stars)                                  AS new_stars,
    SUM(a.activity_score)                             AS activity_score
FROM marts.fact_repo_activity a
JOIN marts.dim_repositories r USING (repo_id)
WHERE r.is_org_owned
GROUP BY r.owner_login
ORDER BY activity_score DESC
LIMIT 25;

-- ---------------------------------------------------------------------
-- Bonus: trending repositories, last 7 days vs previous 7 days
-- ---------------------------------------------------------------------
WITH windows AS (
    SELECT
        repo_id,
        SUM(new_stars) FILTER (WHERE activity_date >  current_date - 7)                            AS stars_7d,
        SUM(new_stars) FILTER (WHERE activity_date <= current_date - 7
                                 AND activity_date >  current_date - 14)                           AS stars_prev_7d
    FROM marts.fact_repo_activity
    GROUP BY repo_id
)
SELECT r.full_name, r.language, w.stars_7d, w.stars_prev_7d,
       w.stars_7d - COALESCE(w.stars_prev_7d, 0) AS star_delta
FROM windows w
JOIN marts.dim_repositories r USING (repo_id)
WHERE w.stars_7d IS NOT NULL
ORDER BY star_delta DESC
LIMIT 15;
