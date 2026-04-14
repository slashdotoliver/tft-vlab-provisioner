DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'manager_db_user') THEN

      CREATE ROLE manager_db_user LOGIN;
   END IF;
END
$do$;

ALTER USER manager_db_user WITH PASSWORD :'user_pass';

GRANT CONNECT ON DATABASE lab_db TO manager_db_user;
GRANT USAGE ON SCHEMA public TO manager_db_user;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO manager_db_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO manager_db_user;
