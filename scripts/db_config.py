import os

from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env, configure it, "
            "or set DATABASE_URL in the environment."
        )
    return database_url
