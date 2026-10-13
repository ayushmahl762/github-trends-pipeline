{# Grain: contributor x repository x UTC day. Bots and unlinked identities are excluded. #}
select
    md5(actor_login || '-' || repo_id::text || '-' || event_date::text)      as contribution_key,
    actor_login,
    repo_id,
    event_date                                                               as activity_date,
    count(*) filter (where event_type = 'commit')                            as commits,
    count(*) filter (where event_type = 'pr_opened')                         as prs_opened,
    count(*) filter (where event_type = 'pr_merged')                         as prs_merged,
    count(*) filter (where event_type = 'issue_opened')                      as issues_opened,
    count(*)                                                                 as contributions
from {{ ref('stg_events') }}
where event_type in ('commit', 'pr_opened', 'pr_merged', 'issue_opened')
  and actor_login <> 'unknown'
  and not is_bot
group by actor_login, repo_id, event_date
