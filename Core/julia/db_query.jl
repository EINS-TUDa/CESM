using SQLite

function _iter_param(cursor::SQLite.Cursor, param_name::String)
    if haskey(Parser.param_index_dict, param_name)
        index_dict = Parser.param_index_dict[param_name]
        query = ""
        if index_dict == ["CS"]
            query = """
            SELECT pc.$(param_name), cp.name AS cp, cin.name AS cin, cout.name AS cout
            FROM param_cs AS pc
            JOIN conversion_subprocess AS cs ON pc.cs_id = cs.id
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            WHERE pc.$(param_name) IS NOT NULL;
            """
        elseif index_dict == ["Y"]
            query = """
            SELECT py.$(param_name), y.value
            FROM param_y AS py
            JOIN year AS y ON py.y_id = y.id
            WHERE py.$(param_name) IS NOT NULL;
            """
        elseif index_dict == ["CS", "Y"]
            query = """
            SELECT pcy.$(param_name), cp.name AS cp, cin.name AS cin, cout.name AS cout, y.value
            FROM param_cs_y AS pcy
            JOIN conversion_subprocess AS cs ON pcy.cs_id = cs.id
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            JOIN year AS y ON pcy.y_id = y.id
            WHERE pcy.$(param_name) IS NOT NULL;
            """
        elseif index_dict == ["CS", "T"]
            query = """
            SELECT pct.$(param_name), cp.name AS cp, cin.name AS cin, cout.name AS cout, ts.value
            FROM param_cs_t AS pct
            JOIN conversion_subprocess AS cs ON pct.cs_id = cs.id
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            JOIN time_step AS ts ON pct.t_id = ts.id
            WHERE pct.$(param_name) IS NOT NULL;
            """
        end

        # Execute the query and return the results
        return SQLite.execute(cursor, query)
    end
end

function _get_param(cursor::SQLite.Cursor, param_name::String, indices...)
    if haskey(Parser.param_index_dict, param_name)
        index_dict = Parser.param_index_dict[param_name]
        query = ""
        x = nothing
        if isempty(index_dict)
            query = "SELECT $(param_name) FROM param_global;"
        elseif index_dict == ["CS"]
            cs = indices[1]
            query = """
            SELECT pc.$(param_name)
            FROM param_cs AS pc
            JOIN conversion_subprocess AS cs ON pc.cs_id = cs.id
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            WHERE pc.$(param_name) IS NOT NULL AND cp.name ='$(cs.cp)' AND cin.name ='$(cs.cin)' AND cout.name ='$(cs.cout)';
            """
        elseif index_dict == ["Y"]
            y = indices[1]
            query = """
            SELECT py.$(param_name)
            FROM param_y AS py
            JOIN year AS y ON py.y_id = y.id
            WHERE py.$(param_name) IS NOT NULL AND y.value = $(y);
            """
        elseif index_dict == ["CS", "Y"]
            cs, y = indices
            query = """
            SELECT pcy.$(param_name)
            FROM param_cs_y AS pcy
            JOIN conversion_subprocess AS cs ON pcy.cs_id = cs.id
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            JOIN year AS y ON pcy.y_id = y.id
            WHERE pcy.$(param_name) IS NOT NULL AND cp.name ='$(cs.cp)' AND cin.name ='$(cs.cin)' AND cout.name ='$(cs.cout)' AND y.value = $(y);
            """
        elseif index_dict == ["CS", "T"]
            cs, t = indices
            query = """
            SELECT pct.$(param_name)
            FROM param_cs_t AS pct
            JOIN conversion_subprocess AS cs ON pct.cs_id = cs.id
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            JOIN time_step AS ts ON pct.t_id = ts.id
            WHERE pct.$(param_name) IS NOT NULL AND cs.name ='$(cs.cp)' AND cin.name ='$(cs.cin)' AND cout.name ='$(cs.cout)' AND ts.value = $(t);
            """
            
        end
        x = SQLite.execute(cursor, query)
        if x !== nothing
            return fetchone(x)
        end
    end
    return Parser.param_default_dict[param_name]
end


function _get_set(cursor::SQLite.Cursor, set_name::String)
    if set_name == "time"
        return [x[1] for x in cursor("SELECT value FROM time_step ORDER BY value;")]
    elseif set_name == "year"
        return [x[1] for x in cursor("SELECT value FROM year ORDER BY value;")]
    elseif set_name == "conversion_process"
        return [x[1] for x in cursor("SELECT name FROM conversion_process;")]
    elseif set_name == "commodity"
        return [x[1] for x in cursor("SELECT name FROM commodity;")]
    elseif set_name == "conversion_subprocess"
        query = """
        SELECT cp.name AS conversion_process_name, 
        cin.name AS input_commodity_name, 
        cout.name AS output_commodity_name 
        FROM conversion_subprocess AS cs
        JOIN conversion_process AS cp ON cs.cp_id = cp.id
        JOIN commodity AS cin ON cs.cin_id = cin.id
        JOIN commodity AS cout ON cs.cout_id = cout.id;
        """
        return [x for x in cursor(query)]
    elseif set_name == "storage_cs"
        query = """
        SELECT cp.name AS conversion_process_name, 
        cin.name AS input_commodity_name, 
        cout.name AS output_commodity_name 
        FROM conversion_subprocess AS cs
        JOIN conversion_process AS cp ON cs.cp_id = cp.id
        JOIN commodity AS cin ON cs.cin_id = cin.id
        JOIN commodity AS cout ON cs.cout_id = cout.id
        JOIN param_cs AS pc ON cs.id = pc.cs_id
        WHERE pc.is_storage = 1;
        """
        return [x for x in cursor(query)]
    end
end


function _get_discount_factor(cursor::SQLite.Cursor, y::Int)
    y_0 = _get_set(cutsor, "year")[1]
    return (1 + _get_param(cutsor, "discount_rate")) ^ (y_0 - y)
end


