-- Create the 'time' table
CREATE TABLE IF NOT EXISTS time (
    id INTEGER PRIMARY KEY,
    order INTEGER,
    value INTEGER
    CONSTRAINT value_unique UNIQUE (value),
    CONSTRAINT order_unique UNIQUE (order)
);

-- Create the 'year' table
CREATE TABLE IF NOT EXISTS year (
    id INTEGER PRIMARY KEY,
    order INTEGER,
    value INTEGER,
    CONSTRAINT order_unique UNIQUE (order),
    CONSTRAINT value_unique UNIQUE (value)
);

-- Create the 'commodity' table
CREATE TABLE IF NOT EXISTS commodity (
    id INTEGER PRIMARY KEY,
    name TEXT,
    CONSTRAINT name_unique UNIQUE (name)
);

-- Create the 'conversion_process' table
CREATE TABLE IF NOT EXISTS conversion_process (
    id INTEGER PRIMARY KEY,
    name TEXT,
    CONSTRAINT name_unique UNIQUE (name)
);

-- Create the 'conversion_subprocess' table
CREATE TABLE IF NOT EXISTS conversion_subprocess (
    id INTEGER PRIMARY KEY,
    name TEXT,
    cp INTEGER,
    cin INTEGER,
    cout INTEGER,
    FOREIGN KEY (cp) REFERENCES cp(id),
    FOREIGN KEY (cin) REFERENCES commodity(id),
    FOREIGN KEY (cout) REFERENCES commodity(id),
    CONSTRAINT name_unique UNIQUE (name),
    CONSTRAINT cs_unique UNIQUE (cp,cin,cout)
);

-- Create the 'param' table
CREATE TABLE IF NOT EXISTS param_global (
    id INTEGER PRIMARY KEY,
    dt FLOAT,
    discount FLOAT,
    -- Add a column that holds a constant value
    constant_column INTEGER DEFAULT 1,
    CONSTRAINT only_one_row UNIQUE (constant_column)
);

-- Create the 'param_cs' table
CREATE TABLE IF NOT EXISTS param_cs (
    id INTEGER PRIMARY KEY,
    spec_co2 FLOAT,
    efficiency FLOAT,
    technology_lifetime FLOAT,
    technical_availability FLOAT,
    c_rate FLOAT,
    efficiency_charge FLOAT,
    cs INTEGER,
    FOREIGN KEY (cs) REFERENCES conversion_process(id),
    CONSTRAINT cs_unique UNIQUE (cs)
);

-- Create the 'param_y' table
CREATE TABLE IF NOT EXISTS param_y (
    id INTEGER PRIMARY KEY,
    annual_co2_limit FLOAT,
    co2_price FLOAT,
    y INTEGER,
    FOREIGN KEY (y) REFERENCES year(id),
    CONSTRAINT y_unique UNIQUE (y)
);

-- Create the 'param_cs_y' table
CREATE TABLE IF NOT EXISTS param_cs_y (
    id INTEGER PRIMARY KEY,
    opex_cost_energy FLOAT,
    opex_cost_power FLOAT,
    capex_cost_power FLOAT,
    max_eout FLOAT,
    min_eout FLOAT,
    cap_min FLOAT,
    cap_max FLOAT,
    cap_res_max FLOAT,
    cap_res_min FLOAT,
    out_frac_min FLOAT,
    out_frac_max FLOAT,
    in_frac_min FLOAT,
    in_frac_max FLOAT,
    cs INTEGER,
    y INTEGER,
    FOREIGN KEY (cs) REFERENCES conversion_subprocess(id),
    FOREIGN KEY (y) REFERENCES year(id),
    CONSTRAINT cs_y_unique UNIQUE (cs, y)
);

-- Create the 'param_cs_t' table
CREATE TABLE IF NOT EXISTS param_cs_t (
    id INTEGER PRIMARY KEY,
    availability_profile FLOAT,
    output_profile FLOAT,
    cs INTEGER,
    t INTEGER,
    FOREIGN KEY (cs) REFERENCES cp(id),
    FOREIGN KEY (t) REFERENCES time(id),
    CONSTRAINT cs_t_unique UNIQUE (cs, t)
);


