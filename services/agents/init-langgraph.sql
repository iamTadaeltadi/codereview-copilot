-- 1. Ensure role exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles WHERE rolname = 'langgraph'
  ) THEN
    CREATE ROLE langgraph LOGIN PASSWORD 'langgraph';
  END IF;
END;
$$;

-- -- 2. Create checkpointer DB if missing
-- DO $$
-- BEGIN
--   IF NOT EXISTS (
--     SELECT FROM pg_database WHERE datname = 'checkpointer'
--   ) THEN
--     CREATE DATABASE checkpointer OWNER langgraph;
--   END IF;
-- END;
-- $$;
-- GRANT ALL PRIVILEGES ON DATABASE checkpointer TO langgraph;

-- -- 3. Create store DB if missing
-- DO $$
-- BEGIN
--   IF NOT EXISTS (
--     SELECT FROM pg_database WHERE datname = 'store'
--   ) THEN
--     CREATE DATABASE store OWNER langgraph;
--   END IF;
-- END;
-- $$;
-- GRANT ALL PRIVILEGES ON DATABASE store TO langgraph;