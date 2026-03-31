-- Add LemonSqueezy billing columns to companies table
-- and create webhook events audit table for idempotency

-- 1. Normalize existing plan values
UPDATE companies SET plan = 'pro' WHERE plan IN ('premium', 'enterprise');

-- 2. Add subscription columns to companies
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS ls_customer_id TEXT,
  ADD COLUMN IF NOT EXISTS ls_subscription_id TEXT,
  ADD COLUMN IF NOT EXISTS ls_subscription_status TEXT DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS subscription_renews_at TIMESTAMPTZ;

UPDATE companies SET plan = 'free' WHERE plan IS NULL;
UPDATE companies SET ls_subscription_status = 'none' WHERE ls_subscription_status IS NULL;

-- 3. Create webhook events audit table (idempotency + audit trail)
CREATE TABLE IF NOT EXISTS webhook_events (
  id TEXT PRIMARY KEY,
  event_id TEXT UNIQUE NOT NULL,
  event_name TEXT NOT NULL,
  company_id TEXT,
  ls_subscription_id TEXT,
  processed BOOLEAN DEFAULT TRUE,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_event_id ON webhook_events (event_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_company_id ON webhook_events (company_id);
