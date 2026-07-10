import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from fastapi import HTTPException, status
from config import DATABASE_URL

# Initialize ThreadedConnectionPool for fast connection reuse and to prevent leaks
db_pool = None

def init_db_pool():
    global db_pool
    if not DATABASE_URL:
        return
    try:
        db_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=15,
            dsn=DATABASE_URL
        )
        print("Database connection pool initialized successfully.")
    except Exception as e:
        print("Failed to initialize database connection pool:", e)

# Run pool initialization immediately
init_db_pool()

@contextmanager
def get_db_connection():
    global db_pool
    if not db_pool:
        # Fallback to direct connection if pool is not initialized
        if not DATABASE_URL:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="DATABASE_URL environment variable is not configured. Please set it in Backend/.env"
            )
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET search_path TO documind, public;")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    else:
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET search_path TO documind, public;")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            db_pool.putconn(conn)

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set. Skipping schema initialization...")
        return
    try:
        print("Initializing PostgreSQL database...")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            print(f"schema.sql not found at {schema_path}")
            return
            
        with open(schema_path, "r") as f:
            schema_sql = f.read()
            
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(schema_sql)
                # Schema migrations for existing tables
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;")
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(6);")
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMP;")
                # Update existing users to be verified so we don't break them
                cursor.execute("UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL;")
            conn.commit()
        print("Database schema and migrations initialized successfully.")
    except Exception as e:
        print("WARNING: Database schema initialization failed. Is the database URL/credentials correct?")
        print("Error details:", e)
