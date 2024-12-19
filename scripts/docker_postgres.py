import logging
import subprocess
import time
from urllib.parse import quote_plus

import psycopg2

"""
Starts a Postgres database container, with pgvector configured, using Docker
"""


DB_NAME = "elroy"
DB_USER = "elroy"
DB_PASSWORD = "password"
DB_HOST = "localhost"
DB_PORT = "5432"
CONTAINER_NAME = "elroy_postgres"
VOLUME_NAME = "elroy_postgres-data"

DOCKER_DB_URL = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def is_docker_running():
    """Checks if docker daemon is running by trying to execute docker info"""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, check=True)
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def ping():
    """Checks if the dockerized postgres is up and running."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


def create_volume_if_not_exists():
    """Creates a Docker volume if it doesn't exist."""
    if subprocess.run(["docker", "volume", "inspect", VOLUME_NAME], capture_output=True, text=True).returncode != 0:
        subprocess.run(["docker", "volume", "create", VOLUME_NAME], check=True, capture_output=True)
        logging.info(f"Created volume: {VOLUME_NAME}")
    else:
        logging.info(f"Volume {VOLUME_NAME} already exists.")


def rm_orphan_container_if_exists():
    if (
        CONTAINER_NAME
        in subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={CONTAINER_NAME}", "--filter", "status=exited", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        ).stdout
    ):
        subprocess.run(["docker", "rm", CONTAINER_NAME], check=True, capture_output=True)
        logging.info(f"Removed existing stopped container: {CONTAINER_NAME}")


def start_db() -> str:
    """Starts a dockerized postgres, if it is not already running."""
    if ping():
        logging.info("Database is already running.")
    else:
        # Check if container exists but is not running
        rm_orphan_container_if_exists()
        create_volume_if_not_exists()
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINER_NAME,
                "-e",
                f"POSTGRES_USER={DB_USER}",
                "-e",
                f"POSTGRES_PASSWORD={DB_PASSWORD}",
                "-e",
                f"POSTGRES_DB={DB_NAME}",
                "-v",
                f"{VOLUME_NAME}:/var/lib/postgresql/data",
                "-p",
                f"{DB_PORT}:5432",
                "ankane/pgvector:v0.5.1",
                "postgres",
                "-c",
                "shared_preload_libraries=vector",
            ],
            check=True,
            capture_output=True,
        )

        # Wait for the database to be ready
        for _ in range(30):  # Try for 30 seconds
            if ping():
                break
            time.sleep(1)
        else:
            raise Exception("Database failed to start within 30 seconds")

    return f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def stop_db() -> None:
    """Stops the dockerized postgres, if it is running."""
    subprocess.run(["docker", "stop", CONTAINER_NAME], check=True, capture_output=True)
    subprocess.run(["docker", "rm", CONTAINER_NAME], check=True, capture_output=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage Elroy's PostgreSQL database container")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start", action="store_true", help="Start the database (default if no flag provided)")
    group.add_argument("--stop", action="store_true", help="Stop the database")
    args = parser.parse_args()

    if args.stop:
        stop_db()
        print("Database stopped")
    else:
        # Either --start was provided or no args
        if not is_docker_running():
            print("Error: Docker is not running")
            exit(1)
        db_url = start_db()
        print(f"Database started")
        print("To use with Elroy, either set:")
        print(f'ELROY_DATABASE_URL="{db_url}"')
        print(f"or run:")
        print(f'elroy --database-url "{db_url}"')
