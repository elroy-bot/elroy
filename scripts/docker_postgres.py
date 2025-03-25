#!/usr/bin/env python3
import logging
import subprocess
import time
from urllib.parse import quote_plus

import psycopg2

"""
Starts a Postgres database container, with pgvector configured, using Docker
"""

# Default values
DEFAULT_DB_NAME = "elroy"
DEFAULT_DB_PASSWORD = "password"
DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = "5432"


class PostgresConfig:
    def __init__(self, db_name: str = DEFAULT_DB_NAME, port: str = DEFAULT_DB_PORT, password: str = DEFAULT_DB_PASSWORD):
        self.db_name = db_name
        self.db_user = db_name  # Keep user same as db_name
        self.db_password = password
        self.db_host = DEFAULT_DB_HOST
        self.db_port = port
        self.container_name = f"{db_name}_postgres"
        self.volume_name = f"{db_name}_postgres-data"


def is_docker_running():
    """Checks if docker daemon is running by trying to execute docker info"""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, check=True)
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def ping(config: PostgresConfig):
    """Checks if the dockerized postgres is up and running."""
    try:
        conn = psycopg2.connect(
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password,
            host=config.db_host,
            port=config.db_port,
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


def create_volume_if_not_exists(config: PostgresConfig):
    """Creates a Docker volume if it doesn't exist."""
    if subprocess.run(["docker", "volume", "inspect", config.volume_name], capture_output=True, text=True).returncode != 0:
        subprocess.run(["docker", "volume", "create", config.volume_name], check=True, capture_output=True)
        logging.info(f"Created volume: {config.volume_name}")
    else:
        logging.info(f"Volume {config.volume_name} already exists.")


def rm_orphan_container_if_exists(config: PostgresConfig):
    if (
        config.container_name
        in subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={config.container_name}", "--filter", "status=exited", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        ).stdout
    ):
        subprocess.run(["docker", "rm", config.container_name], check=True, capture_output=True)
        logging.info(f"Removed existing stopped container: {config.container_name}")


def start_db(config: PostgresConfig) -> str:
    """Starts a dockerized postgres, if it is not already running."""
    if ping(config):
        logging.info("Database is already running.")
    else:
        rm_orphan_container_if_exists(config)
        create_volume_if_not_exists(config)
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                config.container_name,
                "-e",
                f"POSTGRES_USER={config.db_user}",
                "-e",
                f"POSTGRES_PASSWORD={config.db_password}",
                "-e",
                f"POSTGRES_DB={config.db_name}",
                "-v",
                f"{config.volume_name}:/var/lib/postgresql/data",
                "-p",
                f"{config.db_port}:5432",
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
            if ping(config):
                break
            time.sleep(1)
        else:
            raise Exception("Database failed to start within 30 seconds")

    return f"postgresql://{config.db_user}:{quote_plus(config.db_password)}@{config.db_host}:{config.db_port}/{config.db_name}"


def stop_db(config: PostgresConfig) -> None:
    """Stops the dockerized postgres, if it is running."""
    subprocess.run(["docker", "stop", config.container_name], check=True, capture_output=True)
    subprocess.run(["docker", "rm", config.container_name], check=True, capture_output=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage Elroy's PostgreSQL database container")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start", action="store_true", help="Start the database (default if no flag provided)")
    group.add_argument("--stop", action="store_true", help="Stop the database")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME, help="Database name (default: elroy)")
    parser.add_argument("--port", default=DEFAULT_DB_PORT, help="Port to expose (default: 5432)")
    parser.add_argument("--password", default=DEFAULT_DB_PASSWORD, help="Database password (default: password)")
    args = parser.parse_args()

    config = PostgresConfig(db_name=args.db_name, port=args.port, password=args.password)

    if args.stop:
        stop_db(config)
        print("Database stopped")
    else:
        # Either --start was provided or no args
        if not is_docker_running():
            print("Error: Docker is not running")
            exit(1)
        db_url = start_db(config)
        print(f"Database started")
        print("To use with Elroy, either set:")
        print(f'ELROY_DATABASE_URL="{db_url}"')
        print(f"or run:")
        print(f'elroy --database-url "{db_url}"')
