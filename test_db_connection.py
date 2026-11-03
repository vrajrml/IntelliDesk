from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
import os

# Load environment variables from the project root.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL is missing from the .env file.")

# Display the connection target without revealing credentials.
url = make_url(database_url)
print(f"Database target: {url.host}:{url.port or 3306}/{url.database}")
print(f"MySQL username: {url.username}")

engine = create_engine(
    database_url,
    pool_pre_ping=True,
)

try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT DATABASE(), VERSION()")
        )
        database_name, mysql_version = result.fetchone()

        print("\nDatabase connection successful!")
        print(f"Database: {database_name}")
        print(f"MySQL version: {mysql_version}")

except Exception as error:
    print("\nDatabase connection failed.")
    print(f"Error type: {type(error).__name__}")
    print(f"Error details: {error}")

finally:
    engine.dispose()