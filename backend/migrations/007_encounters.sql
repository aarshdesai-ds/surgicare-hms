-- =============================================================================
-- HMS — Migration 007: clinical encounters (consultation notes)
-- A lightweight medical record: vitals + complaints + diagnosis + notes per
-- visit, linked to the patient (and optionally the OPD queue entry / doctor).
-- NOT clinical decision support. Run in the Supabase SQL Editor after 006.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.encounters (
    id             bigint generated always as identity primary key,
    patient_id     bigint not null references public.patients (id),
    doctor_id      bigint references public.doctors (id),
    queue_entry_id bigint references public.queue_entries (id),
    encounter_type text not null default 'opd'
                   check (encounter_type in ('opd','ipd','ot')),
    vitals         jsonb,                 -- {bp, pulse, temp, spo2, weight}
    complaints     text,
    diagnosis      text,
    notes          text,
    occurred_at    timestamptz not null default now(),
    created_by     uuid references public.profiles (id),
    created_at     timestamptz not null default now()
);
CREATE INDEX IF NOT EXISTS idx_encounters_patient
    ON public.encounters (patient_id, occurred_at DESC);

ALTER TABLE public.encounters ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS encounters_read_staff ON public.encounters;
CREATE POLICY encounters_read_staff ON public.encounters
    FOR SELECT USING (public.is_active_staff());

DROP POLICY IF EXISTS encounters_write_staff ON public.encounters;
CREATE POLICY encounters_write_staff ON public.encounters
    FOR ALL USING (public.current_app_role() IN ('reception','admin','doctor'))
    WITH CHECK (public.current_app_role() IN ('reception','admin','doctor'));
