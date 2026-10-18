from datetime import datetime
from typing import Dict, Optional
from mysql.connector import Error

from database.db_connection import create_connection



def create_roadmap_table_if_missing():
    create_query = (
        "CREATE TABLE IF NOT EXISTS roadmaps ("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "user_id INT NOT NULL, "
        "career_role VARCHAR(255) NOT NULL, "
        "roadmap_text TEXT NOT NULL, "
        "duration_months INT NOT NULL, "
        "readiness_score DECIMAL(5,2) NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT fk_roadmap_user FOREIGN KEY (user_id) REFERENCES users(id) "
        "ON DELETE CASCADE ON UPDATE CASCADE"
        ")"
    )
    alter_queries = [
        "ALTER TABLE roadmaps ADD COLUMN IF NOT EXISTS roadmap_text TEXT NOT NULL",
        "ALTER TABLE roadmaps ADD COLUMN IF NOT EXISTS duration_months INT NOT NULL DEFAULT 0",
        "ALTER TABLE roadmaps ADD COLUMN IF NOT EXISTS readiness_score DECIMAL(5,2) NOT NULL DEFAULT 0.0",
        "ALTER TABLE roadmaps ADD COLUMN IF NOT EXISTS created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
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
                pass
        connection.commit()
    except Error as error:
        raise RuntimeError(f"Unable to create or migrate roadmap table: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def save_roadmap(
    user_id: int,
    career_role: str,
    roadmap_text: str,
    duration_months: int,
    readiness_score: float,
):
    query = (
        "INSERT INTO roadmaps (user_id, career_role, roadmap_text, duration_months, readiness_score, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
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
                roadmap_text,
                duration_months,
                readiness_score,
                datetime.now(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except Error as error:
        raise RuntimeError(f"Unable to save roadmap: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_latest_roadmap(user_id: int) -> Optional[Dict]:
    query = (
        "SELECT id, user_id, career_role, roadmap_text, duration_months, readiness_score, created_at "
        "FROM roadmaps WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch latest roadmap: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()
