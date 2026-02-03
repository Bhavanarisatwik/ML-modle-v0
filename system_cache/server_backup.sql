-- Production Database Backup
-- Created: 2026-02-03
-- Size: 2.4 GB (compressed)

-- Database: production_db
CREATE DATABASE IF NOT EXISTS production_db;
USE production_db;

-- Table: users
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users VALUES
(1, 'admin', 'admin@company.com', '$2y$10$abcd1234efgh5678ijkl9012mnopqrstu', '2024-01-01'),
(2, 'superuser', 'su@company.com', '$2y$10$wxyz9876abcd4321efgh1234ijklmnop', '2024-01-05'),
(3, 'testuser', 'test@company.com', '$2y$10$1234abcd5678efgh9012ijkl3456mnop', '2024-01-10');

-- Table: sensitive_data
CREATE TABLE sensitive_data (
  id INT PRIMARY KEY AUTO_INCREMENT,
  data_type VARCHAR(100),
  encrypted_content LONGBLOB,
  access_level VARCHAR(20),
  created_at TIMESTAMP
);

INSERT INTO sensitive_data VALUES
(1, 'financial_records', UNHEX('E8F9A2B3C4D5E6F7A8B9C0D1E2F3A4B5'), 'secret', '2026-01-20'),
(2, 'client_list', UNHEX('1A2B3C4D5E6F7A8B9C0D1E2F3A4B5C6D'), 'confidential', '2026-01-25');

-- Server Configuration
-- Host: prod-db.company.internal
-- Port: 3306
-- Backup Status: COMPLETED
-- Backup Size: 2.4 GB
-- Compression: gzip
