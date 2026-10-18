-- Schema definition for Phase 2 of AI Career Readiness & Skill Gap Analyzer.

CREATE DATABASE IF NOT EXISTS career_readiness_db;
USE career_readiness_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    cgpa DECIMAL(4,2) DEFAULT 0.00,
    communication TINYINT DEFAULT 0,
    logical_reasoning TINYINT DEFAULT 0,
    projects_count INT DEFAULT 0,
    certifications_count INT DEFAULT 0,
    internship_count INT DEFAULT 0,
    interest_domain VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_profiles_user FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
