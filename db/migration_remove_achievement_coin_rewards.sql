-- Migration: Remove Achievement Coin Rewards
-- Date: 2025-01-XX
-- This migration removes coin rewards from all achievements
-- Achievements will still award badges, but no longer give coins

-- Update all existing achievements to have 0 points_reward
UPDATE achievements SET points_reward = 0 WHERE points_reward > 0;

