-- Voice agent feature: per-company config, availability, bookings, call logs.
-- Twilio auth token and LLM API key are stored encrypted (Fernet, handled in
-- app/core/encryption.py). Identity of the caller company in webhook flows is
-- resolved by unique twilio_phone_number on voice_agent_config.

CREATE TABLE IF NOT EXISTS voice_agent_config (
  company_id TEXT PRIMARY KEY REFERENCES companies(company_id) ON DELETE CASCADE,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  twilio_account_sid TEXT,
  twilio_auth_token_encrypted TEXT,
  twilio_phone_number TEXT UNIQUE,
  greeting TEXT NOT NULL DEFAULT 'Hello, thanks for calling. How can I help you today?',
  system_prompt TEXT NOT NULL DEFAULT 'You are a friendly phone receptionist for a plumbing company. Help the caller book an appointment. Keep responses short and conversational.',
  llm_provider TEXT NOT NULL DEFAULT 'groq',
  llm_model TEXT NOT NULL DEFAULT 'llama-3.3-70b-versatile',
  llm_api_key_encrypted TEXT,
  tts_voice TEXT NOT NULL DEFAULT 'en_US-amy-medium',
  timezone TEXT NOT NULL DEFAULT 'America/New_York',
  default_appointment_duration_minutes INTEGER NOT NULL DEFAULT 60,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voice_agent_config_twilio_number
  ON voice_agent_config (twilio_phone_number);

CREATE TABLE IF NOT EXISTS availability_config (
  company_id TEXT PRIMARY KEY REFERENCES companies(company_id) ON DELETE CASCADE,
  -- weekly_hours: {"mon": {"open": "08:00", "close": "17:00", "enabled": true}, ...}
  weekly_hours JSONB NOT NULL DEFAULT '{
    "mon": {"open": "08:00", "close": "17:00", "enabled": true},
    "tue": {"open": "08:00", "close": "17:00", "enabled": true},
    "wed": {"open": "08:00", "close": "17:00", "enabled": true},
    "thu": {"open": "08:00", "close": "17:00", "enabled": true},
    "fri": {"open": "08:00", "close": "17:00", "enabled": true},
    "sat": {"open": "09:00", "close": "13:00", "enabled": false},
    "sun": {"open": "09:00", "close": "13:00", "enabled": false}
  }'::jsonb,
  slot_granularity_minutes INTEGER NOT NULL DEFAULT 30,
  buffer_minutes INTEGER NOT NULL DEFAULT 15,
  daily_cap INTEGER NOT NULL DEFAULT 8,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bookings (
  booking_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  call_id TEXT,
  customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL,
  service_type TEXT,
  address TEXT,
  notes TEXT,
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bookings_company_starts_at
  ON bookings (company_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_bookings_company_status
  ON bookings (company_id, status);

CREATE TABLE IF NOT EXISTS call_logs (
  call_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  twilio_call_sid TEXT UNIQUE,
  from_number TEXT,
  to_number TEXT,
  direction TEXT DEFAULT 'inbound',
  status TEXT DEFAULT 'initiated',
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at TIMESTAMPTZ,
  duration_seconds INTEGER,
  transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
  booking_id TEXT REFERENCES bookings(booking_id) ON DELETE SET NULL,
  recording_url TEXT,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_call_logs_company_started_at
  ON call_logs (company_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_logs_twilio_sid
  ON call_logs (twilio_call_sid);
