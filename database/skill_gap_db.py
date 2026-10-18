from datetime import datetime
from typing import Dict, List, Optional
from mysql.connector import Error

from database.db_connection import create_connection


def create_skill_gap_table_if_missing():
    create_query = (
        "CREATE TABLE IF NOT EXISTS skill_gap ("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "user_id INT NOT NULL, "
        "career_role VARCHAR(255) NOT NULL, "
        "matched_skills TEXT, "
        "missing_skills TEXT, "
        "extra_skills TEXT, "
        "skill_match_score DECIMAL(5,2) NOT NULL, "
        "readiness_score DECIMAL(5,2) NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT fk_skill_gap_user FOREIGN KEY (user_id) REFERENCES users(id) "
        "ON DELETE CASCADE ON UPDATE CASCADE"
        ")"
    )
    alter_queries = [
        "ALTER TABLE skill_gap ADD COLUMN IF NOT EXISTS matched_skills TEXT",
        "ALTER TABLE skill_gap ADD COLUMN IF NOT EXISTS missing_skills TEXT",
        "ALTER TABLE skill_gap ADD COLUMN IF NOT EXISTS extra_skills TEXT",
        "ALTER TABLE skill_gap ADD COLUMN IF NOT EXISTS skill_match_score DECIMAL(5,2) NOT NULL DEFAULT 0.0",
        "ALTER TABLE skill_gap ADD COLUMN IF NOT EXISTS readiness_score DECIMAL(5,2) NOT NULL DEFAULT 0.0",
        "ALTER TABLE skill_gap ADD COLUMN IF NOT EXISTS created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
    ]

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(create_query)
        for query in alter_queries:
            try:
                cursor.execute(query)
            except Error:
                # Some MySQL versions do not support ADD COLUMN IF NOT EXISTS.
                # Continue if the column already exists or if syntax is unsupported.
                pass
        connection.commit()
    except Error as error:
        raise RuntimeError(f"Unable to create or migrate skill_gap table: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def save_skill_gap_analysis(
    user_id: int,
    career_role: str,
    matched_skills: List[str],
    missing_skills: List[str],
    extra_skills: List[str],
    skill_match_score: float,
    readiness_score: float,
):
    query = (
        "INSERT INTO skill_gap (user_id, career_role, matched_skills, missing_skills, extra_skills, skill_match_score, readiness_score, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                user_id,
                career_role,
                ", ".join(matched_skills),
                ", ".join(missing_skills),
                ", ".join(extra_skills),
                skill_match_score,
                readiness_score,
                datetime.now(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except Error as error:
        raise RuntimeError(f"Unable to save skill gap analysis: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_latest_skill_gap_analysis(user_id: int) -> Optional[Dict]:
    query = (
        "SELECT id, user_id, career_role, matched_skills, missing_skills, extra_skills, skill_match_score, readiness_score, created_at "
        "FROM skill_gap WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch latest skill gap analysis: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()
