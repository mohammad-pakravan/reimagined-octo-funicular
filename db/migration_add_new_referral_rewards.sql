-- Migration: Add New Referral Reward Settings
-- Date: 2025-11-10
-- This migration adds new referral reward settings for signup and profile completion

INSERT INTO coin_reward_settings (activity_type, coins_amount, description, is_active) VALUES
('referral_signup', 500, 'پاداش دعوت‌کننده با عضویت', TRUE),
('referral_profile_complete', 200, 'پاداش دعوت‌کننده با تکمیل پروفایل', TRUE),
('referral_referred_signup', 200, 'پاداش دعوت‌شده با عضویت', TRUE)
ON DUPLICATE KEY UPDATE coins_amount=VALUES(coins_amount), description=VALUES(description);

