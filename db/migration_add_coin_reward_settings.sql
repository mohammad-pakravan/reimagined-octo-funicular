-- Migration: Add Coin Reward Settings System
-- Date: 2025-11-09
-- This migration adds the coin_reward_settings table for managing coin rewards for different activities

CREATE TABLE IF NOT EXISTS coin_reward_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    activity_type VARCHAR(50) NOT NULL UNIQUE,
    coins_amount INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    description VARCHAR(200) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_activity_type (activity_type),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default values
INSERT INTO coin_reward_settings (activity_type, coins_amount, description, is_active) VALUES
('daily_login', 10, 'ورود روزانه', TRUE),
('chat_success', 50, 'چت موفق', TRUE),
('mutual_like', 100, 'لایک متقابل', TRUE),
('referral_referrer', 500, 'دعوت‌کننده', TRUE),
('referral_referred', 200, 'دعوت‌شده', TRUE)
ON DUPLICATE KEY UPDATE coins_amount=VALUES(coins_amount);

