-- =============================================================================
-- HMS — Migration 010: inpatient beds, wards, and admissions
-- SurgiCare's real rooms: 201-206 & 302-304 special (1 bed); 207 general (3);
-- 301 semi-special (2). Run in the Supabase SQL Editor after 009.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.beds (
    id           bigint generated always as identity primary key,
    room_no      text not null,
    bed_label    text not null unique,
    ward_type    text not null check (ward_type in ('special','semi_special','general')),
    daily_charge numeric(10,2) not null default 0,   -- set real rates later
    status       text not null default 'available'
                 check (status in ('available','occupied','reserved','maintenance')),
    is_active    boolean not null default true
);

INSERT INTO public.beds (room_no, bed_label, ward_type)
SELECT * FROM (VALUES
    ('201','201','special'), ('202','202','special'), ('203','203','special'),
    ('204','204','special'), ('205','205','special'), ('206','206','special'),
    ('207','207-A','general'), ('207','207-B','general'), ('207','207-C','general'),
    ('301','301-A','semi_special'), ('301','301-B','semi_special'),
    ('302','302','special'), ('303','303','special'), ('304','304','special')
) AS seed(room_no, bed_label, ward_type)
WHERE NOT EXISTS (SELECT 1 FROM public.beds);

CREATE TABLE IF NOT EXISTS public.admissions (
    id                  bigint generated always as identity primary key,
    patient_id          bigint not null references public.patients (id),
    attending_doctor_id bigint references public.doctors (id),
    bed_id              bigint not null references public.beds (id),
    status              text not null default 'admitted'
                        check (status in ('admitted','discharged')),
    diagnosis           text,
    discharge_summary   text,
    admitted_at         timestamptz not null default now(),
    discharged_at       timestamptz,
    created_by          uuid references public.profiles (id),
    created_at          timestamptz not null default now()
);
CREATE INDEX IF NOT EXISTS idx_admissions_bed ON public.admissions (bed_id);
CREATE INDEX IF NOT EXISTS idx_admissions_patient ON public.admissions (patient_id);
-- Only one active admission per bed.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_admission_per_bed
    ON public.admissions (bed_id) WHERE (status = 'admitted');

-- ---- RLS --------------------------------------------------------------------
ALTER TABLE public.beds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS beds_read ON public.beds;
CREATE POLICY beds_read ON public.beds
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS beds_write ON public.beds;
CREATE POLICY beds_write ON public.beds
    FOR ALL USING (public.current_app_role() IN ('reception','admin','doctor','nurse'))
    WITH CHECK (public.current_app_role() IN ('reception','admin','doctor','nurse'));

DROP POLICY IF EXISTS adm_read ON public.admissions;
CREATE POLICY adm_read ON public.admissions
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS adm_write ON public.admissions;
CREATE POLICY adm_write ON public.admissions
    FOR ALL USING (public.current_app_role() IN ('reception','admin','doctor','nurse'))
    WITH CHECK (public.current_app_role() IN ('reception','admin','doctor','nurse'));
