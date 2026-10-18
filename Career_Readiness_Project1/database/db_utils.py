from datetime import datetime
from mysql.connector import Error

from database.db_connection import create_connection


def get_user_by_email(email: str):
    query = "SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s"
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (email,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch user by email: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_user_by_id(user_id: int):
    query = "SELECT id, name, email, created_at FROM users WHERE id = %s"
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch user by ID: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def create_user(name: str, email: str, password_hash: str):
    query = "INSERT INTO users (name, email, password_hash, created_at) VALUES (%s, %s, %s, %s)"
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(query, (name, email, password_hash, datetime.now()))
        connection.commit()
        return cursor.lastrowid
    except Error as error:
        raise RuntimeError(f"Unable to create user: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_profile_by_user_id(user_id: int):
    query = "SELECT id, user_id, cgpa, communication, logical_reasoning, projects_count, certifications_count, internship_count, interest_domain, created_at FROM profiles WHERE user_id = %s"
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchone()
    except Error as error:
        raise RuntimeError(f"Unable to fetch profile by user ID: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def create_profile(
    user_id: int,
    cgpa: float,
    communication: int,
    logical_reasoning: int,
    projects_count: int,
    certifications_count: int,
    internship_count: int,
    interest_domain: str,
):
    query = (
        "INSERT INTO profiles (user_id, cgpa, communication, logical_reasoning, projects_count, certifications_count, internship_count, interest_domain, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                user_id,
                cgpa,
                communication,
                logical_reasoning,
                projects_count,
                certifications_count,
                internship_count,
                interest_domain,
                datetime.now(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except Error as error:
        raise RuntimeError(f"Unable to create profile: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def update_profile(
    user_id: int,
    cgpa: float,
    communication: int,
    logical_reasoning: int,
    projects_count: int,
    certifications_count: int,
    internship_count: int,
    interest_domain: str,
):
    query = (
        "UPDATE profiles SET cgpa = %s, communication = %s, logical_reasoning = %s, "
        "projects_count = %s, certifications_count = %s, internship_count = %s, interest_domain = %s "
        "WHERE user_id = %s"
    )
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                cgpa,
                communication,
                logical_reasoning,
                projects_count,
                certifications_count,
                internship_count,
                interest_domain,
                user_id,
            ),
        )
        connection.commit()
        return cursor.rowcount
    except Error as error:
        raise RuntimeError(f"Unable to update profile: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()
