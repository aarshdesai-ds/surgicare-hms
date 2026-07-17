-- =============================================================================
-- HMS — Migration 009: name the real theatres + restrict the Labor Room
-- SurgiCare has a standard Operation Theatre (any specialty) and a Labor Room
-- (OB-GYN only). Run in the Supabase SQL Editor after 008.
-- =============================================================================

ALTER TABLE public.operation_theatres
    ADD COLUMN IF NOT EXISTS obgyn_only boolean NOT NULL DEFAULT false;

-- Rename the generic seeds to the real rooms and set the restriction.
UPDATE public.operation_theatres
SET name = 'Operation Theatre', obgyn_only = false WHERE name = 'OT-1';

UPDATE public.operation_theatres
SET name = 'Labor Room', obgyn_only = true WHERE name = 'OT-2';
