"""
Utility function to connect to PostgreSQL server.
"""
import psycopg2

HOST = "localhost"
USER = "postgres"
PASSWORD = "xxxxxxxxxxx"
def connect_to_database_server(dbname):
    """
    Connects to PostgreSQL server database 'dbname' and 
    returns a connection object and cursor.
    """
    try:
        conn = psycopg2.connect(host=HOST, database=dbname, user=USER, password=PASSWORD)
        cur = conn.cursor() 
        return [conn, cur]
    except psycopg2.OperationalError:
        return -1
