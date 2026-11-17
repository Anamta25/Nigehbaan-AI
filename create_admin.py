from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import psycopg
import os
import getpass

load_dotenv()

admin_name = input("Enter Admin Name: ")
admin_email = input("Enter Admin Email: ")
admin_password = getpass.getpass("Enter Admin Password: ")

password_hash = generate_password_hash(admin_password)

conn = psycopg.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

cursor = conn.cursor()

cursor.execute(
    """
    INSERT INTO users (full_name, email, password_hash, role)
    VALUES (%s, %s, %s, %s)
    RETURNING user_id;
    """,
    (admin_name, admin_email, password_hash, "admin")
)

admin_id = cursor.fetchone()[0]

conn.commit()

cursor.close()
conn.close()

print("Admin account created successfully!")
print("Admin ID:", admin_id)
