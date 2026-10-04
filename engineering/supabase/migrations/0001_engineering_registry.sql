begin;

create schema if not exists ustracker_eng;
revoke all on schema ustracker_eng from public;
revoke all on schema ustracker_eng from anon;
revoke all on schema ustracker_eng from authenticated;

create table if not exists ustracker_eng.release_baselines (
    id text primary key,
    product text not null,
    version text not null,
    schema_version integer not null check (schema_version >= 0),
    source_sha256 text not null,
    git_commit text not null,
    created_at timestamptz not null default now()
);

create table if not exists ustracker_eng.change_sets (
    id text primary key,
    task_number integer not null,
    title text not null,
    base_commit text not null,
    schema_from integer not null,
    schema_to integer not null,
    status text not null check (status in ('PREPARED','APPROVED','IN_PROGRESS','VERIFIED','REJECTED')),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (schema_to >= schema_from and schema_to <= schema_from + 1)
);

create table if not exists ustracker_eng.verification_runs (
    id text primary key,
    changeset_id text not null references ustracker_eng.change_sets(id),
    git_head text not null,
    status text not null check (status in ('PASS','PARTIAL','FAIL','INCONCLUSIVE')),
    evidence jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists ustracker_eng.migration_runs (
    id text primary key,
    changeset_id text not null references ustracker_eng.change_sets(id),
    schema_from integer not null,
    schema_to integer not null,
    status text not null,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    check (schema_to >= schema_from and schema_to <= schema_from + 1)
);

create table if not exists ustracker_eng.release_candidates (
    id text primary key,
    changeset_id text references ustracker_eng.change_sets(id),
    version text not null,
    schema_version integer not null,
    git_head text not null,
    package_sha256 text,
    status text not null check (status in ('BUILT','VERIFIED','REJECTED','PROMOTED')),
    created_at timestamptz not null default now()
);

create table if not exists ustracker_eng.deployment_events (
    id text primary key,
    candidate_id text references ustracker_eng.release_candidates(id),
    environment text not null,
    event text not null,
    outcome text not null,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

commit;
