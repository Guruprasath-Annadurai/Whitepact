-- WhitePact production retention control (Supabase/PostgreSQL)
-- Applied to the hosted production database on 2026-09-18.
-- This file is the reproducible source for the provider-specific operational
-- control; it is intentionally separate from application Alembic migrations.

create extension if not exists pg_cron;

create schema if not exists whitepact_ops;
revoke all on schema whitepact_ops from public;
revoke all on schema whitepact_ops from anon;
revoke all on schema whitepact_ops from authenticated;

create table if not exists whitepact_ops.retention_runs (
  id bigint generated always as identity primary key,
  run_at timestamptz not null default now(),
  audit_deleted integer not null default 0,
  token_usage_deleted integer not null default 0,
  trust_scores_deleted integer not null default 0,
  eval_runs_deleted integer not null default 0,
  oauth_requests_deleted integer not null default 0,
  oauth_codes_deleted integer not null default 0,
  oauth_credentials_deleted integer not null default 0,
  status text not null default 'success'
);

create or replace function whitepact_ops.safe_timestamptz(value text)
returns timestamptz
language plpgsql
immutable
as $$
begin
  return value::timestamptz;
exception when others then
  return null;
end;
$$;

create or replace function whitepact_ops.enforce_retention()
returns void
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  n_audit integer := 0;
  n_token integer := 0;
  n_trust integer := 0;
  n_eval integer := 0;
  n_req integer := 0;
  n_code integer := 0;
  n_cred integer := 0;
begin
  delete from public.audit_log
   where whitepact_ops.safe_timestamptz("timestamp") < now() - interval '12 months';
  get diagnostics n_audit = row_count;

  delete from public.token_usage
   where whitepact_ops.safe_timestamptz(recorded_at) < now() - interval '365 days';
  get diagnostics n_token = row_count;

  delete from public.trust_scores
   where whitepact_ops.safe_timestamptz(recorded_at) < now() - interval '365 days';
  get diagnostics n_trust = row_count;

  delete from public.eval_runs
   where whitepact_ops.safe_timestamptz(created_at) < now() - interval '30 days';
  get diagnostics n_eval = row_count;

  delete from public.oauth_authorization_requests
   where whitepact_ops.safe_timestamptz(expires_at) < now() - interval '7 days';
  get diagnostics n_req = row_count;

  delete from public.oauth_authorization_codes
   where whitepact_ops.safe_timestamptz(expires_at) < now() - interval '7 days';
  get diagnostics n_code = row_count;

  delete from public.oauth_credentials
   where whitepact_ops.safe_timestamptz(expires_at) < now() - interval '30 days';
  get diagnostics n_cred = row_count;

  insert into whitepact_ops.retention_runs(
    audit_deleted, token_usage_deleted, trust_scores_deleted, eval_runs_deleted,
    oauth_requests_deleted, oauth_codes_deleted, oauth_credentials_deleted, status
  ) values (n_audit,n_token,n_trust,n_eval,n_req,n_code,n_cred,'success');
exception when others then
  insert into whitepact_ops.retention_runs(status) values ('failed');
  raise;
end;
$$;

revoke all on function whitepact_ops.safe_timestamptz(text) from public;
revoke all on function whitepact_ops.enforce_retention() from public;
revoke all on function whitepact_ops.safe_timestamptz(text) from anon;
revoke all on function whitepact_ops.enforce_retention() from anon;
revoke all on function whitepact_ops.safe_timestamptz(text) from authenticated;
revoke all on function whitepact_ops.enforce_retention() from authenticated;

do $$
declare j record;
begin
  for j in select jobid from cron.job where jobname='whitepact-retention-daily'
  loop
    perform cron.unschedule(j.jobid);
  end loop;
end $$;

select cron.schedule(
  'whitepact-retention-daily',
  '17 3 * * *',
  'select whitepact_ops.enforce_retention();'
);
