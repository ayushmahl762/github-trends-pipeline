with source as (

    select * from {{ source('raw', 'raw_github_events') }}

),

cleaned as (

    select
        event_id,
        cast(repo_id as bigint)                                   as repo_id,
        trim(repo_full_name)                                      as repo_full_name,
        lower(trim(event_type))                                   as event_type,
        -- unlinked commit emails and deleted accounts have no login
        coalesce(nullif(trim(actor_login), ''), 'unknown')        as actor_login,
        actor_id,
        nullif(trim(org_login), '')                               as org_login,
        event_ts::timestamptz                                     as event_ts,
        (event_ts at time zone 'UTC')::date                       as event_date,
        coalesce(payload, '{}'::jsonb)                            as payload,
        ingested_at::timestamptz                                  as ingested_at,
        coalesce(actor_login ilike '%[bot]', false)               as is_bot
    from source
    where event_id is not null
      and repo_id is not null
      and event_ts is not null

)

select * from cleaned
