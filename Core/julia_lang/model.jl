# Import the necessary functions and types from the required files
using SQLite
using JuMP
using Gurobi

# Include the data_access.jl file
include("data_access.jl")


# Define the CESM_Model type
mutable struct CESM_Model
    model::Model
    conn::Connection
    cursor::Cursor
    vars::Dict{String, Any}
    constrs::Dict{String, Any}
end

function CESM_Model(conn::Connection)
    cursor = conn.cursor()
    model = new(Model("model"), conn, cursor, DAO(conn), Dict{String, Any}(), Dict{String, Any}())
    _add_var!(model)
    _add_constr!(model)
    return model
end

# Define the _add_var method
function _add_var!(model::CESM_Model)
    vars = model.vars
    cursor = model.cursor
    # Costs
    vars["TOTEX"] = @variable(model.model, name="TOTEX")
    vars["CAPEX"] = @variable(model.model, name="CAPEX")
    vars["OPEX"] = @variable(model.model, name="OPEX")

    # CO2
    vars["Total_annual_co2_emission"] = @variable(model.model, get_set(cursor, "year"), name="Total_annual_co2_emission")

    # Power
    vars["Cap_new"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), name="Cap_new")
    vars["Cap_active"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), name="Cap_active")
    vars["Cap_res"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), name="Cap_res")
    vars["Pin"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), get_set(cursor, "time"), name="Pin")
    vars["Pout"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), get_set(cursor, "time"), name="Pout")

    # Energy
    vars["Eouttot"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), name="Eouttot")
    vars["Eintot"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), name="Eintot")
    vars["Eouttime"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), get_set(cursor, "time"), name="Eouttime")
    vars["Eintime"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), get_set(cursor, "time"), name="Eintime")
    vars["Enetgen"] = @variable(model.model, get_set(cursor, "commodity"), get_set(cursor, "year"), get_set(cursor, "time"), name="Enetgen")
    vars["Enetcons"] = @variable(model.model, get_set(cursor, "commodity"), get_set(cursor, "year"), get_set(cursor, "time"), name="Enetcons")

    # Storage
    vars["E_storage_level"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), get_set(cursor, "time"), name="E_storage_level")
    vars["E_storage_level_max"] = @variable(model.model, get_set(cursor, "conversion_subprocess"), get_set(cursor, "year"), name="E_storage_level_max")
end

