# syntax = docker/dockerfile:1.6

# Version tags can be found here: https://hub.docker.com/r/ankane/pgvector/tags
ARG PGVECTOR=v0.5.1
# Set up a minimal postgres image
FROM ankane/pgvector:${PGVECTOR}
RUN sed -e 's/^    //' >/docker-entrypoint-initdb.d/01-initelroy.sql <<'EOF'
    -- Title: Init Elroy Database

    -- Set db user, password, and name to the values in the environment variables.
    \set db_user `echo "${DB_USER}"`
    \set db_password `echo "${DB_PASSWORD}"`
    \set db_name `echo "${DB_NAME}"`

    CREATE USER :"db_user"
        WITH PASSWORD :'db_password'
        NOCREATEDB
        NOCREATEROLE
        ;

    CREATE DATABASE :"db_name"
        WITH
        OWNER = :"db_user"
        ENCODING = 'UTF8'
        LC_COLLATE = 'en_US.utf8'
        LC_CTYPE = 'en_US.utf8'
        LOCALE_PROVIDER = 'libc'
        TABLESPACE = pg_default
        CONNECTION LIMIT = -1;

    -- Set up our schema and extensions in our new database.
    \c :"db_name"

    CREATE SCHEMA :"db_name"
        AUTHORIZATION :"db_user";

    ALTER DATABASE :"db_name"
        SET search_path TO :"db_name";

    CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA :"db_name";

    DROP SCHEMA IF EXISTS public CASCADE;
EOF
