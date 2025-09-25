-- Initialize database for A Fine Wine Dynasty
-- This script sets up basic database structure and TimescaleDB extension

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create database schema for development
\c afinewinedynasty;

-- Add any initial database setup here
-- (Tables will be created via Alembic migrations)

-- Create a basic health check table
CREATE TABLE IF NOT EXISTS system_health (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'healthy',
    last_check TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial health record
INSERT INTO system_health (service_name, status)
VALUES ('database', 'healthy')
ON CONFLICT DO NOTHING;