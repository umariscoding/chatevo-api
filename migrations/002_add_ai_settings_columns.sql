-- Add AI settings columns to companies table
ALTER TABLE companies ADD COLUMN IF NOT EXISTS default_model text DEFAULT 'Llama-instant';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS system_prompt text;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tone text DEFAULT 'professional';
