-- Migration: Create virtual_profiles table
-- Date: 2025-11-17
-- Description: Creates a separate table for virtual/fake profiles used in matchmaking

-- Create virtual_profiles table
CREATE TABLE IF NOT EXISTS virtual_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE COMMENT 'شناسه کاربر مرتبط در جدول users',
    display_name VARCHAR(255) NOT NULL COMMENT 'نام نمایشی',
    age INT NOT NULL COMMENT 'سن',
    province VARCHAR(255) NOT NULL COMMENT 'استان',
    city VARCHAR(255) NOT NULL COMMENT 'شهر',
    profile_image_url VARCHAR(512) NULL COMMENT 'عکس پروفایل',
    like_count INT DEFAULT 0 NOT NULL COMMENT 'تعداد لایک‌ها',
    profile_id VARCHAR(50) NOT NULL UNIQUE COMMENT 'شناسه عمومی پروفایل',
    
    -- Tracking
    is_active BOOLEAN DEFAULT TRUE NOT NULL COMMENT 'فعال/غیرفعال',
    usage_count INT DEFAULT 0 NOT NULL COMMENT 'تعداد دفعات استفاده',
    last_used_at DATETIME NULL COMMENT 'آخرین بار استفاده',
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT 'تاریخ ایجاد',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL COMMENT 'تاریخ به‌روزرسانی',
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_profile_id (profile_id),
    INDEX idx_is_active (is_active),
    INDEX idx_created_at (created_at),
    INDEX idx_last_used_at (last_used_at),
    INDEX idx_city_province (city, province),
    
    -- Foreign Key
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='پروفایل‌های مجازی برای matchmaking';

-- Keep is_virtual field in users table (needed for backward compatibility)
-- We use both: is_virtual in users table AND separate virtual_profiles table
-- This allows us to easily identify virtual users without joining tables

