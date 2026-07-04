#!/usr/bin/env bash
# Run the full local test matrix:
#   Python 3.12-3.14  x  Django 5.2/6.0  x  Postgres 16/17/18/19beta1
#
# nox handles the Python x Django axis. This script adds the Postgres axis by
# starting one container per Postgres version and running nox against each in
# parallel. Each nox invocation talks to its own Postgres server on its own
# port, so the parallel branches never collide on the test database.
#
# Usage:
#   ./scripts/test-matrix.sh                       # all four Postgres versions
#   PG_VERSIONS="16 18" ./scripts/test-matrix.sh   # a subset
#   BASE_PORT=5500 ./scripts/test-matrix.sh        # shift the host port range
#
# Live progress per branch:  tail -f .matrix-logs/pg-<version>.log
#
# Requires: docker, uv.
set -euo pipefail

PG_VERSIONS=${PG_VERSIONS:-"16 17 18 19beta1"}
BASE_PORT=${BASE_PORT:-5446}   # 5446.. avoids the dev compose port (5433)
LOG_DIR=${LOG_DIR:-".matrix-logs"}
NAME_PREFIX="dag-pg"

mkdir -p "$LOG_DIR"

cleanup() {
  for v in $PG_VERSIONS; do
    docker rm -f "${NAME_PREFIX}-${v}" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

# 1. Start a Postgres container per version.
declare -A PORTS
port=$BASE_PORT
for v in $PG_VERSIONS; do
  PORTS[$v]=$port
  echo ">>> starting postgres:$v on host port $port"
  docker run -d --rm --name "${NAME_PREFIX}-${v}" \
    -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres \
    -p "${port}:5432" "postgres:${v}" >/dev/null
  port=$((port + 1))
done

# 2. Wait for each server to accept connections.
for v in $PG_VERSIONS; do
  printf '>>> waiting for postgres:%s ' "$v"
  until docker exec "${NAME_PREFIX}-${v}" pg_isready -U postgres >/dev/null 2>&1; do
    printf '.'; sleep 1
  done
  echo ' ready'
done

# 3. Run nox against each Postgres in parallel.
#
# Each branch gets its OWN --envdir. nox names its virtualenvs by
# session (tests-<py>-django-<ver>) and does not include the Postgres
# version, so without separate envdirs the parallel processes would race
# to create/clear the same .nox/<session> paths and corrupt each other.
declare -A PIDS
for v in $PG_VERSIONS; do
  echo ">>> nox tests against postgres:$v (log: $LOG_DIR/pg-$v.log)"
  PG_PORT=${PORTS[$v]} uv run nox -s tests --envdir ".nox-pg-$v" \
    >"$LOG_DIR/pg-$v.log" 2>&1 &
  PIDS[$v]=$!
done

# 4. Collect results.
echo
echo "=== results ==="
status=0
for v in $PG_VERSIONS; do
  if wait "${PIDS[$v]}"; then
    echo "PASS  postgres:$v"
  else
    echo "FAIL  postgres:$v  (see $LOG_DIR/pg-$v.log)"
    status=1
  fi
done

exit $status
