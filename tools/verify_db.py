import os
import psycopg2
from dotenv import load_dotenv

# Load env variables
load_dotenv()
db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("Error: DATABASE_URL not found in .env file!")
    exit(1)

try:
    print("Attempting to connect to Neon PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print("Database connection SUCCESS!")
    print(f"Postgres Version: {db_version[0]}")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Database connection FAILED: {e}")
    exit(1)
