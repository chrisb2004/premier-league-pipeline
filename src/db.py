"""Database connection helper shared by every stage that talks to MySQL."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine


def get_engine() -> Engine:
    """Build a SQLAlchemy engine from the settings in .env."""
    load_dotenv()  # reads .env into environment variables (does nothing if already set)

    # URL.create escapes special characters in the password (e.g. '@', '/'),
    # which would break a hand-built "mysql+pymysql://user:pass@host" string.
    url = URL.create(
        drivername="mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        database=os.environ["DB_NAME"],
    )
    return create_engine(url)
