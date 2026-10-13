{# Grain: one row per repository per UTC day with at least one event. #}
with events as (

    select * from {{ ref('stg_events') }}

),

daily as (

    select
        repo_id,
        event_date                                                           as activity_date,
        count(*) filter (where event_type = 'commit')                        as commits,
        count(*) filter (where event_type = 'star')                          as new_stars,
        count(*) filter (where event_type = 'issue_opened')                  as issues_opened,
        count(*) filter (where event_type = 'issue_closed')                  as issues_closed,
        count(*) filter (where event_type = 'pr_opened')                     as prs_opened,
        count(*) filter (where event_type = 'pr_merged')                     as prs_merged,
        count(*) filter (where event_type = 'pr_closed')                     as prs_closed_unmerged,
        count(distinct actor_login) filter (
            where event_type in ('commit', 'pr_opened', 'pr_merged', 'issue_opened')
              and actor_login <> 'unknown' and not is_bot
        )                                                                    as unique_contributors,
        count(*)                                                             as total_events
    from events
    group by repo_id, event_date

)

select
    md5(d.repo_id::text || '-' || d.activity_date::text)                     as activity_key,
    d.repo_id,
    r.language_key,
    d.activity_date,
    d.commits,
    d.new_stars,
    d.issues_opened,
    d.issues_closed,
    d.prs_opened,
    d.prs_merged,
    d.prs_closed_unmerged,
    d.unique_contributors,
    d.total_events,
    -- weighted engagement signal used for ranking "most active"
    (d.commits + 2 * d.prs_opened + 3 * d.prs_merged
       + d.issues_opened + 0.5 * d.new_stars)::numeric(12, 1)                as activity_score
from daily d
inner join {{ ref('dim_repositories') }} r on r.repo_id = d.repo_id
