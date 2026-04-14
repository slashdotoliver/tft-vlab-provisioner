#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
SQL_DIR="$DIR/users_sql/"
declare -A users

ADMIN_PASSWD="$(cat /run/secrets/postgres-passwd)"
users["worker_db_user"]="/run/secrets/db-worker-passwd|worker_db_user.sql"
users["manager_db_user"]="/run/secrets/db-manager-passwd|manager_db_user.sql"

export PGPASSWORD="$ADMIN_PASSWD"
DB_USER="${POSTGRES_USER:-admin_db}"
DB_NAME="${POSTGRES_DB:-lab_db}"

for user in "${!users[@]}"; do
    IFS='|' read -r user_passwd_file user_sql_file <<< "${users[$user]}"
    user_sql_path="$SQL_DIR/$user_sql_file"

    if [[ ! -f "$user_passwd_file" ]]; then
        echo "Error: Not found password file at $user_passwd_file for $user user"
        continue
    fi
    if [[ ! -f "$user_sql_path" ]]; then
        echo "Error: Not found SQL file at $user_sql_path for $user user"
    fi

    user_passwd="$(tr -d '\r\n' < "$user_passwd_file")"
    echo "-> Setting up user: $user (Script: $user_sql_file)..."
    psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
             -v user_pass="$user_passwd" \
             -f "$user_sql_path"
done
unset PGPASSWORD

echo "All users processed."
