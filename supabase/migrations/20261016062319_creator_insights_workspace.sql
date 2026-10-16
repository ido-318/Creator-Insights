-- Creator Insights is a private, server-operated research workspace.
-- The browser never receives a secret key. No public access policies are added.
create table public.creator_snapshots (
    id text primary key check (id ~ '^[a-f0-9]{64}$'),
    captured_at timestamptz not null default now(),
    row_count integer not null check (row_count > 0),
    posts jsonb not null check (jsonb_typeof(posts) = 'array'),
    training jsonb not null check (jsonb_typeof(training) = 'object'),
    reports jsonb not null check (jsonb_typeof(reports) = 'object'),
    constraint snapshot_row_count_matches check (jsonb_array_length(posts) = row_count)
);

create index creator_snapshots_captured_at_idx on public.creator_snapshots (captured_at desc, id desc);
alter table public.creator_snapshots enable row level security;
revoke all on public.creator_snapshots from public, anon, authenticated;
grant select, insert on public.creator_snapshots to service_role;

-- A single transaction writes the dataset, model results and reports together.
-- Content-derived IDs make retries idempotent without replacing past snapshots.
create function public.save_creator_snapshot(payload jsonb)
returns text
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if payload->>'id' is null
       or payload->>'row_count' is null
       or jsonb_typeof(payload->'posts') is distinct from 'array'
       or jsonb_typeof(payload->'training') is distinct from 'object'
       or jsonb_typeof(payload->'reports') is distinct from 'object' then
        raise exception 'Invalid snapshot payload';
    end if;

    insert into public.creator_snapshots (id, row_count, posts, training, reports)
    values (payload->>'id', (payload->>'row_count')::integer,
            payload->'posts', payload->'training', payload->'reports')
    on conflict (id) do nothing;
    return payload->>'id';
end;
$$;

revoke all on function public.save_creator_snapshot(jsonb) from public, anon, authenticated;
grant execute on function public.save_creator_snapshot(jsonb) to service_role;

comment on table public.creator_snapshots is
    'Immutable research snapshots. JSONB preserves the exact model/report bundle for the small UCI dataset.';
