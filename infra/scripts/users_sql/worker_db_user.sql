DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'worker_db_user') THEN

      CREATE ROLE worker_db_user LOGIN;
   END IF;
END
$do$;

ALTER USER worker_db_user WITH PASSWORD :'user_pass';

GRANT CONNECT ON DATABASE lab_db TO worker_db_user;
GRANT USAGE ON SCHEMA public TO worker_db_user;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO worker_db_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO worker_db_user;
