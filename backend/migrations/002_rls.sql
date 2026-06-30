-- =============================================================================
-- HMS — Migration 002: Row-Level Security (RLS)
-- RLS protects the *browser → Supabase* path (anon/auth keys). The FastAPI
-- backend connects with a privileged role and bypasses these policies, so it
-- remains responsible for business rules + audit logging.
-- =============================================================================

-- Helper: the role of the currently authenticated Supabase user.
-- SECURITY DEFINER so it can read profiles regardless of the caller's policies.
create or replace function public.current_app_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
    select role from public.profiles where id = auth.uid();
$$;

create or replace function public.is_active_staff()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select coalesce((select is_active from public.profiles where id = auth.uid()), false);
$$;

-- ---- profiles ---------------------------------------------------------------
alter table public.profiles enable row level security;

drop policy if exists profiles_select_self_or_admin on public.profiles;
create policy profiles_select_self_or_admin on public.profiles
    for select using (id = auth.uid() or public.current_app_role() = 'admin');

drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles
    for update using (id = auth.uid())
    with check (id = auth.uid());

-- Only admins can change roles / create profiles directly.
drop policy if exists profiles_admin_all on public.profiles;
create policy profiles_admin_all on public.profiles
    for all using (public.current_app_role() = 'admin')
    with check (public.current_app_role() = 'admin');

-- ---- doctors ----------------------------------------------------------------
alter table public.doctors enable row level security;

drop policy if exists doctors_read_staff on public.doctors;
create policy doctors_read_staff on public.doctors
    for select using (public.is_active_staff());

drop policy if exists doctors_write_admin on public.doctors;
create policy doctors_write_admin on public.doctors
    for all using (public.current_app_role() = 'admin')
    with check (public.current_app_role() = 'admin');

-- ---- patients ---------------------------------------------------------------
alter table public.patients enable row level security;

-- Any active clinical/admin staff may read patients.
drop policy if exists patients_read_staff on public.patients;
create policy patients_read_staff on public.patients
    for select using (public.is_active_staff());

-- Only reception/admin may create or edit patient demographics.
drop policy if exists patients_insert on public.patients;
create policy patients_insert on public.patients
    for insert with check (public.current_app_role() in ('reception','admin'));

drop policy if exists patients_update on public.patients;
create policy patients_update on public.patients
    for update using (public.current_app_role() in ('reception','admin'))
    with check (public.current_app_role() in ('reception','admin'));

-- ---- audit_log (append-only) ------------------------------------------------
alter table public.audit_log enable row level security;

-- Anyone authenticated can append; nobody can update/delete; only admin reads.
drop policy if exists audit_insert on public.audit_log;
create policy audit_insert on public.audit_log
    for insert with check (auth.uid() is not null);

drop policy if exists audit_admin_read on public.audit_log;
create policy audit_admin_read on public.audit_log
    for select using (public.current_app_role() = 'admin');
-- (No update/delete policies → those operations are denied for non-superusers.)
