-- Migration script to add chat_end_notifications table

SET @table_exists = (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'chat_end_notifications');

SET @query = IF(@table_exists = 0,
    'CREATE TABLE chat_end_notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        watcher_id INT NOT NULL,
        target_user_id INT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (watcher_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE,
        INDEX idx_watcher_id (watcher_id),
        INDEX idx_target_user_id (target_user_id),
        INDEX idx_created_at (created_at),
        UNIQUE KEY idx_watcher_target_unique (watcher_id, target_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;',
    'SELECT "Table chat_end_notifications already exists" AS message;');

PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

