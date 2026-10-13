with source as (

    select * from {{ source('raw', 'raw_github_repos') }}

),

deduplicated as (

    select
        *,
        row_number() over (partition by repo_id order by ingested_at desc) as _rn
    from source

),

cleaned as (

    select
        cast(repo_id as bigint)                                   as repo_id,
        trim(full_name)                                           as full_name,
        trim(name)                                                as repo_name,
        trim(owner_login)                                         as owner_login,
        case when lower(owner_type) = 'organization'
             then 'Organization' else 'User' end                  as owner_type,
        nullif(trim(description), '')                             as description,
        coalesce(nullif(trim(language), ''), 'Unknown')           as language,
        coalesce(stargazers_count, 0)::integer                    as stars,
        coalesce(forks_count, 0)::integer                         as forks,
        coalesce(open_issues_count, 0)::integer                   as open_issues,
        coalesce(watchers_count, 0)::integer                      as watchers,
        coalesce(size_kb, 0)::integer                             as size_kb,
        created_at::timestamptz                                   as created_at,
        updated_at::timestamptz                                   as updated_at,
        pushed_at::timestamptz                                    as pushed_at,
        coalesce(nullif(trim(license_spdx), ''), 'NONE')          as license,
        coalesce(topics, '[]'::jsonb)                             as topics,
        coalesce(is_archived, false)                              as is_archived,
        coalesce(is_fork, false)                                  as is_fork,
        default_branch,
        html_url,
        ingested_at::timestamptz                                  as ingested_at
    from deduplicated
    where _rn = 1
      and repo_id is not null
      and full_name is not null

)

select * from cleaned
