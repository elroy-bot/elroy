import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def is_docker_compose_available() -> bool:
    """Check if docker-compose is available on the system."""
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_compose_file_path() -> Optional[Path]:
    """Find the docker-compose.yml file."""
    # Look in current directory first
    current_dir = Path.cwd() / "docker-compose.yml"
    if current_dir.exists():
        return current_dir

    # Look relative to this script
    script_dir = Path(__file__).parent.parent / "docker-compose.yml"
    if script_dir.exists():
        return script_dir

    return None


def run_elroy_docker_compose() -> int:
    """Run Elroy using docker-compose."""
    if not is_docker_compose_available():
        logging.error("docker-compose is not available. Please install docker-compose first.")
        return 1

    compose_file = get_compose_file_path()
    if not compose_file:
        logging.error("Could not find docker-compose.yml")
        return 1

    try:
        # Build the docker-compose command
        cmd: List[str] = ["docker-compose", "-f", str(compose_file), "run", "--rm", "elroy"]

        # Add any additional arguments passed to the script
        if len(sys.argv) > 1:
            cmd.extend(sys.argv[1:])

        logging.info(f"Running command: {' '.join(cmd)}")

        # Run the command
        result = subprocess.run(cmd)
        return result.returncode

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to run docker-compose: {e}")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return 1


def main():
    """Entry point for elroy-compose command."""
    logging.basicConfig(level=logging.INFO)
    sys.exit(run_elroy_docker_compose())


if __name__ == "__main__":
    main()
