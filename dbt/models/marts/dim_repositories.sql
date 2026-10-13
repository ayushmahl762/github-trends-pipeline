with repos as (

    select * from {{ ref('stg_repos') }}

),

languages as (

    select language_key, language_name from {{ ref('dim_languages') }}

)

select
    r.repo_id,
    r.full_name,
    r.repo_name,
    r.owner_login,
    r.owner_type,
    (r.owner_type = 'Organization')                                          as is_org_owned,
    r.description,
    l.language_key,
    r.language,
    r.stars,
    r.forks,
    r.open_issues,
    r.watchers,
    r.license,
    r.topics,
    r.is_archived,
    r.html_url,
    r.created_at,
    r.pushed_at,
    (current_date - r.created_at::date)                                      as repo_age_days,
    dense_rank() over (order by r.stars desc)                                as star_rank,
    dense_rank() over (partition by r.language order by r.stars desc)        as star_rank_in_language,
    r.ingested_at                                                            as snapshot_at
from repos r
left join languages l on l.language_name = r.language
