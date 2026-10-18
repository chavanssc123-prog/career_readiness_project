from datetime import datetime
from typing import Dict, Optional
from mysql.connector import Error

from database.db_connection import create_connection


def create_career_predictions_table_if_missing():
    query = (
        "CREATE TABLE IF NOT EXISTS career_predictions ("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "user_id INT NOT NULL, "
        "recommended_role VARCHAR(255) NOT NULL, "
        "confidence_score DECIMAL(5,2) NOT NULL, "
        "predicted_role VARCHAR(255) NOT NULL, "
        "selected_role VARCHAR(255) NOT NULL, "
        "prediction_confidence DECIMAL(5,2) NOT NULL, "
        "prediction_date DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT fk_prediction_user FOREIGN KEY (user_id) REFERENCES users(id) "
        "ON DELETE CASCADE ON UPDATE CASCADE"
        ")"
    )
    alter_queries = [
        "ALTER TABLE career_predictions ADD COLUMN IF NOT EXISTS predicted_role VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE career_predictions ADD COLUMN IF NOT EXISTS selected_role VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE career_predictions ADD COLUMN IF NOT EXISTS prediction_confidence DECIMAL(5,2) NOT NULL DEFAULT 0.0",
    ]
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        for alter_query in alter_queries:
            try:
                cursor.execute(alter_query)
            except Error:
                pass
        connection.commit()
    except Error as error:
        raise RuntimeError(f"Unable to create career_predictions table: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def save_career_prediction(
    user_id: int,
    predicted_role: str,
    prediction_confidence: float,
    selected_role: str = None,
):
    if selected_role is None:
        selected_role = predicted_role

    query = (
        "INSERT INTO career_predictions (user_id, recommended_role, confidence_score, predicted_role, selected_role, prediction_confidence, prediction_date) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                user_id,
                predicted_role,
                prediction_confidence,
                predicted_role,
                selected_role,
                prediction_confidence,
                datetime.now(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except Error as error:
        raise RuntimeError(f"Unable to save career prediction: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def update_latest_career_prediction(user_id: int, selected_role: str):
    latest = get_latest_career_prediction(user_id)
    if not latest or not latest.get("id"):
        return None

    query = (
        "UPDATE career_predictions SET selected_role = %s "
        "WHERE id = %s"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(query, (selected_role, latest["id"]))
        connection.commit()
        return cursor.rowcount
    except Error as error:
        raise RuntimeError(f"Unable to update latest career prediction: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_latest_career_prediction(user_id: int) -> Optional[Dict]:
    query = (
        "SELECT id, user_id, recommended_role, confidence_score, predicted_role, selected_role, prediction_confidence, prediction_date "
        "FROM career_predictions WHERE user_id = %s ORDER BY prediction_date DESC LIMIT 1"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch latest career prediction: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()
