from typing import Optional, Dict
from mysql.connector import Error

from database.db_connection import create_connection


def get_resume_data_by_user(user_id: int) -> Optional[Dict]:
    query = "SELECT id, user_id, resume_file, skills, projects, certifications, education, upload_date FROM resume_data WHERE user_id = %s"
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch resume data: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def create_resume_data(user_id: int, resume_file: str, skills: str, projects: str, certifications: str, education: str):
    query = (
        "INSERT INTO resume_data (user_id, resume_file, skills, projects, certifications, education, upload_date) "
        "VALUES (%s, %s, %s, %s, %s, %s, NOW())"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(query, (user_id, resume_file, skills, projects, certifications, education))
        connection.commit()
        return cursor.lastrowid
    except Error as error:
        raise RuntimeError(f"Unable to create resume data: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def update_resume_data(user_id: int, resume_file: str, skills: str, projects: str, certifications: str, education: str):
    query = (
        "UPDATE resume_data SET resume_file = %s, skills = %s, projects = %s, certifications = %s, education = %s, upload_date = NOW() "
        "WHERE user_id = %s"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(query, (resume_file, skills, projects, certifications, education, user_id))
        connection.commit()
        return cursor.rowcount
    except Error as error:
        raise RuntimeError(f"Unable to update resume data: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()
