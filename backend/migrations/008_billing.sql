-- =============================================================================
-- HMS — Migration 008: Billing framework (catalog, invoices, line items, payments)
-- Structure only — prices are placeholders (edit in the Price list screen once
-- the staff interviews are done). Run in the Supabase SQL Editor after 007.
-- =============================================================================

-- ---- Service catalog (billable items + prices) ------------------------------
CREATE TABLE IF NOT EXISTS public.service_catalog (
    id          bigint generated always as identity primary key,
    code        text unique,
    name        text not null,
    category    text not null default 'other'
                check (category in ('consultation','procedure','bed','ot',
                                    'lab','pharmacy','other')),
    unit_price  numeric(10,2) not null default 0,
    gst_rate    numeric(5,2) not null default 0,   -- most healthcare is exempt
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

-- Placeholder items (price 0 — set real prices later). Seeded only if empty.
INSERT INTO public.service_catalog (code, name, category, unit_price)
SELECT * FROM (VALUES
    ('CONSULT',   'Consultation',                 'consultation', 0),
    ('FOLLOWUP',  'Follow-up consultation',       'consultation', 0),
    ('INJECTION', 'Injection',                    'procedure',    0),
    ('DRESSING',  'Dressing',                     'procedure',    0),
    ('BED_GEN',   'Bed charge — General (/day)',  'bed',          0),
    ('OT_MINOR',  'OT charge — Minor procedure',  'ot',           0)
) AS seed(code, name, category, unit_price)
WHERE NOT EXISTS (SELECT 1 FROM public.service_catalog);

-- ---- Invoices ---------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS public.invoice_no_seq;

CREATE TABLE IF NOT EXISTS public.invoices (
    id           bigint generated always as identity primary key,
    invoice_no   text unique,               -- assigned on finalize
    patient_id   bigint not null references public.patients (id),
    status       text not null default 'draft'
                 check (status in ('draft','finalized','partially_paid',
                                   'paid','cancelled')),
    subtotal     numeric(12,2) not null default 0,
    tax_total    numeric(12,2) not null default 0,
    discount     numeric(12,2) not null default 0,
    grand_total  numeric(12,2) not null default 0,
    amount_paid  numeric(12,2) not null default 0,
    notes        text,
    created_by   uuid references public.profiles (id),
    created_at   timestamptz not null default now(),
    finalized_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_invoices_patient ON public.invoices (patient_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON public.invoices (status);

CREATE TABLE IF NOT EXISTS public.invoice_line_items (
    id          bigint generated always as identity primary key,
    invoice_id  bigint not null references public.invoices (id) ON DELETE CASCADE,
    service_id  bigint references public.service_catalog (id),
    description text not null,
    source      text not null default 'manual'
                check (source in ('manual','consultation','bed','ot',
                                  'pharmacy','lab')),
    source_ref  text,                        -- idempotency key (e.g. pharmacy bill)
    quantity    numeric(10,2) not null default 1,
    unit_price  numeric(10,2) not null,
    gst_rate    numeric(5,2) not null default 0,
    line_total  numeric(12,2) not null
);
CREATE INDEX IF NOT EXISTS idx_line_items_invoice
    ON public.invoice_line_items (invoice_id);

CREATE TABLE IF NOT EXISTS public.payments (
    id           bigint generated always as identity primary key,
    invoice_id   bigint not null references public.invoices (id),
    amount       numeric(12,2) not null check (amount > 0),
    method       text not null default 'cash'
                 check (method in ('cash','card','upi','netbanking',
                                   'razorpay','other')),
    reference    text,
    received_by  uuid references public.profiles (id),
    received_at  timestamptz not null default now()
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON public.payments (invoice_id);

-- ---- RLS --------------------------------------------------------------------
ALTER TABLE public.service_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoice_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS catalog_read ON public.service_catalog;
CREATE POLICY catalog_read ON public.service_catalog
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS catalog_write ON public.service_catalog;
CREATE POLICY catalog_write ON public.service_catalog
    FOR ALL USING (public.current_app_role() IN ('billing','admin'))
    WITH CHECK (public.current_app_role() IN ('billing','admin'));

DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['invoices','invoice_line_items','payments'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I_read ON public.%I', tbl, tbl);
    EXECUTE format(
      'CREATE POLICY %I_read ON public.%I FOR SELECT USING (public.is_active_staff())',
      tbl, tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON public.%I', tbl, tbl);
    EXECUTE format(
      'CREATE POLICY %I_write ON public.%I FOR ALL '
      'USING (public.current_app_role() IN (''billing'',''admin'',''reception'')) '
      'WITH CHECK (public.current_app_role() IN (''billing'',''admin'',''reception''))',
      tbl, tbl);
  END LOOP;
END $$;
