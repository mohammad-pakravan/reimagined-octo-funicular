-- Initialize database schema
-- This file is automatically executed when MySQL container starts for the first time

-- Database will be created automatically by MySQL container environment variables
-- This file can contain additional initialization SQL if needed

ل-- Grant remote access to MySQL user (allows connections from any host)
-- The user is created by environment variables, but we ensure it has remote access
-- Note: Update username and password if you changed MYSQL_USER or MYSQL_PASSWORD in docker-compose.yml
GRANT ALL PRIVILEGES ON telecaht.* TO 'telecaht_user'@'%';
FLUSH PRIVILEGES;

-- Example: Create additional indexes or views if required
-- The tables will be created by SQLAlchemy models

