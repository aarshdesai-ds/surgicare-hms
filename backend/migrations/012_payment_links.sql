-- =============================================================================
-- HMS — Migration 012: Razorpay payment links
-- Tracks online payment links created against invoices so the webhook and the
-- manual "check status" poll can both reconcile a payment exactly once.
-- Run in the Supabase SQL Editor after 011 (or applied directly via asyncpg).
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.payment_links (
    id                  bigint generated always as identity primary key,
    invoice_id          bigint not null references public.invoices (id),
    provider            text not null default 'razorpay',
    provider_link_id    text unique,             -- Razorpay "plink_..."
    short_url           text,                    -- shareable / QR URL
    amount              numeric(12,2) not null check (amount > 0),
    status              text not null default 'created'
                        check (status in ('created','paid','cancelled','expired')),
    provider_payment_id text,                    -- Razorpay "pay_..." once paid
    payment_id          bigint references public.payments (id),  -- recorded payment
    created_by          uuid references public.profiles (id),
    created_at          timestamptz not null default now(),
    paid_at             timestamptz
);
CREATE INDEX IF NOT EXISTS idx_payment_links_invoice
    ON public.payment_links (invoice_id);
CREATE INDEX IF NOT EXISTS idx_payment_links_provider_link
    ON public.payment_links (provider_link_id);

-- ---- RLS --------------------------------------------------------------------
ALTER TABLE public.payment_links ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS payment_links_read ON public.payment_links;
CREATE POLICY payment_links_read ON public.payment_links
    FOR SELECT USING (public.is_active_staff());
DROP POLICY IF EXISTS payment_links_write ON public.payment_links;
CREATE POLICY payment_links_write ON public.payment_links
    FOR ALL USING (public.current_app_role() IN ('billing','admin','reception'))
    WITH CHECK (public.current_app_role() IN ('billing','admin','reception'));
