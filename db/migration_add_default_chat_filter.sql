-- Migration: Add default_chat_filter_same_age field to users table
-- Date: 2025-01-XX
-- Description: Adds default_chat_filter_same_age field to store user's default preference for same-age filter

-- Check if column exists before adding
SET @dbname = DATABASE();
SET @tablename = "users";
SET @columnname = "default_chat_filter_same_age";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (COLUMN_NAME = @columnname)
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " BOOLEAN DEFAULT TRUE NOT NULL AFTER is_active")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Set default value for existing users (enable by default)
UPDATE users SET default_chat_filter_same_age = TRUE WHERE default_chat_filter_same_age IS NULL;

