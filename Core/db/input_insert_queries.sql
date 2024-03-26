INSERT INTO time (order,value) VALUES (?,?);

INSERT INTO year (order, value) VALUES (?, ?);

INSERT INTO commodity (name) VALUES (?);

INSERT INTO conversion_process (name) VALUES (?);

INSERT INTO conversion_subprocess (name, cp, cin, cout) 
    VALUES (?, (SELECT id FROM conversion_process WHERE name = ?),
            (SELECT id FROM commodity WHERE name = ?),
            (SELECT id FROM commodity WHERE name = ?))


INSERT INTO param_global (dt, discount, tss_name) VALUES (?, ?, ?);

INSERT INTO param_cs (spec_co2, efficiency, technology_lifetime, technical_availability, c_rate, efficiency_charge, cs) 
    VALUES (?, ?, ?, ?, ?, ?, (SELECT id FROM conversion_process WHERE name = ?));


INSERT INTO param_y (annual_co2_limit, co2_price, y) 
    VALUES (?, ?, (SELECT id FROM year WHERE value = ?));

INSERT INTO param_cs_y (opex_cost_energy, opex_cost_power, capex_cost_power, max_eout, min_eout, cap_min, cap_max, cap_res_max, cap_res_min, out_frac_min, out_frac_max, in_frac_min, in_frac_max, cs, y) 
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
        (SELECT id FROM conversion_subprocess WHERE name = ?), 
        (SELECT id FROM year WHERE value = ?));