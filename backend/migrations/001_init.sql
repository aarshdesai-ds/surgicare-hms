-- =============================================================================
-- HMS — Migration 001: extensions + core identity & patient tables
-- Run in the Supabase SQL Editor (or via the Supabase CLI).
-- Idempotent where practical so it is safe to re-run during development.
-- =============================================================================

-- ---- Extensions -------------------------------------------------------------
create extension if not exists btree_gist;   -- exclusion constraints (scheduling)
create extension if not exists pgcrypto;      -- gen_random_uuid(), digest()

-- ---- profiles ---------------------------------------------------------------
-- One row per Supabase auth user. Holds role + display info. The `id` mirrors
-- auth.users(id). A trigger (below) auto-creates a profile on signup.
create table if not exists public.profiles (
    id          uuid primary key references auth.users (id) on delete cascade,
    full_name   text,
    phone       text,
    role        text not null default 'reception'
                 check (role in ('admin','doctor','reception','billing','nurse')),
    locale      text not null default 'en' check (locale in ('en','gu')),
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

-- Auto-provision a profile whenever a new auth user is created.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, full_name, phone)
    values (new.id, new.raw_user_meta_data ->> 'full_name',
                     new.raw_user_meta_data ->> 'phone')
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ---- doctors ----------------------------------------------------------------
create table if not exists public.doctors (
    id           bigint generated always as identity primary key,
    profile_id   uuid references public.profiles (id),
    full_name    text not null,
    specialty    text not null check (specialty in ('orthopedics','obgyn')),
    reg_number   text,
    consult_fee  numeric(10,2) not null default 0,
    is_active    boolean not null default true,
    created_at   timestamptz not null default now()
);

-- ---- patients (master index) ------------------------------------------------
create sequence if not exists public.patient_uhid_seq;

create table if not exists public.patients (
    id            bigint generated always as identity primary key,
    uhid          text unique not null
                  default ('HMS-' || to_char(now(),'YYYY') || '-' ||
                           lpad(nextval('public.patient_uhid_seq')::text, 6, '0')),
    first_name    text not null,
    last_name     text,
    dob           date check (dob is null or dob <= current_date),
    gender        text check (gender in ('M','F','O')),
    phone         text not null,
    alt_phone     text,
    address       text,
    blood_group   text,
    abha_number   text,                 -- nullable; ABDM-ready for the future
    emergency_contact jsonb,
    allergies     text,
    created_at    timestamptz not null default now(),
    created_by    uuid references public.profiles (id)
);

create index if not exists idx_patients_phone on public.patients (phone);
create index if not exists idx_patients_name
    on public.patients (lower(first_name), lower(last_name));

-- ---- audit_log (append-only) ------------------------------------------------
create table if not exists public.audit_log (
    id            bigint generated always as identity primary key,
    actor_user_id uuid references public.profiles (id),
    action        text not null,        -- 'create','update','delete','view_phi','login'
    entity        text not null,        -- table name
    entity_id     text,
    detail        jsonb,
    ip_address    inet,
    at            timestamptz not null default now()
);
create index if not exists idx_audit_entity on public.audit_log (entity, entity_id);
create index if not exists idx_audit_at on public.audit_log (at);
