-- Postgres: inline FKs, enum type, defaults, checks, unique, table comment
CREATE TYPE order_status AS ENUM ('pending', 'paid', 'shipped');

CREATE TABLE customers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    full_name varchar(255),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    status order_status NOT NULL,
    total numeric(10, 2) NOT NULL CHECK (total >= 0),
    placed_on date
);

CREATE TABLE customer_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL UNIQUE REFERENCES customers (id),
    bio text
);

CREATE INDEX idx_orders_customer ON orders (customer_id);
CREATE UNIQUE INDEX idx_customers_email ON customers (email);

COMMENT ON TABLE orders IS 'Customer purchase orders';
