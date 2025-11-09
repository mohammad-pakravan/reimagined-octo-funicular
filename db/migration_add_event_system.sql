-- Migration: Add Event System
-- Date: 2025-01-XX
-- This migration adds tables for event system including events, participants, and rewards

-- Create events table - Store admin-created events
CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_key VARCHAR(100) NOT NULL UNIQUE,
    event_name VARCHAR(200) NOT NULL,
    event_description TEXT,
    event_type VARCHAR(50) NOT NULL,  -- 'points_multiplier', 'referral_reward', 'challenge_lottery'
    config_json TEXT,  -- JSON configuration for flexible event rules
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_visible BOOLEAN DEFAULT TRUE NOT NULL,
    created_by_admin_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_event_key (event_key),
    INDEX idx_event_type (event_type),
    INDEX idx_start_end_date (start_date, end_date),
    INDEX idx_is_active (is_active),
    INDEX idx_created_by_admin_id (created_by_admin_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create event_participants table - Track user participation and progress
CREATE TABLE IF NOT EXISTS event_participants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    progress_value INT DEFAULT 0 NOT NULL,
    additional_data TEXT,  -- JSON for flexible data storage
    is_eligible BOOLEAN DEFAULT TRUE NOT NULL,
    has_received_reward BOOLEAN DEFAULT FALSE NOT NULL,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_event_user (event_id, user_id),
    INDEX idx_event_user (event_id, user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_progress_value (progress_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create event_rewards table - Track rewards distributed to users
CREATE TABLE IF NOT EXISTS event_rewards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    reward_type VARCHAR(50) NOT NULL,  -- 'points', 'premium_days', 'badge', 'lottery_win'
    reward_value INT NOT NULL,
    reward_description TEXT,
    is_lottery_winner BOOLEAN DEFAULT FALSE NOT NULL,
    lottery_rank INT,
    awarded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_event_id (event_id),
    INDEX idx_user_id (user_id),
    INDEX idx_reward_type (reward_type),
    INDEX idx_awarded_at (awarded_at),
    INDEX idx_is_lottery_winner (is_lottery_winner)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

