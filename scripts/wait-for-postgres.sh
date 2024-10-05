#!/bin/bash

set -e

host="elroy_postgres"
cmd="$@"

max_retries=60
counter=0

until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$host" -U "$POSTGRES_USER" -d "elroy" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 5
  counter=$((counter+1))
  if [ $counter -ge $max_retries ]; then
    >&2 echo "Max retries reached. Postgres is still unavailable."
    exit 1
  fi
done

>&2 echo "Postgres is up - executing command"
exec $cmd
