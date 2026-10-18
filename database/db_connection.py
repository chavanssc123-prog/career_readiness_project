import os
import mysql.connector
from mysql.connector import Error, errorcode


def _load_schema_file(schema_file: str, cursor):
    with open(schema_file, "r", encoding="utf-8") as file:
        sql_commands = file.read()

    for statement in sql_commands.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def create_connection(
    host_name: str = None,
    user_name: str = None,
    user_password: str = None,
    db_name: str = None,
):
    """Create and return a MySQL database connection.

    Args:
        host_name: Hostname of the MySQL server.
        user_name: Username for MySQL authentication.
        user_password: Password for MySQL authentication.
        db_name: Database name to connect to.

    Returns:
        A mysql.connector.connection.MySQLConnection instance.
    """
    host_name = host_name or os.environ.get("DB_HOST", "localhost")
    user_name = user_name or os.environ.get("DB_USER", "root")
    user_password = user_password or os.environ.get("DB_PASSWORD", "")
    db_name = db_name or os.environ.get("DB_NAME", "career_readiness_db")

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
        if error.errno == errorcode.ER_BAD_DB_ERROR:
            try:
                connection = mysql.connector.connect(
                    host=host_name,
                    user=user_name,
                    password=user_password,
                )
                cursor = connection.cursor()
                schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
                _load_schema_file(schema_path, cursor)
                connection.commit()
                cursor.close()
                connection.close()
                connection = mysql.connector.connect(
                    host=host_name,
                    user=user_name,
                    password=user_password,
                    database=db_name,
                )
                if connection.is_connected():
                    return connection
            except Error as create_error:
                print(f"Error: Could not initialize database '{db_name}'. {create_error}")
                raise
        print(f"Error: Could not connect to MySQL. {error}")
        raise

    return None
