
from getpass import getpass
from werkzeug.security import generate_password_hash
from db import get_db_connection

email = "admin@smartparking.com"

password = getpass("Create a new admin password: ")
confirm_password = getpass("Confirm admin password: ")

if len(password) < 8:
    print("Password must be at least 8 characters.")
elif password != confirm_password:
    print("Passwords do not match.")
else:
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        password_hash = generate_password_hash(password)

        cursor.execute(
            """
            UPDATE STAFF
            SET password_hash = %s
            WHERE email = %s AND role = 'Admin'
            """,
            (password_hash, email)
        )

        connection.commit()

        if cursor.rowcount == 1:
            print("Admin password updated successfully!")
            print("Admin email:", email)
        else:
            print("Admin account not found. Check the STAFF table.")

    except Exception:
        if connection:
            connection.rollback()
        print("Could not update the password. Check the VS Code terminal.")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
