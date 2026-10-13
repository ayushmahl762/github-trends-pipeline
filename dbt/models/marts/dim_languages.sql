with repos as (

    select * from {{ ref('stg_repos') }}

),

by_language as (

    select
        language                               as language_name,
        count(*)                               as repo_count,
        sum(stars)                             as total_stars,
        sum(forks)                             as total_forks,
        round(avg(stars), 0)                   as avg_stars_per_repo,
        max(stars)                             as max_stars
    from repos
    group by language

)

select
    md5(language_name)                                                       as language_key,
    language_name,
    repo_count,
    total_stars,
    total_forks,
    avg_stars_per_repo,
    max_stars,
    round(100.0 * repo_count  / sum(repo_count)  over (), 2)                 as pct_of_repos,
    round(100.0 * total_stars / sum(total_stars) over (), 2)                 as pct_of_stars,
    dense_rank() over (order by total_stars desc)                            as star_rank
from by_language
