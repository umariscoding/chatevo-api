-- Migration: Alter messages.timestamp column from integer to bigint
-- Reason: Support millisecond-precision timestamps which exceed 32-bit integer range
-- Date: 2026-03-13

-- Alter the timestamp column to support millisecond timestamps
ALTER TABLE messages ALTER COLUMN timestamp SET DATA TYPE bigint;
