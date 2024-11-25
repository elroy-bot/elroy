import os
import sys
import subprocess
from elroy.docker_postgres import start_db, stop_db

def main():
    # Start postgres and get the URL
    db_url = start_db()
    
    try:
        # Create environment with the postgres URL
        env = os.environ.copy()
        env['ELROY_POSTGRES_URL'] = db_url

        # Get the elroy command and args that were passed to this script
        elroy_args = sys.argv[1:] if len(sys.argv) > 1 else ['chat']
        
        # Run elroy with the environment variable set
        result = subprocess.run(
            ['elroy'] + elroy_args,
            env=env,
            check=True
        )
        
        sys.exit(result.returncode)
    finally:
        # Clean up postgres
        stop_db()

if __name__ == '__main__':
    main()
