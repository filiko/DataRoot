-- Postgres: child table defined BEFORE parent, all FKs added via trailing ALTER TABLE
CREATE TABLE line_items (
    id bigint PRIMARY KEY,
    invoice_id bigint NOT NULL,
    product_sku text NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0)
);

CREATE TABLE invoices (
    id bigint PRIMARY KEY,
    number text NOT NULL,
    issued_on date NOT NULL
);

ALTER TABLE line_items
    ADD CONSTRAINT fk_line_items_invoice
    FOREIGN KEY (invoice_id) REFERENCES invoices (id)
    ON DELETE CASCADE ON UPDATE NO ACTION;
