-- Create the 'time' table
CREATE TABLE IF NOT EXISTS time_step (
    id INTEGER PRIMARY KEY,
    value INTEGER,
    CONSTRAINT value_unique UNIQUE (value)
);

-- Create the 'year' table
CREATE TABLE IF NOT EXISTS year (
    id INTEGER PRIMARY KEY,
    value INTEGER,
    CONSTRAINT value_unique UNIQUE (value)
);

-- Create the 'commodity' table
CREATE TABLE IF NOT EXISTS commodity (
    id INTEGER PRIMARY KEY,
    name TEXT,
    plot_color TEXT,
    plot_order INTEGER,
    CONSTRAINT name_unique UNIQUE (name)
);

-- Create the 'conversion_process' table
CREATE TABLE IF NOT EXISTS conversion_process (
    id INTEGER PRIMARY KEY,
    name TEXT,
    plot_color TEXT,
    plot_order INTEGER,
    CONSTRAINT name_unique UNIQUE (name)
);

-- Create the 'conversion_subprocess' table
CREATE TABLE IF NOT EXISTS conversion_subprocess (
    id INTEGER PRIMARY KEY,
    cp_id INTEGER,
    cin_id INTEGER,
    cout_id INTEGER,
    FOREIGN KEY (cp_id) REFERENCES conversion_process(id),
    FOREIGN KEY (cin_id) REFERENCES commodity(id),
    FOREIGN KEY (cout_id) REFERENCES commodity(id),
    CONSTRAINT cs_unique UNIQUE (cp_id,cin_id,cout_id)
);

-- Create the 'unit' table
CREATE TABLE IF NOT EXISTS unit (
    id INTEGER PRIMARY KEY,
    power FLOAT,
    energy FLOAT,
    co2_emissions FLOAT,
    cost_energy FLOAT,
    cost_power FLOAT,
    co2_spec FLOAT,
    -- Add a column that holds a constant value
    constant_column INTEGER DEFAULT 1,
    CONSTRAINT only_one_row UNIQUE (constant_column)
);


-- Create the 'param' table
CREATE TABLE IF NOT EXISTS param_global (
    id INTEGER PRIMARY KEY,
    dt FLOAT,
    w FLOAT,
    discount FLOAT,
    tss_name text,
    -- Add a column that holds a constant value
    constant_column INTEGER DEFAULT 1,
    CONSTRAINT only_one_row UNIQUE (constant_column)
);

-- Create the 'param_cs' table
CREATE TABLE IF NOT EXISTS param_cs (
    id INTEGER PRIMARY KEY,
    spec_co2 FLOAT,
    efficiency FLOAT,
    technical_lifetime FLOAT,
    technical_availability FLOAT,
    c_rate FLOAT,
    efficiency_charge FLOAT,
    cs_id INTEGER,
    FOREIGN KEY (cs_id) REFERENCES conversion_subprocess(id),
    CONSTRAINT cs_unique UNIQUE (cs_id)
);

-- Create the 'param_y' table
CREATE TABLE IF NOT EXISTS param_y (
    id INTEGER PRIMARY KEY,
    annual_co2_limit FLOAT,
    co2_price FLOAT,
    y_id INTEGER,
    FOREIGN KEY (y_id) REFERENCES year(id),
    CONSTRAINT y_unique UNIQUE (y_id)
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
    cs_id INTEGER,
    y_id INTEGER,
    FOREIGN KEY (cs_id) REFERENCES conversion_subprocess(id),
    FOREIGN KEY (y_id) REFERENCES year(id),
    CONSTRAINT cs_y_unique UNIQUE (cs_id, y_id)
);

-- Create the 'param_cs_t' table
CREATE TABLE IF NOT EXISTS param_cs_t (
    id INTEGER PRIMARY KEY,
    availability_profile FLOAT,
    output_profile FLOAT,
    cs_id INTEGER,
    t_id INTEGER,
    FOREIGN KEY (cs_id) REFERENCES conversion_subprocess(id),
    FOREIGN KEY (t_id) REFERENCES time(id),
    CONSTRAINT cs_t_unique UNIQUE (cs_id, t_id)
);

-- Output tables

-- Create the 'output_global' table
CREATE TABLE IF NOT EXISTS output_global (
    id INTEGER PRIMARY KEY,
    OPEX FLOAT,
    CAPEX FLOAT,
    TOTEX FLOAT,
    -- Add a column that holds a constant value
    constant_column INTEGER DEFAULT 1,
    CONSTRAINT only_one_row UNIQUE (constant_column)
);

-- Create the 'output_cs_y' table
CREATE TABLE IF NOT EXISTS output_cs (
    id INTEGER PRIMARY KEY,
    value FLOAT,
    cs_id INTEGER,
    y_id INTEGER,
    FOREIGN KEY (cs_id) REFERENCES conversion_subprocess(id),
    FOREIGN KEY (y_id) REFERENCES year(id),
    CONSTRAINT cs_y_unique UNIQUE (cs_id, y_id)
);

-- Create the 'output_cs_y_t' table
CREATE TABLE IF NOT EXISTS output_cs_t (
    id INTEGER PRIMARY KEY,
    value FLOAT,
    cs_id INTEGER,
    y_id INTEGER,
    t_id INTEGER,
    FOREIGN KEY (cs_id) REFERENCES conversion_subprocess(id),
    FOREIGN KEY (y_id) REFERENCES year(id),
    FOREIGN KEY (t_id) REFERENCES time(id),
    CONSTRAINT cs_y_t_unique UNIQUE (cs_id, y_id, t_id)
);

-- Create the 'output_co_y_t' table
CREATE TABLE IF NOT EXISTS output_co_y_t (
    id INTEGER PRIMARY KEY,
    value FLOAT,
    co_id INTEGER,
    y_id INTEGER,
    t_id INTEGER,
    FOREIGN KEY (co_id) REFERENCES commodity(id),
    FOREIGN KEY (y_id) REFERENCES year(id),
    FOREIGN KEY (t_id) REFERENCES time(id),
    CONSTRAINT co_y_t_unique UNIQUE (co_id, y_id, t_id)
);

