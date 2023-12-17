#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE TABLE todo (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        done BOOLEAN NOT NULL DEFAULT FALSE,
        owner BIGINT NOT NULL,
        guild BIGINT NOT NULL
    );
EOSQL
