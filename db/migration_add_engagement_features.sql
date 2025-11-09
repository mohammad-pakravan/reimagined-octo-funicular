-- Migration: Add Engagement Features (Points, Rewards, Referrals, Badges, Achievements, Challenges)
-- Date: 2025-01-XX
-- This migration adds tables for user engagement features including points, daily rewards, referrals, badges, achievements, and weekly challenges

-- Create user_points table - Track user points balance and history
CREATE TABLE IF NOT EXISTS user_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    points INT DEFAULT 0 NOT NULL,
    total_earned INT DEFAULT 0 NOT NULL,
    total_spent INT DEFAULT 0 NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_points (user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_points (points)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create points_history table - Track all point transactions
CREATE TABLE IF NOT EXISTS points_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    points INT NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- 'earned', 'spent', 'reward', 'purchase', 'referral', etc.
    source VARCHAR(100) NOT NULL, -- 'daily_login', 'chat_success', 'mutual_like', 'referral', etc.
    description TEXT,
    related_user_id INT NULL, -- For referrals, mutual likes, etc.
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (related_user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create daily_rewards table - Track daily login rewards and streaks
CREATE TABLE IF NOT EXISTS daily_rewards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    reward_date DATE NOT NULL,
    points_rewarded INT NOT NULL,
    streak_count INT DEFAULT 1 NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_date (user_id, reward_date),
    INDEX idx_user_id (user_id),
    INDEX idx_reward_date (reward_date),
    INDEX idx_streak_count (streak_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create referrals table - Track referral relationships
CREATE TABLE IF NOT EXISTS referrals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    referrer_id INT NOT NULL, -- User who invited
    referred_id INT NOT NULL, -- User who was invited
    referral_code VARCHAR(50) NOT NULL, -- Unique referral code
    points_rewarded_referrer INT DEFAULT 0 NOT NULL,
    points_rewarded_referred INT DEFAULT 0 NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (referred_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_referral (referrer_id, referred_id),
    UNIQUE KEY unique_referral_code (referral_code),
    INDEX idx_referrer_id (referrer_id),
    INDEX idx_referred_id (referred_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create user_referral_codes table - Store each user's referral code
CREATE TABLE IF NOT EXISTS user_referral_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    referral_code VARCHAR(50) NOT NULL,
    usage_count INT DEFAULT 0 NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_code (user_id),
    UNIQUE KEY unique_referral_code (referral_code),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create badges table - Define available badges
CREATE TABLE IF NOT EXISTS badges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    badge_key VARCHAR(50) NOT NULL UNIQUE,
    badge_name VARCHAR(100) NOT NULL,
    badge_description TEXT,
    badge_icon VARCHAR(20), -- Emoji or icon identifier
    badge_type VARCHAR(50) NOT NULL, -- 'achievement', 'milestone', 'special', etc.
    required_points INT NULL, -- Points required to earn (if applicable)
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_badge_key (badge_key),
    INDEX idx_badge_type (badge_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create user_badges table - Track which badges users have earned
CREATE TABLE IF NOT EXISTS user_badges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_id INT NOT NULL,
    earned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_badge (user_id, badge_id),
    INDEX idx_user_id (user_id),
    INDEX idx_badge_id (badge_id),
    INDEX idx_earned_at (earned_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create achievements table - Define achievement types
CREATE TABLE IF NOT EXISTS achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    achievement_key VARCHAR(50) NOT NULL UNIQUE,
    achievement_name VARCHAR(100) NOT NULL,
    achievement_description TEXT,
    achievement_type VARCHAR(50) NOT NULL, -- 'chat_count', 'like_count', 'streak', 'referral', etc.
    target_value INT NOT NULL, -- Target value to achieve (e.g., 10 chats, 5 likes)
    points_reward INT DEFAULT 0 NOT NULL,
    badge_id INT NULL, -- Badge awarded when achievement is unlocked
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE SET NULL,
    INDEX idx_achievement_key (achievement_key),
    INDEX idx_achievement_type (achievement_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create user_achievements table - Track user progress towards achievements
CREATE TABLE IF NOT EXISTS user_achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    achievement_id INT NOT NULL,
    current_progress INT DEFAULT 0 NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_achievement (user_id, achievement_id),
    INDEX idx_user_id (user_id),
    INDEX idx_achievement_id (achievement_id),
    INDEX idx_is_completed (is_completed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create weekly_challenges table - Define weekly challenges
CREATE TABLE IF NOT EXISTS weekly_challenges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    challenge_key VARCHAR(50) NOT NULL UNIQUE,
    challenge_name VARCHAR(100) NOT NULL,
    challenge_description TEXT,
    challenge_type VARCHAR(50) NOT NULL, -- 'chat_count', 'like_count', 'streak', etc.
    target_value INT NOT NULL,
    points_reward INT NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_challenge_key (challenge_key),
    INDEX idx_week_dates (week_start_date, week_end_date),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create user_challenges table - Track user progress in weekly challenges
CREATE TABLE IF NOT EXISTS user_challenges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_id INT NOT NULL,
    current_progress INT DEFAULT 0 NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE NOT NULL,
    completed_at DATETIME NULL,
    points_rewarded INT DEFAULT 0 NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (challenge_id) REFERENCES weekly_challenges(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_challenge (user_id, challenge_id),
    INDEX idx_user_id (user_id),
    INDEX idx_challenge_id (challenge_id),
    INDEX idx_is_completed (is_completed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default badges
INSERT IGNORE INTO badges (badge_key, badge_name, badge_description, badge_icon, badge_type) VALUES
('first_chat', 'First Chat', 'Completed your first chat', '💬', 'milestone'),
('chat_master', 'Chat Master', 'Completed 50 chats', '🎯', 'milestone'),
('social_butterfly', 'Social Butterfly', 'Received 100 likes', '🦋', 'milestone'),
('popular', 'Popular', 'Received 500 likes', '⭐', 'milestone'),
('streak_7', 'Week Warrior', '7 day login streak', '🔥', 'achievement'),
('streak_30', 'Monthly Warrior', '30 day login streak', '💪', 'achievement'),
('referrer', 'Referrer', 'Invited your first friend', '👥', 'achievement'),
('super_referrer', 'Super Referrer', 'Invited 10 friends', '🎉', 'achievement'),
('early_bird', 'Early Bird', 'One of the first 100 users', '🐦', 'special'),
('premium', 'Premium Member', 'Premium subscriber', '💎', 'special');

-- Insert default achievements
INSERT IGNORE INTO achievements (achievement_key, achievement_name, achievement_description, achievement_type, target_value, points_reward, badge_id) VALUES
('first_chat', 'First Chat', 'Complete your first chat', 'chat_count', 1, 50, (SELECT id FROM badges WHERE badge_key = 'first_chat' LIMIT 1)),
('chat_10', 'Chatter', 'Complete 10 chats', 'chat_count', 10, 200, NULL),
('chat_50', 'Chat Master', 'Complete 50 chats', 'chat_count', 50, 1000, (SELECT id FROM badges WHERE badge_key = 'chat_master' LIMIT 1)),
('like_10', 'Liked', 'Receive 10 likes', 'like_count', 10, 100, NULL),
('like_100', 'Social Butterfly', 'Receive 100 likes', 'like_count', 100, 500, (SELECT id FROM badges WHERE badge_key = 'social_butterfly' LIMIT 1)),
('like_500', 'Popular', 'Receive 500 likes', 'like_count', 500, 2000, (SELECT id FROM badges WHERE badge_key = 'popular' LIMIT 1)),
('streak_7', 'Week Warrior', '7 day login streak', 'streak', 7, 300, (SELECT id FROM badges WHERE badge_key = 'streak_7' LIMIT 1)),
('streak_30', 'Monthly Warrior', '30 day login streak', 'streak', 30, 1500, (SELECT id FROM badges WHERE badge_key = 'streak_30' LIMIT 1)),
('referral_1', 'Referrer', 'Invite your first friend', 'referral_count', 1, 500, (SELECT id FROM badges WHERE badge_key = 'referrer' LIMIT 1)),
('referral_10', 'Super Referrer', 'Invite 10 friends', 'referral_count', 10, 5000, (SELECT id FROM badges WHERE badge_key = 'super_referrer' LIMIT 1));




