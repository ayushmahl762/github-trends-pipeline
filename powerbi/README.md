# Power BI Dashboard: GitHub Developer Trends

This directory contains the Power BI report and documentation for the GitHub Developer Trends data pipeline.

## 📊 File Overview
* **`github_trends.pbix`**: Complete Power BI Desktop report connected to the PostgreSQL warehouse (`github_trends` database, `marts` schema).

---

## 📑 Dashboard Pages & Panels

### 1. Executive KPIs (Page 1)
High-level summary of the GitHub developer ecosystem tracked by the pipeline:
* **Tracked Repositories:** Distinct count of monitored repositories across targeted programming languages.
* **Total Stars:** Snapshot of cumulative stars.
* **Total Commits:** Sum of all processed commit events.
* **PRs Merged / Activity Metrics:** Snapshot of community pull request engagement.

### 2. Repository Rankings (Page 2 & Page 4)
* **Most Starred Repositories:** Clustered bar chart comparing star counts across repositories.
* **Top Repositories by Activity:** Visualizes high-velocity developer activity.

### 3. Slicer / Interactive Filtering (Page 3)
* **Language Slicer:** Interactive multi-select and dropdown filters to drill down into specific ecosystems (Python, TypeScript, Rust, Go, Java, C++, C#, JavaScript).

### 4. Language Distribution (Page 5)
* **Donut Chart:** Share of tracked repositories and total stars grouped by programming language (`marts.dim_languages`).

### 5. Developer Activity Over Time (Page 6)
* **Line Chart:** Daily time-series tracking commit volume, merged PRs, and star growth over time.

### 6. Contributor & Community Leaderboards (`contributer` Page)
* **Top Contributors Table:** Ranked developer contributions (`actor_login`, commit count, PRs merged, total contributions).
* **Most Active Organizations Table:** Activity scores across GitHub organizations (excluding automated bot accounts).

---

## 🛠️ Data Model & Relationships
The report connects to PostgreSQL warehouse via DirectQuery or Import mode on `localhost:5433` (database `github_trends`):
* `marts.dim_repositories` (1) $\rightarrow$ `marts.fact_repo_activity` ($\infty$) on `repo_id`
* `marts.dim_languages` (1) $\rightarrow$ `marts.fact_repo_activity` ($\infty$) on `language_key`
* `marts.dim_repositories` (1) $\rightarrow$ `marts.fact_contributor_activity` ($\infty$) on `repo_id`
* `marts.dim_languages` (1) $\rightarrow$ `marts.dim_repositories` ($\infty$) on `language_key`

---

## 🔄 Refreshing the Report
1. Ensure the Docker pipeline is running:
   ```bash
   make up
   ```
2. Open `github_trends.pbix` in Power BI Desktop.
3. Click **Home > Refresh** to pull the latest transformed data from dbt marts.
