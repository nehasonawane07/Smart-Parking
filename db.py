
import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Neh@7483",
        database="smart_parking"
    )
    return connection