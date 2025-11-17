-- Migration: Add is_virtual field to users table
-- Date: 2025-01-XX
-- Description: Adds is_virtual field to mark virtual/bot profiles

-- Check if column exists before adding
SET @dbname = DATABASE();
SET @tablename = "users";
SET @columnname = "is_virtual";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (COLUMN_NAME = @columnname)
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " BOOLEAN DEFAULT FALSE NOT NULL AFTER is_active")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Set default value for existing users (all are real users)
UPDATE users SET is_virtual = FALSE WHERE is_virtual IS NULL;

