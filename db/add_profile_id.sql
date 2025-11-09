-- Add profile_id column and update existing users
-- Check if column exists first
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'profile_id';

SET @query = IF(@col_exists = 0, 
    'ALTER TABLE users ADD COLUMN profile_id VARCHAR(50) NULL AFTER like_count', 
    'SELECT "Column profile_id already exists" AS message');
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create unique index if not exists
SET @idx_exists = 0;
SELECT COUNT(*) INTO @idx_exists FROM information_schema.STATISTICS 
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND INDEX_NAME = 'idx_profile_id';

SET @query = IF(@idx_exists = 0, 
    'CREATE UNIQUE INDEX idx_profile_id ON users(profile_id)', 
    'SELECT "Index idx_profile_id already exists" AS message');
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Update existing users with profile_id
UPDATE users 
SET profile_id = SUBSTRING(MD5(CONCAT('user_', telegram_id)), 1, 12)
WHERE profile_id IS NULL;

