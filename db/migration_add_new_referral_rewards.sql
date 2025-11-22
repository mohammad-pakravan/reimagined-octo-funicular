-- Migration: Add New Referral Reward Settings
-- Date: 2025-11-10
-- This migration adds new referral reward settings for signup and profile completion

-- Insert new referral reward settings (only if not exists - preserves admin changes on restart)
INSERT IGNORE INTO coin_reward_settings (activity_type, coins_amount, description, is_active, created_at, updated_at) VALUES
('referral_signup', 500, 'پاداش دعوت‌کننده با عضویت', TRUE, NOW(), NOW()),
('referral_profile_complete', 200, 'پاداش دعوت‌کننده با تکمیل پروفایل', TRUE, NOW(), NOW()),
('referral_referred_signup', 200, 'پاداش دعوت‌شده با عضویت', TRUE, NOW(), NOW());

