-- Create the 'output_t' table
CREATE TABLE IF NOT EXISTS output_t (
    id INTEGER PRIMARY KEY,
    t_id INTEGER,
    upper FLOAT,
    FOREIGN KEY (t_id) REFERENCES time(id),
    CONSTRAINT t_unique UNIQUE (t_id)
);