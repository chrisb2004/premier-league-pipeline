"""Database connection helper shared by every stage that talks to MySQL."""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

# Always the .env in the project root, no matter where the command is run from
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def check_env_file() -> None:
    """Fail early with a clear message instead of a long MySQL 'Access denied' error."""
    if not ENV_FILE.exists():
        raise RuntimeError(f"No .env file at {ENV_FILE}. Copy .env.example to .env and fill it in.")

    file_values = dotenv_values(ENV_FILE)
    if file_values.get("DB_USER") == "your_user" or file_values.get("DB_PASSWORD") == "your_password":
        raise RuntimeError(f"{ENV_FILE} still has the placeholder values from .env.example. "
                           "Fill in your MySQL user and password, and save the file.")

    # Variables already set in the environment win over .env (that's how servers
    # pass secrets), so a leftover Windows/shell variable can silently override the file.
    for key in ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"):
        if key in os.environ and key in file_values and os.environ[key] != file_values[key]:
            raise RuntimeError(f"Environment variable {key} is set and overrides the value in .env. "
                               f"Remove it (Windows: System Properties -> Environment Variables), "
                               f"then open a new terminal.")


def get_engine() -> Engine:
    """Build a SQLAlchemy engine from the settings in .env."""
    check_env_file()
    load_dotenv(ENV_FILE)  # reads .env into environment variables (doesn't overwrite existing ones)

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