# Define the _add_constr method (if needed)
function _add_constr!(model::CESM_Model)
    constrs = model.constrs
    cursor = model.cursor
    # Costs
    constrs["totex"] = @constraint(model.model, model.vars["TOTEX"] == model.vars["CAPEX"] + model.vars["OPEX"])
    constrs["capex"] = @constraint(model.model,
        model.vars["CAPEX"] == sum(get_discount_factor(cursor,y) *
        (get_param(cursor,"co2_price", y) * model.vars["Total_annual_co2_emission"][y] +
        sum(model.vars["Cap_new"][cs, y] * get_param(cursor,"capex_cost_power", cs, y) for cs in get_set(cursor, "conversion_subprocess")))
        for y in get_set(cursor, "year")),
        name="capex"
    )
        
    @constraint(model.model,
        model.vars["OPEX"] == sum(
        model.vars["Cap_active"][cs, y] * get_param(cursor,"opex_cost_power", cs, y) +
        model.vars["Eouttot"][cs, y] * get_param(cursor,"opex_cost_energy", cs, y)
        for cs in get_set(cursor, "conversion_subprocess")
        for y in get_set(cursor, "year")
        ),
        name="opex"
    )
        
    # Power Balance
    nondummy_commodities = Set(get_set(cursor, "commodity")) - Set(["Dummy"])
    constrs["power_balance"] = @constraint(model.model,
        [sum(model.vars["Pin"][cs, y, t] for cs in get_set(cursor, "conversion_subprocess") if cs.cin == co) ==
        sum(model.vars["Pout"][cs, y, t] for cs in get_set(cursor, "conversion_subprocess") if cs.cout == co)
        for t in get_set(cursor, "time")
        for y in get_set(cursor, "year")
        for co in nondummy_commodities],
        name="power_balance"
    )
        
    # CO2
    constrs["co2_emission_eq"] = @constraint(model.model,
        [model.vars["Total_annual_co2_emission"][y] ==
        sum(get_param(cursor,"spec_co2", cs) * model.vars["Eouttot"][cs, y] for cs in get_set(cursor, "conversion_subprocess"))
        for y in get_set(cursor, "year")],
        name="co2_emission_eq"
    )
    constrs["co2_emission_limit"] = @constraint(model.model,
        [model.vars["Total_annual_co2_emission"][y] <= limit
        for (y, limit) in iter_param(cursor, "annual_co2_limit")],
        name="co2_emission_limit"
    )
        
    # Power Output Constraints
    constrs["efficiency"] = @constraint(model.model,
        [model.vars["Pout"][cs, y, t] == model.vars["Pin"][cs, y, t] * get_param(cursor,"efficiency", cs)
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "conversion_subprocess")
        if cs ∉ get_set(cursor, "storage_cs")],
        name="efficiency_eq"
    )
    constrs["max_power_out"] = @constraint(model.model,
        [model.vars["Pout"][cs, y, t] <= model.vars["Cap_active"][cs, y]
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="max_power_out"
    )
    constrs["re_availability"] = @constraint(model.model,
        [model.vars["Pout"][cs, y, t] <= model.vars["Cap_active"][cs, y] * avail
        for y in get_set(cursor, "year")
        for (cs, t, avail) in iter_param(cursor, "availability_profile")],
        name="re_availability"
    )
    constrs["technical_availability"] = @constraint(model.model,
        [model.vars["Pout"][cs, y, t] <= model.vars["Cap_active"][cs, y] * get_param(cursor,"technical_availability", cs)
        for cs in get_set(cursor, "conversion_subprocess")
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")],
        name="technical_availability"
    )

    # Power Energy Constraints
    constrs["eouttime"] = @constraint(model.model,
        [model.vars["Eouttime"][cs, y, t] == model.vars["Pout"][cs, y, t] * get_param(cursor,"dt") * get_param(cursor,"w")
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="eouttime"
    )
        
    constrs["eintime"] = @constraint(model.model,
        [model.vars["Eintime"][cs, y, t] == model.vars["Pin"][cs, y, t] * get_param(cursor,"dt") * get_param(cursor,"w")
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="eintime"
    )

    # Fraction Equations
    constrs["min_cosupply"] = @constraint(model.model,
        [model.vars["Eouttime"][cs, y, t] >= out_frac_min * model.vars["Enetgen"][cs.cout, y, t]
        for t in get_set(cursor, "time")
        for (cs, y, out_frac_min) in iter_param(cursor, "out_frac_min")
        if out_frac_min != 0],
        name="min_cosupply"
    )
    constrs["max_cosupply"] = @constraint(model.model,
        [model.vars["Eouttime"][cs, y, t] <= out_frac_max * model.vars["Enetgen"][cs.cout, y, t]
        for t in get_set(cursor, "time")
        for (cs, y, out_frac_max) in iter_param(cursor, "out_frac_max")],
        name="max_cosupply"
    )
    constrs["min_couse"] = @constraint(model.model,
        [model.vars["Eintime"][cs, y, t] >= in_frac_min * model.vars["Enetcons"][cs.cin, y, t]
        for t in get_set(cursor, "time")
        for (cs, y, in_frac_min) in iter_param(cursor, "in_frac_min")],
        name="min_couse"
    )
    constrs["max_couse"] = @constraint(model.model,
        [model.vars["Eintime"][cs, y, t] <= in_frac_max * model.vars["Enetcons"][cs.cin, y, t]
        for t in get_set(cursor, "time")
        for (cs, y, in_frac_max) in iter_param(cursor, "in_frac_max")],
        name="max_couse"
    )

    # Capacity
    constrs["max_cap_res"] = @constraint(model.model,
        [model.vars["Cap_res"][cs, y] <= get_param(cursor,"cap_res_max", cs, y)
        for y in get_set(cursor, "year")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="max_cap_res"
    )
    constrs["min_cap_res"] = @constraint(model.model,
        [model.vars["Cap_res"][cs, y] >= get_param(cursor,"cap_res_min", cs, y)
        for y in get_set(cursor, "year")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="min_cap_res"
    )

    constrs["cap_active"] = @constraint(model.model,
        [model.vars["Cap_active"][cs, y] == model.vars["Cap_res"][cs, y] +
        sum(model.vars["Cap_new"][cs, yy] for yy in get_set(cursor, "year") if int(yy) in range(y - Int(get_param(cursor,"technical_lifetime", cs)), y + 1))
        for y in get_set(cursor, "year")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="cap_active"
    )
    constrs["max_cap_active"] = @constraint(model.model,
        [model.vars["Cap_active"][cs, y] <= cap_max
        for (cs, y, cap_max) in iter_param(cursor, "cap_max")],
        name="max_cap_active"
    )
    constrs["min_cap_active"] = @constraint(model.model,
        [model.vars["Cap_active"][cs, y] >= cap_min
        for (cs, y, cap_min) in iter_param(cursor, "cap_min")],
        name="min_cap_active"
    )

    # Energy
    constrs["energy_power_out"] = @constraint(model.model,
        [model.vars["Eouttot"][cs, y] == sum(model.vars["Eouttime"][cs, y, t] for t in get_set(cursor, "time"))
        for y in get_set(cursor, "year")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="energy_power_out"
    )
    constrs["energy_power_in"] = @constraint(model.model,
        [model.vars["Eintot"][cs, y] == sum(model.vars["Eintime"][cs, y, t] for t in get_set(cursor, "time"))
        for y in get_set(cursor, "year")
        for cs in get_set(cursor, "conversion_subprocess")],
        name="energy_power_in"
    )
    constrs["max_energy_out"] = @constraint(model.model,
        [model.vars["Eouttot"][cs, y] <= max_eout
        for (cs, y, max_eout) in iter_param(cursor, "max_eout")],
        name="max_energy_out"
    )
    constrs["min_energy_out"] = @constraint(model.model,
        [model.vars["Eouttot"][cs, y] >= min_eout
        for (cs, y, min_eout) in iter_param(cursor, "min_eout")],
        name="min_energy_out"
    )
    constrs["load_shape"] = @constraint(model.model,
        [model.vars["Eouttime"][cs, y, t] == output_profile * model.vars["Eouttot"][cs, y]
        for y in get_set(cursor, "year")
        for (cs, t, output_profile) in iter_param(cursor, "output_profile")],
        name="load_shape"
    )
    constrs["net_to_gen"] = @constraint(model.model,
        [model.vars["Enetgen"][co, y, t] == sum(model.vars["Eouttime"][cs, y, t] for cs in get_set(cursor, "conversion_subprocess") if cs.cout == co)
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for co in get_set(cursor, "commodity")],
        name="net_to_gen"
    )
    constrs["net_to_con"] = @constraint(model.model,
        [model.vars["Enetcons"][co, y, t] == sum(model.vars["Eintime"][cs, y, t] for cs in get_set(cursor, "conversion_subprocess") if cs.cin == co)
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for co in get_set(cursor, "commodity")],
        name="net_to_con"
    )

    # Storage
    constrs["storage_energy_limit"] = @constraint(model.model,
        [model.vars["E_storage_level"][cs, y, t] <= model.vars["E_storage_level_max"][cs, y]
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "storage_cs")],
        name="storage_energy_limit"
    )
    constrs["charge_power_limit"] = @constraint(model.model,
        [model.vars["Pin"][cs, y, t] <= model.vars["Cap_active"][cs, y]
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "storage_cs")],
        name="storage_charge_power_limit"
    )
    constrs["energy_balance"] = @constraint(model.model,
        [model.vars["E_storage_level"][cs, y, t] == model.vars["E_storage_level"][cs, y, findfirst(x -> x == t, get_set(cursor, "time")) - 1] +
        model.vars["Pin"][cs, y, t] * get_param(cursor,"dt", "global") * get_param(cursor,"efficiency_charge", cs) -
        model.vars["Pout"][cs, y, t] * get_param(cursor,"dt", "global") / get_param(cursor,"efficiency", cs)
        for y in get_set(cursor, "year")
        for t in get_set(cursor, "time")
        for cs in get_set(cursor, "storage_cs")],
        name="storage_energy_balance"
    )

    constrs["c_rate_relation"] = @constraint(model.model,
        [model.vars["E_storage_level_max"][cs, y] == model.vars["Cap_active"][cs, y] / get_param(cursor,"c_rate", cs)
        for y in get_set(cursor, "year")
        for cs in get_set(cursor, "storage_cs")],
        name="c_rate_relation"
    )

    @objective(model.model, Min, model.vars["TOTEX"])
end

function solve!(model::CESM_Model)
    set_optimizer(model.model, Gurobi.Optimizer)
    optimize!(model.model)
end


function save_output(model::CESM_Model)
    vars = model.vars
    cursor = model.cursor

    # Y
    for y in get_set(cursor, "year")
        query = """
        INSERT INTO output_y (y_id, total_annual_co2_emission)
        SELECT y.id, $(value(vars["Total_annual_co2_emission"][y]))
        FROM year AS y 
        WHERE y.value = $y;
        """
        execute(cursor, query)
    end

    # CS,Y
    for cs in get_set(cursor, "conversion_subprocess")
        for y in get_set(cursor, "year")
            cap_new = value(vars["Cap_new"][cs,y])
            cap_active = value(vars["Cap_active"][cs,y])
            cap_res = value(vars["Cap_res"][cs,y])
            eouttot = value(vars["Eouttot"][cs,y])
            eintot = value(vars["Eintot"][cs,y])
            e_storage_level_max =  value(vars["E_storage_level_max"][cs,y])
            if any(x -> x != 0, (cap_new, cap_active, cap_res, eouttot, eintot, e_storage_level_max))
                query = """
                INSERT INTO output_cs_y (cs_id, y_id, cap_new, cap_active, cap_res, eouttot, eintot, e_storage_level_max)  
                SELECT cs.id, y.id, $cap_new, $cap_active, $cap_res, $eouttot, $eintot, $e_storage_level_max
                FROM conversion_subprocess AS cs
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                CROSS JOIN year AS y
                WHERE cp.name = '$(cs.cp)' AND cin.name = '$(cs.cin)' AND cout.name = '$(cs.cout)' AND y.value = $y;
                """
                execute(cursor, query)
            end
        end
    end

    # CS,Y,T
    for cs in get_set(cursor, "conversion_subprocess")
        for y in get_set(cursor, "year")
            for t in get_set(cursor, "time")
                eouttime = value(vars["Eouttime"][cs,y,t])
                eintime = value(vars["Eintime"][cs,y,t])
                pin = value(vars["Pin"][cs,y,t])
                pout = value(vars["Pout"][cs,y,t])
                e_storage_level = value(vars["E_storage_level"][cs,y,t])
                if any(x -> x != 0, (eouttime, eintime, pin, pout, e_storage_level))
                    query = """
                    INSERT INTO output_cs_y_t (cs_id, y_id, t_id, eouttime, eintime, pin, pout, e_storage_level)
                    SELECT cs.id, y.id, t.id, $eouttime, $eintime, $pin, $pout, $e_storage_level
                    FROM conversion_subprocess AS cs
                    JOIN conversion_process AS cp ON cs.cp_id = cp.id
                    JOIN commodity AS cin ON cs.cin_id = cin.id
                    JOIN commodity AS cout ON cs.cout_id = cout.id
                    CROSS JOIN year AS y
                    CROSS JOIN time_step AS t
                    WHERE cp.name = '$(cs.cp)' AND cin.name = '$(cs.cin)' AND cout.name = '$(cs.cout)' AND y.value = $y AND t.value = $t;
                    """
                    execute(cursor, query)
                end
            end
        end
    end

    # CO,Y,T
    for co in get_set(cursor, "commodity")
        for y in get_set(cursor, "year")
            for t in get_set(cursor, "time")
                enetgen = value(vars["Enetgen"][co,y,t])
                enetcons = value(vars["Enetcons"][co,y,t])
                if any(x -> x != 0, (enetgen, enetcons))
                    query = """
                    INSERT INTO output_co_y_t (co_id, y_id, t_id, enetgen, enetcons)
                    SELECT co.id, y.id, t.id, $enetgen, $enetcons
                    FROM commodity AS co
                    CROSS JOIN year AS y
                    CROSS JOIN time_step AS t
                    WHERE co.name = '$co' AND y.value = $y AND t.value = $t;
                    """
                    execute(cursor, query)
                end
            end
        end
    end

    # without index
    query = """
    INSERT INTO output_global (OPEX, CAPEX, TOTEX) 
    VALUES ($(value(vars["OPEX"])), $(value(vars["CAPEX"])), $(value(vars["TOTEX"])));
    """
    execute(cursor, query)
    commit(cursor)
end




