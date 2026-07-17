-- =============================================================================
-- HMS — Migration 005: Operation Theatre (OT) scheduling — daily ordered lists
-- Each theatre has an ordered list of cases per day (1st case, 2nd case, ...),
-- with surgeon, patient and procedure. Run in the Supabase SQL Editor after 004.
-- =============================================================================

-- ---- Theatres (seed OT-1, OT-2) ---------------------------------------------
CREATE TABLE IF NOT EXISTS public.operation_theatres (
    id         bigint generated always as identity primary key,
    name       text not null unique,
    obgyn_only boolean not null default false,  -- Labor Room = OB-GYN only
    is_active  boolean not null default true
);

INSERT INTO public.operation_theatres (name, obgyn_only)
SELECT * FROM (VALUES
    ('Operation Theatre', false),
    ('Labor Room', true)
) AS seed(name, obgyn_only)
WHERE NOT EXISTS (SELECT 1 FROM public.operation_theatres);

-- ---- OT cases (ordered list per theatre per day) ----------------------------
CREATE TABLE IF NOT EXISTS public.ot_cases (
    id           bigint generated always as identity primary key,
    theatre_id   bigint not null references public.operation_theatres (id),
    case_date    date not null,
    patient_id   bigint not null references public.patients (id),
    surgeon_id   bigint not null references public.doctors (id),
    procedure    text not null,
    position     int not null,          -- order within the theatre's day list
    status       text not null default 'scheduled'
                 check (status in ('scheduled','in_progress','completed','cancelled')),
    notes        text,
    started_at   timestamptz,
    completed_at timestamptz,
    created_by   uuid references public.profiles (id),
    created_at   timestamptz not null default now()
);
CREATE INDEX IF NOT EXISTS idx_ot_theatre_date
    ON public.ot_cases (theatre_id, case_date, position);
CREATE INDEX IF NOT EXISTS idx_ot_patient ON public.ot_cases (patient_id);

-- ---- RLS --------------------------------------------------------------------
ALTER TABLE public.operation_theatres ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ot_cases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS theatres_read_staff ON public.operation_theatres;
CREATE POLICY theatres_read_staff ON public.operation_theatres
    FOR SELECT USING (public.is_active_staff());

DROP POLICY IF EXISTS ot_read_staff ON public.ot_cases;
CREATE POLICY ot_read_staff ON public.ot_cases
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS ot_write_staff ON public.ot_cases;
CREATE POLICY ot_write_staff ON public.ot_cases
    FOR ALL USING (public.current_app_role() IN ('reception','admin','doctor'))
    WITH CHECK (public.current_app_role() IN ('reception','admin','doctor'));
