-- Create the 'output_t' table
CREATE TABLE IF NOT EXISTS output_t (
    id INTEGER PRIMARY KEY,
    t_id INTEGER,
    upper FLOAT,
    FOREIGN KEY (t_id) REFERENCES time(id),
    CONSTRAINT t_unique UNIQUE (t_id)
);

-- Create the 'output_alg' table
CREATE TABLE IF NOT EXISTS output_alg (
    id INTEGER PRIMARY KEY,
    obj_upper FLOAT,
    obj_primal FLOAT,
    obj_dual FLOAT,
    cap_active_primal FLOAT,
    cap_active_dual FLOAT
);