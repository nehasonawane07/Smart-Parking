
from db import get_db_connection

try:
    connection = get_db_connection()

    if connection.is_connected():
        print("SUCCESS: Connected to MySQL!")
        print("Database: smart_parking")

    connection.close()

except Exception as error:
    print("Connection failed.")
    print("Error:", error)