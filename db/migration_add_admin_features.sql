-- Migration: Add Admin Features (Referral Links, Coin Settings)
-- Date: 2025-01-XX
-- This migration adds tables for admin features including referral links with statistics and coin price settings

-- Create admin_referral_links table - Track referral links created by admins
CREATE TABLE IF NOT EXISTS admin_referral_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL, -- Telegram ID of admin who created the link
    link_code VARCHAR(50) NOT NULL UNIQUE, -- Unique code for the link (e.g., "summer2024")
    link_url VARCHAR(512) NOT NULL, -- Full referral link URL
    description TEXT, -- Optional description for the link
    click_count INT DEFAULT 0 NOT NULL, -- Number of times link was clicked
    signup_count INT DEFAULT 0 NOT NULL, -- Number of users who signed up via this link
    is_active BOOLEAN DEFAULT TRUE NOT NULL, -- Whether link is active
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_link_code (link_code),
    INDEX idx_admin_id (admin_id),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create admin_referral_link_clicks table - Track individual clicks on admin referral links
CREATE TABLE IF NOT EXISTS admin_referral_link_clicks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    link_id INT NOT NULL,
    telegram_id BIGINT, -- Telegram ID of user who clicked (NULL if not logged in)
    ip_address VARCHAR(45), -- IP address (IPv4 or IPv6)
    user_agent TEXT, -- User agent string
    clicked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (link_id) REFERENCES admin_referral_links(id) ON DELETE CASCADE,
    INDEX idx_link_id (link_id),
    INDEX idx_clicked_at (clicked_at),
    INDEX idx_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create admin_referral_link_signups table - Track signups via admin referral links
CREATE TABLE IF NOT EXISTS admin_referral_link_signups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    link_id INT NOT NULL,
    user_id INT NOT NULL, -- User ID who signed up
    clicked_at DATETIME, -- When they clicked the link (if available)
    signed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (link_id) REFERENCES admin_referral_links(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_link (link_id, user_id),
    INDEX idx_link_id (link_id),
    INDEX idx_user_id (user_id),
    INDEX idx_signed_up_at (signed_up_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create coin_settings table - Store coin prices for premium conversion (admin configurable)
CREATE TABLE IF NOT EXISTS coin_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    premium_days INT NOT NULL UNIQUE, -- Number of premium days (1, 3, 7, 30)
    coins_required INT NOT NULL, -- Number of coins required for this duration
    is_active BOOLEAN DEFAULT TRUE NOT NULL, -- Whether this option is available
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_premium_days (premium_days),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default coin settings (only if not exists - preserves admin changes on restart)
INSERT IGNORE INTO coin_settings (premium_days, coins_required, is_active, created_at, updated_at) VALUES
(1, 200, TRUE, NOW(), NOW()),
(3, 400, TRUE, NOW(), NOW()),
(7, 800, TRUE, NOW(), NOW()),
(30, 3000, TRUE, NOW(), NOW());

-- Create broadcast_messages table - Store broadcast messages with statistics
CREATE TABLE IF NOT EXISTS broadcast_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL, -- Telegram ID of admin who sent the broadcast
    message_type VARCHAR(50) NOT NULL, -- 'text', 'photo', 'video', 'document', 'forward', etc.
    message_text TEXT, -- Text content (if available)
    message_file_id VARCHAR(512), -- Telegram file_id for media
    message_caption TEXT, -- Caption for media
    forwarded_from_chat_id BIGINT, -- If forwarded, original chat ID
    forwarded_from_message_id INT, -- If forwarded, original message ID
    sent_count INT DEFAULT 0 NOT NULL, -- Number of users who received the message
    failed_count INT DEFAULT 0 NOT NULL, -- Number of failed deliveries
    opened_count INT DEFAULT 0 NOT NULL, -- Number of users who opened/interacted with the message
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_admin_id (admin_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create broadcast_message_receipts table - Track individual message deliveries
CREATE TABLE IF NOT EXISTS broadcast_message_receipts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    broadcast_id INT NOT NULL,
    user_id INT NOT NULL,
    telegram_message_id BIGINT, -- Telegram message ID sent to user
    status VARCHAR(50) NOT NULL, -- 'sent', 'failed', 'opened'
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    opened_at DATETIME NULL, -- When user opened/interacted with message
    FOREIGN KEY (broadcast_id) REFERENCES broadcast_messages(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_broadcast_user (broadcast_id, user_id),
    INDEX idx_broadcast_id (broadcast_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

