import psycopg

try:
    connection = psycopg.connect(
        dbname="nigehbaan_db",
        user="nigehbaan_user",
        password="Nigehbaan@2026",
        host="localhost",
        port="5432"
    )

    print("Nigehbaan AI Database Connected Successfully!")

    cursor = connection.cursor()
    cursor.execute("SELECT current_database();")

    print("Connected Database:", cursor.fetchone()[0])

    cursor.close()
    connection.close()

except Exception as error:
    print("Connection Failed:", error)

