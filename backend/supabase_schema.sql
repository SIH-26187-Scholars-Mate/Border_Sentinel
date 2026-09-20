-- Border Sentinel production schema for Supabase/Postgres.
-- Run this once in Supabase SQL Editor before starting the backend.

create extension if not exists pgcrypto;

create sequence if not exists public.camera_number_seq;

create table if not exists public.cameras (
  id uuid primary key default gen_random_uuid(),
  camera_number bigint not null default nextval('public.camera_number_seq') unique,
  name text not null check (length(trim(name)) > 0),
  location text not null check (length(trim(location)) > 0),
  latitude double precision,
  longitude double precision,
  stream_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz
);

-- Backfill/upgrade existing installations created before camera_number was added.
alter table public.cameras add column if not exists camera_number bigint;
select setval(
  'public.camera_number_seq',
  coalesce((select max(camera_number) from public.cameras), 1),
  exists (select 1 from public.cameras)
);
update public.cameras set camera_number = nextval('public.camera_number_seq') where camera_number is null;
alter table public.cameras alter column camera_number set default nextval('public.camera_number_seq');
alter table public.cameras alter column camera_number set not null;
create unique index if not exists cameras_camera_number_idx on public.cameras(camera_number);

create table if not exists public.alerts (
  id uuid primary key default gen_random_uuid(),
  camera_id uuid not null references public.cameras(id) on delete cascade,
  alert_type text not null check (alert_type in ('intrusion','unauthorized_vehicle','suspicious_activity','perimeter_breach','unattended_object','other')),
  severity text not null check (severity in ('low','medium','high','critical')),
  confidence double precision not null check (confidence between 0 and 1),
  description text,
  image_url text,
  is_acknowledged boolean not null default false,
  created_at timestamptz not null default now(),
  acknowledged_at timestamptz
);

create index if not exists alerts_created_at_idx on public.alerts(created_at desc);
create index if not exists alerts_camera_id_created_at_idx on public.alerts(camera_id, created_at desc);

-- Backend uses the service-role key, which bypasses RLS. Keep RLS enabled so
-- browser clients can never directly write these tables with the anon key.
alter table public.cameras enable row level security;
alter table public.alerts enable row level security;


create or replace function public.set_camera_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists cameras_updated_at on public.cameras;
create trigger cameras_updated_at
before update on public.cameras
for each row execute function public.set_camera_updated_at();

create table if not exists public.zones (
  id uuid primary key default gen_random_uuid(),
  camera_id uuid not null references public.cameras(id) on delete cascade,
  name text not null,
  points jsonb not null,
  enabled boolean not null default true,
  trigger_object text not null default 'person',
  created_at timestamptz not null default now()
);
create index if not exists zones_camera_idx on public.zones(camera_id);

-- Note: the watchlist feature (and its table) was removed. If you ran an
-- earlier version of this schema and want to drop the leftover table:
--   drop table if exists public.watchlist;

-- Added: tells alerts raised by a live camera worker apart from ones found
-- by analyzing an uploaded recording after the fact (dashboard "Analyze"
-- feature). Existing rows default to 'live' since that's what every alert
-- was before this feature existed.
alter table public.alerts add column if not exists source text not null default 'live'
  check (source in ('live','video_analysis'));
create index if not exists alerts_source_idx on public.alerts(source);
