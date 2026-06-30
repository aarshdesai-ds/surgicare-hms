-- =============================================================================
-- HMS — Migration 003: OPD appointments + doctor seed
-- Run in the Supabase SQL Editor after 001 and 002.
-- =============================================================================

-- ---- Seed the doctors (only if the table is empty) --------------------------
-- SurgiCare Hospital, Valsad. Dr. Pallavi covers Dr. Hetal's OB-GYN practice.
INSERT INTO public.doctors (full_name, specialty, consult_fee)
SELECT * FROM (VALUES
    ('Dr. Mitesh Desai', 'orthopedics', 500),
    ('Dr. Hetal Desai', 'obgyn', 600),
    ('Dr. Pallavi N. Patel', 'obgyn', 600)
) AS seed(full_name, specialty, consult_fee)
WHERE NOT EXISTS (SELECT 1 FROM public.doctors);

-- ---- Appointments -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.appointments (
    id            bigint generated always as identity primary key,
    patient_id    bigint not null references public.patients (id),
    doctor_id     bigint not null references public.doctors (id),
    scheduled_at  timestamptz not null,
    duration_min  int not null default 15 check (duration_min between 5 and 480),
    status        text not null default 'booked'
                  check (status in ('booked','checked_in','in_progress',
                                    'completed','cancelled','no_show')),
    reason        text,
    created_by    uuid references public.profiles (id),
    created_at    timestamptz not null default now()
);

CREATE INDEX IF NOT EXISTS idx_appt_doctor_time
    ON public.appointments (doctor_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_appt_patient
    ON public.appointments (patient_id);

-- Prevent two active appointments for the same doctor in overlapping slots,
-- enforced at the database layer so concurrent reception staff cannot
-- double-book. `timestamptz + interval` is STABLE (not IMMUTABLE), so it cannot
-- live inside the GiST index expression. Instead we keep the time range in a
-- `slot` column maintained by a trigger, and exclude on that plain column.
ALTER TABLE public.appointments ADD COLUMN IF NOT EXISTS slot tstzrange;

CREATE OR REPLACE FUNCTION public.set_appointment_slot()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.slot := tstzrange(
        NEW.scheduled_at,
        NEW.scheduled_at + make_interval(mins => NEW.duration_min)
    );
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_appointment_slot ON public.appointments;
CREATE TRIGGER trg_appointment_slot
    BEFORE INSERT OR UPDATE ON public.appointments
    FOR EACH ROW EXECUTE FUNCTION public.set_appointment_slot();

-- Backfill any rows created before the trigger existed.
UPDATE public.appointments
SET slot = tstzrange(scheduled_at, scheduled_at + make_interval(mins => duration_min))
WHERE slot IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'no_doctor_overlap'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT no_doctor_overlap
            EXCLUDE USING gist (doctor_id WITH =, slot WITH &&)
            WHERE (status NOT IN ('cancelled', 'no_show'));
    END IF;
END $$;

-- ---- RLS --------------------------------------------------------------------
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS appt_read_staff ON public.appointments;
CREATE POLICY appt_read_staff ON public.appointments
    FOR SELECT USING (public.is_active_staff());

DROP POLICY IF EXISTS appt_write_staff ON public.appointments;
CREATE POLICY appt_write_staff ON public.appointments
    FOR ALL USING (public.current_app_role() IN ('reception', 'admin', 'doctor'))
    WITH CHECK (public.current_app_role() IN ('reception', 'admin', 'doctor'));
