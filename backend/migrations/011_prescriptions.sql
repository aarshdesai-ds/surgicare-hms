-- =============================================================================
-- HMS — Migration 011: prescriptions + pharmacy outbox
-- The doctor prescribes structured medicines; each prescription is queued in
-- pharmacy_outbox as a standard JSON payload for delivery to Visual Chemist
-- (via whatever transport the vendor supports — adapter seam on the app side).
-- Run in the Supabase SQL Editor after 010.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.prescriptions (
    id           bigint generated always as identity primary key,
    patient_id   bigint not null references public.patients (id),
    doctor_id    bigint references public.doctors (id),
    encounter_id bigint references public.encounters (id),
    notes        text,
    created_by   uuid references public.profiles (id),
    created_at   timestamptz not null default now()
);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient
    ON public.prescriptions (patient_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.prescription_items (
    id              bigint generated always as identity primary key,
    prescription_id bigint not null references public.prescriptions (id) ON DELETE CASCADE,
    position        int not null default 1,
    drug_name       text not null,
    strength        text,
    frequency       text,          -- e.g. 1-0-1, BD, TDS
    duration        text,          -- e.g. 5 days
    quantity        text,          -- e.g. 10, 1 bottle
    instructions    text           -- e.g. after food
);
CREATE INDEX IF NOT EXISTS idx_presc_items ON public.prescription_items (prescription_id);

-- Delivery queue to the pharmacy. payload is the frozen export snapshot.
CREATE TABLE IF NOT EXISTS public.pharmacy_outbox (
    id              bigint generated always as identity primary key,
    prescription_id bigint not null references public.prescriptions (id),
    status          text not null default 'pending'
                    check (status in ('pending','sent','failed')),
    payload         jsonb not null,
    attempts        int not null default 0,
    last_error      text,
    created_at      timestamptz not null default now(),
    sent_at         timestamptz
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON public.pharmacy_outbox (status, created_at);

-- ---- RLS --------------------------------------------------------------------
DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['prescriptions','prescription_items','pharmacy_outbox'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I_read ON public.%I', tbl, tbl);
    EXECUTE format(
      'CREATE POLICY %I_read ON public.%I FOR SELECT USING (public.is_active_staff())',
      tbl, tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON public.%I', tbl, tbl);
    EXECUTE format(
      'CREATE POLICY %I_write ON public.%I FOR ALL '
      'USING (public.current_app_role() IN (''reception'',''admin'',''doctor'',''nurse'')) '
      'WITH CHECK (public.current_app_role() IN (''reception'',''admin'',''doctor'',''nurse''))',
      tbl, tbl);
  END LOOP;
END $$;
