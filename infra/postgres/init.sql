-- Initialize local Postgres with the two databases the dev stack needs.
-- This file is mounted into /docker-entrypoint-initdb.d/ and runs once on
-- first container start (empty data volume only).
CREATE DATABASE dagster;
CREATE DATABASE mlflow;
