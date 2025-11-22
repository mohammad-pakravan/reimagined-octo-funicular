-- Migration: Add Payment System (PaymentTransaction and SystemSetting tables)
-- Date: 2025-11-09
-- This migration adds tables for payment gateway transactions and system settings

-- Create payment_transactions table
CREATE TABLE IF NOT EXISTS payment_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    plan_id INT NULL,
    transaction_id VARCHAR(255) NOT NULL UNIQUE,
    amount FLOAT NOT NULL,
    currency VARCHAR(10) DEFAULT 'IRT' NOT NULL,
    gateway VARCHAR(50) DEFAULT 'zarinpal' NOT NULL,
    authority VARCHAR(255) NULL,
    ref_id VARCHAR(255) NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    payment_status VARCHAR(50) NULL,
    callback_url TEXT NULL,
    return_url TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    paid_at DATETIME NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES premium_plans(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_plan_id (plan_id),
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_authority (authority),
    INDEX idx_ref_id (ref_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create system_settings table
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT NULL,
    setting_type VARCHAR(50) DEFAULT 'string' NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_setting_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default payment gateway domain setting (only if not exists)
INSERT IGNORE INTO system_settings (setting_key, setting_value, setting_type, description, created_at, updated_at)
VALUES ('payment_gateway_domain', 'https://payment.example.com', 'string', 'Payment gateway Flask server domain URL', NOW(), NOW());

-- Insert Zarinpal merchant ID setting (only if not exists - admin should set this via admin panel)
INSERT IGNORE INTO system_settings (setting_key, setting_value, setting_type, description, created_at, updated_at)
VALUES ('zarinpal_merchant_id', '', 'string', 'Zarinpal merchant ID for payment gateway', NOW(), NOW());

-- Insert Zarinpal sandbox mode setting (only if not exists)
INSERT IGNORE INTO system_settings (setting_key, setting_value, setting_type, description, created_at, updated_at)
VALUES ('zarinpal_sandbox', 'true', 'bool', 'Enable Zarinpal sandbox mode for testing', NOW(), NOW());

