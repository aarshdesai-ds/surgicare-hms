-- =============================================================================
-- HMS — Migration 006: doctor coverage (one-way)
-- A doctor can "cover for" another: their OPD queue view also shows the covered
-- doctor's patients, but NOT vice-versa. Dr. Pallavi covers Dr. Hetal.
-- Run in the Supabase SQL Editor after 005.
-- =============================================================================

ALTER TABLE public.doctors
    ADD COLUMN IF NOT EXISTS covers_for_doctor_id bigint
        REFERENCES public.doctors (id);

-- Dr. Pallavi N. Patel covers Dr. Hetal Desai's practice.
UPDATE public.doctors
SET covers_for_doctor_id = (
        SELECT id FROM public.doctors WHERE full_name = 'Dr. Hetal Desai'
    )
WHERE full_name = 'Dr. Pallavi N. Patel';
