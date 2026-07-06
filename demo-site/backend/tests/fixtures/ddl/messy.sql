-- Mixed script: views, inserts, and comments must become warnings, not failures
CREATE TABLE widgets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label text NOT NULL,
    weight_kg numeric
);

INSERT INTO widgets (label, weight_kg) VALUES ('sample', 1.25);

CREATE VIEW heavy_widgets AS
    SELECT * FROM widgets WHERE weight_kg > 10;

CREATE TABLE crates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    widget_id uuid REFERENCES widgets (id) ON DELETE SET NULL,
    packed_at timestamptz DEFAULT now()
);

DROP TABLE IF EXISTS old_junk;
