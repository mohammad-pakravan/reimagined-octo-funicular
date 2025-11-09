-- Migration: Add Premium Plans System
-- Date: 2025-11-09
-- This migration adds the premium_plans table for managing premium subscription plans

CREATE TABLE IF NOT EXISTS premium_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_name VARCHAR(200) NOT NULL,
    duration_days INT NOT NULL,
    price FLOAT NOT NULL,
    original_price FLOAT NULL,
    discount_percent INT DEFAULT 0 NOT NULL,
    discount_start_date DATETIME NULL,
    discount_end_date DATETIME NULL,
    features_json TEXT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_visible BOOLEAN DEFAULT TRUE NOT NULL,
    display_order INT DEFAULT 0 NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_duration_days (duration_days),
    INDEX idx_is_active (is_active),
    INDEX idx_display_order (display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

