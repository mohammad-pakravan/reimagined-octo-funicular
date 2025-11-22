-- Migration: Add coin packages table
-- Description: Creates coin_packages table for managing coin purchase packages
-- Date: 2025-11-21

-- Create coin_packages table
CREATE TABLE IF NOT EXISTS coin_packages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    package_name VARCHAR(200) NOT NULL,
    coin_amount INT NOT NULL,
    price FLOAT NOT NULL,
    original_price FLOAT DEFAULT NULL,
    discount_percent INT DEFAULT 0 NOT NULL,
    stars_required INT DEFAULT NULL,
    payment_methods_json TEXT DEFAULT NULL,
    discount_start_date DATETIME DEFAULT NULL,
    discount_end_date DATETIME DEFAULT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_visible BOOLEAN DEFAULT TRUE NOT NULL,
    display_order INT DEFAULT 0 NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
    INDEX idx_coin_amount (coin_amount),
    INDEX idx_coin_is_active (is_active),
    INDEX idx_coin_display_order (display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add coin_package_id to payment_transactions table
ALTER TABLE payment_transactions 
ADD COLUMN coin_package_id INT DEFAULT NULL AFTER plan_id,
ADD FOREIGN KEY (coin_package_id) REFERENCES coin_packages(id);

-- Insert sample coin packages (optional - admin can create these via admin panel)
INSERT INTO coin_packages (package_name, coin_amount, price, stars_required, payment_methods_json, is_active, is_visible, display_order, created_at, updated_at)
VALUES 
    ('100 سکه', 100, 10000, 50, '["shaparak", "stars"]', TRUE, TRUE, 1, NOW(), NOW()),
    ('500 سکه', 500, 45000, 225, '["shaparak", "stars"]', TRUE, TRUE, 2, NOW(), NOW()),
    ('1000 سکه', 1000, 80000, 400, '["shaparak", "stars"]', TRUE, TRUE, 3, NOW(), NOW()),
    ('2500 سکه', 2500, 180000, 900, '["shaparak", "stars"]', TRUE, TRUE, 4, NOW(), NOW());

-- Note: Admins can manage coin packages through the admin panel at:
-- /admin -> 🪙 مدیریت پکیج‌های سکه

