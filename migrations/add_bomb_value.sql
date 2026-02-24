-- Migration: Add bomb_value to locations table
-- Run this SQL to add the bomb_value column to existing locations

ALTER TABLE locations ADD COLUMN bomb_value INTEGER NOT NULL DEFAULT 1;

-- Update existing locations with calculated bomb values
-- This will be calculated dynamically based on total locations
UPDATE locations 
SET bomb_value = 1;
