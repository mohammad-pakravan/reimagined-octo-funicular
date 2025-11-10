-- Migration: Add mandatory channels table
-- This allows admins to set multiple mandatory channels that users must join

CREATE TABLE IF NOT EXISTS `mandatory_channels` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `channel_id` VARCHAR(255) NOT NULL UNIQUE,
    `channel_name` VARCHAR(255) DEFAULT NULL,
    `channel_link` VARCHAR(512) DEFAULT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `order_index` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_by_admin_id` INT DEFAULT NULL,
    INDEX `idx_channel_id` (`channel_id`),
    INDEX `idx_is_active` (`is_active`),
    INDEX `idx_order_index` (`order_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- If there's an existing MANDATORY_CHANNEL_ID in settings, migrate it to the new table
-- Note: This should be done manually or via a script that reads from environment/config

