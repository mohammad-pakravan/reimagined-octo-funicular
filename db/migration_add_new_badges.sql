-- Migration: Add New Badges
-- Date: 2025-01-XX
-- This migration adds new badges and achievements for various user activities

-- Insert new badges
INSERT IGNORE INTO badges (badge_key, badge_name, badge_description, badge_icon, badge_type) VALUES
-- Chat Badges
('chat_100', 'Chat Veteran', 'Completed 100 successful chats', '🎖️', 'milestone'),
('chat_500', 'Chat Legend', 'Completed 500 successful chats', '👑', 'milestone'),
('message_1000', 'Message Master', 'Sent 1000 messages in chats', '💬', 'milestone'),
('message_10000', 'Message Legend', 'Sent 10000 messages in chats', '📨', 'milestone'),

-- Like Badges
('like_given_50', 'Liker', 'Given 50 likes', '👍', 'milestone'),
('like_given_200', 'Super Liker', 'Given 200 likes', '❤️', 'milestone'),
('like_received_1000', 'Superstar', 'Received 1000 likes', '⭐', 'milestone'),

-- Follow Badges
('follow_given_20', 'Follower', 'Followed 20 users', '👥', 'milestone'),
('follow_received_50', 'Influencer', 'Received 50 follows', '🌟', 'milestone'),
('follow_received_200', 'Celebrity', 'Received 200 follows', '🎭', 'milestone'),

-- DM Badges
('dm_sent_50', 'Messenger', 'Sent 50 direct messages', '📧', 'milestone'),
('dm_sent_200', 'Communicator', 'Sent 200 direct messages', '💌', 'milestone'),

-- Streak Badges
('streak_100', 'Centurion', '100 day login streak', '💯', 'achievement'),
('streak_365', 'Year Warrior', '365 day login streak', '🏆', 'achievement'),

-- Referral Badges
('referral_50', 'Ambassador', 'Invited 50 friends', '🎁', 'achievement'),
('referral_100', 'Champion', 'Invited 100 friends', '🏅', 'achievement'),

-- Premium Badges
('premium_1_year', 'Premium Veteran', '1 year of premium subscription', '💎', 'special'),
('premium_lifetime', 'Premium Master', 'Lifetime premium subscription', '👑', 'special'),

-- Special Badges
('early_adopter', 'Early Adopter', 'One of the first 1000 users', '🚀', 'special'),
('active_user', 'Active User', '30 consecutive days of activity', '⚡', 'special');

-- Insert new achievements
INSERT IGNORE INTO achievements (achievement_key, achievement_name, achievement_description, achievement_type, target_value, points_reward, badge_id) VALUES
-- Chat Achievements
('chat_100', 'Chat Veteran', 'Complete 100 successful chats', 'chat_count', 100, 2000, (SELECT id FROM badges WHERE badge_key = 'chat_100' LIMIT 1)),
('chat_500', 'Chat Legend', 'Complete 500 successful chats', 'chat_count', 500, 10000, (SELECT id FROM badges WHERE badge_key = 'chat_500' LIMIT 1)),
('message_1000', 'Message Master', 'Send 1000 messages in chats', 'message_count', 1000, 1500, (SELECT id FROM badges WHERE badge_key = 'message_1000' LIMIT 1)),
('message_10000', 'Message Legend', 'Send 10000 messages in chats', 'message_count', 10000, 15000, (SELECT id FROM badges WHERE badge_key = 'message_10000' LIMIT 1)),

-- Like Achievements
('like_given_50', 'Liker', 'Give 50 likes', 'like_given_count', 50, 500, (SELECT id FROM badges WHERE badge_key = 'like_given_50' LIMIT 1)),
('like_given_200', 'Super Liker', 'Give 200 likes', 'like_given_count', 200, 2000, (SELECT id FROM badges WHERE badge_key = 'like_given_200' LIMIT 1)),
('like_received_1000', 'Superstar', 'Receive 1000 likes', 'like_count', 1000, 5000, (SELECT id FROM badges WHERE badge_key = 'like_received_1000' LIMIT 1)),

-- Follow Achievements
('follow_given_20', 'Follower', 'Follow 20 users', 'follow_given_count', 20, 300, (SELECT id FROM badges WHERE badge_key = 'follow_given_20' LIMIT 1)),
('follow_received_50', 'Influencer', 'Receive 50 follows', 'follow_received_count', 50, 1000, (SELECT id FROM badges WHERE badge_key = 'follow_received_50' LIMIT 1)),
('follow_received_200', 'Celebrity', 'Receive 200 follows', 'follow_received_count', 200, 5000, (SELECT id FROM badges WHERE badge_key = 'follow_received_200' LIMIT 1)),

-- DM Achievements
('dm_sent_50', 'Messenger', 'Send 50 direct messages', 'dm_sent_count', 50, 400, (SELECT id FROM badges WHERE badge_key = 'dm_sent_50' LIMIT 1)),
('dm_sent_200', 'Communicator', 'Send 200 direct messages', 'dm_sent_count', 200, 1500, (SELECT id FROM badges WHERE badge_key = 'dm_sent_200' LIMIT 1)),

-- Streak Achievements
('streak_100', 'Centurion', '100 day login streak', 'streak', 100, 5000, (SELECT id FROM badges WHERE badge_key = 'streak_100' LIMIT 1)),
('streak_365', 'Year Warrior', '365 day login streak', 'streak', 365, 20000, (SELECT id FROM badges WHERE badge_key = 'streak_365' LIMIT 1)),

-- Referral Achievements
('referral_50', 'Ambassador', 'Invite 50 friends', 'referral_count', 50, 10000, (SELECT id FROM badges WHERE badge_key = 'referral_50' LIMIT 1)),
('referral_100', 'Champion', 'Invite 100 friends', 'referral_count', 100, 25000, (SELECT id FROM badges WHERE badge_key = 'referral_100' LIMIT 1));

