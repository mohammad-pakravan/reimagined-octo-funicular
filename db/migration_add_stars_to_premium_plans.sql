-- Migration: Add Stars payment support to premium_plans table
-- Add stars_required and payment_methods_json columns

ALTER TABLE premium_plans
ADD COLUMN stars_required INT NULL COMMENT 'Stars required for payment (null if not available)',
ADD COLUMN payment_methods_json TEXT NULL COMMENT 'JSON array of payment methods: ["shaparak"], ["stars"], or ["shaparak", "stars"]';

-- Update existing plans to have default payment method
UPDATE premium_plans
SET payment_methods_json = '["shaparak"]'
WHERE payment_methods_json IS NULL;

