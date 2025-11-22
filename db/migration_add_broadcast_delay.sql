-- Add delay_seconds column to broadcast_messages table
ALTER TABLE broadcast_messages 
ADD COLUMN delay_seconds FLOAT DEFAULT 0.067 NOT NULL COMMENT 'Delay between messages in seconds (default ~15 msg/sec)';

