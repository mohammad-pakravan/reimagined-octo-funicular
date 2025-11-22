-- Migration: Add Playlist tables
-- Date: 2025-01-XX

-- Create user_playlists table
CREATE TABLE IF NOT EXISTS user_playlists (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL DEFAULT 'پلی‌لیست من',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create playlist_items table
CREATE TABLE IF NOT EXISTS playlist_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    playlist_id INT NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    file_id VARCHAR(512) NOT NULL,
    title VARCHAR(255) NULL,
    performer VARCHAR(255) NULL,
    duration INT NULL,
    forwarded_from_chat_id BIGINT NULL,
    forwarded_from_message_id INT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES user_playlists(id) ON DELETE CASCADE,
    INDEX idx_playlist_id (playlist_id),
    INDEX idx_message_type (message_type),
    INDEX idx_added_at (added_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

