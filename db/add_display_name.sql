-- Migration: Add display_name column to users table
-- Date: 2024
-- Description: Adds display_name column for user display names

-- Check if column exists first
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'display_name';

SET @query = IF(@col_exists = 0, 
    'ALTER TABLE users ADD COLUMN display_name VARCHAR(255) NULL COMMENT ''نام نمایشی کاربر'' AFTER username', 
    'SELECT "Column display_name already exists" AS message');
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

