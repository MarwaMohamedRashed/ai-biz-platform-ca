-- Migration 004: Add country column to businesses table
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS country TEXT DEFAULT 'Canada';