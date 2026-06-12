import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_HOST = os.getenv("DB_HOST", "aws-1-ap-southeast-1.pooler.supabase.com")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres.yawhkfdlpxvpspbqjqwz")
DB_PASSWORD = os.getenv("DB_PASSWORD", "fSA+naVBX,-D2@p")
DB_PORT = int(os.getenv("DB_PORT", 5432))

conn = None
cursor = None

def connect_db():
    global conn, cursor

    try:
        # Already connected
        if conn is not None and conn.closed == 0:
            print("Database already connected")
            return True

        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            sslmode="require"
        )

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        print("Connected to Supabase PostgreSQL")

        return True

    except Exception as e:
        print("Database connection failed:")
        print(e)

        conn = None
        cursor = None

        return False

def is_connected():
    global conn

    try:
        if conn is not None and conn.closed == 0:
            return True

        return False

    except Exception:
        return False


def push_snapshot(
    male_in: int = 0,
    female_in: int = 0,
    male_out: int = 0,
    female_out: int = 0,
):
    global conn, cursor

    try:
        # Auto reconnect if disconnected
        if not is_connected():
            print("Database not connected. Reconnecting...")

            if not connect_db():
                return None

        recorded_at = datetime.now()

        cursor.execute(
            """
            INSERT INTO public.snapshot (
                recorded_at,
                male_in,
                female_in,
                male_out,
                female_out
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                recorded_at,
                male_in,
                female_in,
                male_out,
                female_out
            )
        )

        result = cursor.fetchone()

        conn.commit()

        print(f"Inserted snapshot ID: {result['id']}")

        return result["id"]

    except Exception as e:
        print("Insert failed:")
        print(e)

        if conn:
            conn.rollback()

        return None


connect_db()

print(is_connected())

push_snapshot(5, 3, 1, 2)
push_snapshot(10, 4, 2, 1)

if cursor:
    try:
        cursor.close()
    except Exception:
        pass

if conn:
    try:
        if conn.closed == 0:
            conn.close()
    except Exception:
        pass