import mysql.connector
from mysql.connector import Error


def create_connection(host_name: str = "localhost", user_name: str = "root", user_password: str = "", db_name: str = "career_readiness_db"):
    """Create and return a MySQL database connection.

    Args:
        host_name: Hostname of the MySQL server.
        user_name: Username for MySQL authentication.
        user_password: Password for MySQL authentication.
        db_name: Database name to connect to.

    Returns:
        A mysql.connector.connection.MySQLConnection instance.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host=host_name,
            user=user_name,
            password=user_password,
            database=db_name,
        )
        if connection.is_connected():
            return connection
    except Error as error:
        print(f"Error: Could not connect to MySQL. {error}")
        raise
    return connection
