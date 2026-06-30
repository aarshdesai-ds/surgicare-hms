-- =============================================================================
-- HMS — Migration 004: OPD token-queue model (replaces fixed-slot appointments)
-- Workflow: staff set a doctor's session hours per day; patients are pre-booked
-- or walk in; on check-in they get the next token number and are seen in order.
-- Run in the Supabase SQL Editor after 003.
-- =============================================================================

-- Remove the fixed-slot appointment model.
DROP TABLE IF EXISTS public.appointments CASCADE;
DROP FUNCTION IF EXISTS public.set_appointment_slot() CASCADE;

-- ---- OPD sessions: a doctor's working window for a given day -----------------
CREATE TABLE IF NOT EXISTS public.opd_sessions (
    id           bigint generated always as identity primary key,
    doctor_id    bigint not null references public.doctors (id),
    session_date date not null,
    start_time   time not null,
    end_time     time not null,
    created_by   uuid references public.profiles (id),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    UNIQUE (doctor_id, session_date),
    CHECK (end_time > start_time)
);

-- ---- Queue entries: patients in a doctor's queue for a day -------------------
CREATE TABLE IF NOT EXISTS public.queue_entries (
    id            bigint generated always as identity primary key,
    doctor_id     bigint not null references public.doctors (id),
    patient_id    bigint not null references public.patients (id),
    queue_date    date not null,
    token_no      int,                       -- assigned at check-in (arrival order)
    status        text not null default 'booked'
                  check (status in ('booked','waiting','in_consultation',
                                    'completed','no_show','cancelled')),
    reason        text,
    booked_at     timestamptz not null default now(),
    checked_in_at timestamptz,
    called_at     timestamptz,
    completed_at  timestamptz,
    created_by    uuid references public.profiles (id),
    created_at    timestamptz not null default now()
);
CREATE INDEX IF NOT EXISTS idx_queue_doctor_date
    ON public.queue_entries (doctor_id, queue_date);
CREATE INDEX IF NOT EXISTS idx_queue_patient
    ON public.queue_entries (patient_id);
-- One token number per doctor per day (guards token assignment under races).
CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_token
    ON public.queue_entries (doctor_id, queue_date, token_no)
    WHERE token_no IS NOT NULL;

-- ---- RLS --------------------------------------------------------------------
ALTER TABLE public.opd_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.queue_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sessions_read_staff ON public.opd_sessions;
CREATE POLICY sessions_read_staff ON public.opd_sessions
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS sessions_write_staff ON public.opd_sessions;
CREATE POLICY sessions_write_staff ON public.opd_sessions
    FOR ALL USING (public.current_app_role() IN ('reception','admin','doctor'))
    WITH CHECK (public.current_app_role() IN ('reception','admin','doctor'));

DROP POLICY IF EXISTS queue_read_staff ON public.queue_entries;
CREATE POLICY queue_read_staff ON public.queue_entries
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS queue_write_staff ON public.queue_entries;
CREATE POLICY queue_write_staff ON public.queue_entries
    FOR ALL USING (public.current_app_role() IN ('reception','admin','doctor'))
    WITH CHECK (public.current_app_role() IN ('reception','admin','doctor'));
