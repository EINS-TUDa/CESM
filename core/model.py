"""
Energy System Planning Model in Gurobi Python API

Author: Sina Hajikazemi
Date: 10.10.2023
"""

import gurobipy as gp
from gurobipy import GRB
from core.data_access import DAO
from sqlite3 import Connection


class Model():
    def __init__(self, conn: Connection) -> None:
        self.model = gp.Model("DEModel")
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.dao = DAO(self.conn)

        self._add_var()
        self._add_constr()
    
    def _add_var(self) -> None:
        model = self.model # alias for readability
        self.vars = {}
        vars = self.vars # alias for readability
        get_set = self.dao.get_set

        # Costs
        vars["TOTEX"] = model.addVar(name="TOTEX")
        vars["CAPEX"] = model.addVar(name="CAPEX")
        vars["OPEX"] = model.addVar(name="OPEX")
        
        # CO2
        vars["Total_annual_co2_emission"] = model.addVars(get_set("year"), name="Total_annual_co2_emission")
        
        # Power
        vars["Cap_new"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), name="Cap_new")
        vars["Cap_active"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), name="Cap_active")
        vars["Cap_res"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), name="Cap_res")
        vars["Pin"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), get_set("time"), name="Pin")
        vars["Pout"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), get_set("time"), name="Pout")

        # Energy
        vars["Eouttot"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), name="Eouttot")
        vars["Eintot"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), name="Eintot")
        vars["Eouttime"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), get_set("time"), name="Eouttime")
        vars["Eintime"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), get_set("time"), name="Eintime")
        vars["Enetgen"] = model.addVars(get_set("commodity"), get_set("year"), get_set("time"), name="Enetgen")
        vars["Enetcons"] = model.addVars(get_set("commodity"), get_set("year"), get_set("time"), name="Enetcons")

        # Storage
        vars["E_storage_level"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), get_set("time"), name="E_storage_level")
        vars["E_storage_level_max"] = model.addVars(get_set("conversion_subprocess"), get_set("year"), name="E_storage_level_max")

    def _add_constr(self) -> None:
        model = self.model
        self.constrs = {}
        constrs = self.constrs # alias for readability
        vars = self.vars # alias for readability
        get_row = self.dao.get_row
        iter_row = self.dao.iter_row
        get_set = self.dao.get_set

        # Costs
        constrs["totex"] = model.addConstr(vars["TOTEX"] == vars["CAPEX"] + vars["OPEX"], name="totex")
        constrs["capex"] = model.addConstr(
                vars["CAPEX"] == sum(self.dao.get_discount_factor(y)*(
                    get_row("co2_price",y) * vars["Total_annual_co2_emission"][y] +
                    sum(vars["Cap_new"][cs,y] * get_row("capex_cost_power",cs, y) for cs in get_set("conversion_subprocess"))
                ) 
                for y in get_set("year")),
                name = "capex"
            )
        
        def year_gap(y):
            if y == get_set("year")[-1]:
                return 1
            else:
                index = get_set("year").index(y)
                return get_set("year")[index+1] - y
        model.addConstr(
            vars["OPEX"] == sum(
                (vars["Cap_active"][cs,y] *  get_row("opex_cost_power",cs,y) + vars["Eouttot"][cs,y] * get_row("opex_cost_energy",cs,y)) * (year_gap(y))
                for cs in get_set("conversion_subprocess") 
                for y in get_set("year")
            ),
            name = "opex"
        )
        
        # Power Balance
        nondummy_commodities = {co for co in get_set("commodity") if co != "Dummy"}
        constrs["power_balance"] = model.addConstrs(
            (
                sum(vars["Pin"][cs,y,t] for cs in get_set("conversion_subprocess") if cs.cin == co) == 
                sum(vars["Pout"][cs,y,t] for cs in get_set("conversion_subprocess") if cs.cout == co)
                for t in get_set("time")
                for y in get_set("year")
                for co in nondummy_commodities
            ),
            name = "power_balance"
        )
        
        # CO2
        constrs["co2_emission_eq"] = model.addConstrs(
            (
                vars["Total_annual_co2_emission"][y] == sum(get_row("spec_co2", cs) * vars["Eouttot"][cs,y] for cs in get_set("conversion_subprocess"))
                for y in get_set("year")
            ),
            name="co2_emission_eq"
        )
        constrs["co2_emission_limit"] = model.addConstrs(
            (
                vars["Total_annual_co2_emission"][y] <= limit
                for (y,limit) in iter_row("annual_co2_limit")
            ),
            name = "co2_emission_limit"
        )
        
        # Power Output Constraints
        constrs["efficiency"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] == vars["Pin"][cs,y,t] * get_row("efficiency",cs)
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("conversion_subprocess")
                if cs not in get_set("storage_cs")
            ),
            name = "efficiency_eq"
        )
        constrs["max_power_out"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] <= vars["Cap_active"][cs,y]
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("conversion_subprocess")
            ),
            name = "max_power_out"
        )
        constrs["re_availability"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] <= vars["Cap_active"][cs,y] * get_row("availability_profile",cs,t)
                for y in get_set("year")
                for cs in get_set("conversion_subprocess")
                for t in get_set("time")
                # for (cs,t, avail) in iter_row("availability_profile")
            ),
            name = "re_availability"
        )
        constrs["technical_availability"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] <= vars["Cap_active"][cs,y] * get_row("technical_availability",cs)
                for cs in get_set("conversion_subprocess") 
                for y in get_set("year")
                for t in get_set("time")          
            )
        ) 
        # Power Energy Constraints
        constrs["eouttime"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] == vars["Pout"][cs,y,t] * get_row("dt") * get_row("w") 
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("conversion_subprocess")
            ),
            name = "eouttime"
        )
        
        constrs["eintime"] = model.addConstrs(
            (
                vars["Eintime"][cs,y,t] == vars["Pin"][cs,y,t] * get_row("dt") * get_row("w")
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("conversion_subprocess")
            ),
            name = "eintime"
        )

        # Fraction Equations
        constrs["min_cosupply"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] >= out_frac_min * vars["Enetgen"][cs.cout,y,t]
                for t in get_set("time")
                for (cs,y, out_frac_min) in iter_row("out_frac_min")
                if out_frac_min != 0
            ),
            name = "min_cosupply"
        )
        constrs["max_cosupply"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] <= out_frac_max * vars["Enetgen"][cs.cout,y,t]
                for t in get_set("time")
                for (cs,y,out_frac_max) in iter_row("out_frac_max")
            ),
            name = "max_cosupply"
        )
        constrs["min_couse"] = model.addConstrs(
            (
                vars["Eintime"][cs,y,t] >= in_frac_min * vars["Enetcons"][cs.cin,y,t] 
                for t in get_set("time")
                for (cs,y, in_frac_min) in iter_row("in_frac_min")
            ),
            name = "min_couse"
        )
        constrs["max_couse"] = model.addConstrs(
            (
                vars["Eintime"][cs,y,t] <= in_frac_max * vars["Enetcons"][cs.cin,y,t]
                for t in get_set("time")
                for (cs,y,in_frac_max) in iter_row("in_frac_max")
            ),
            name = "max_couse"
        )

        # Capacity
        constrs["max_cap_res"] = model.addConstrs(
            (
                vars["Cap_res"][cs,y] <= get_row("cap_res_max",cs,y)
                for y in get_set("year")
                for cs in get_set("conversion_subprocess")
            ),
            name = "max_cap_res"
        )
        constrs["min_cap_res"] = model.addConstrs(
            (
                vars["Cap_res"][cs,y] >= get_row("cap_res_min",cs,y)
                for y in get_set("year")
                for cs in get_set("conversion_subprocess")
            ),
            name = "min_cap_res"
        )

        constrs["cap_active"] = model.addConstrs(
            (
                vars["Cap_active"][cs,y] == vars["Cap_res"][cs,y] + sum(vars["Cap_new"][cs,yy] for yy in get_set("year") if yy in range(y-get_row("technical_lifetime",cs)+1, y+1))
                for y in get_set("year")
                for cs in get_set("conversion_subprocess")
            ),
            name = "cap_active"
        )
        constrs["max_cap_active"] = model.addConstrs(
            (
                vars["Cap_active"][cs,y] <= cap_max
                for (cs,y,cap_max) in iter_row("cap_max")
            ),
            name = "max_cap_active"
        )
        constrs["min_cap_active"] = model.addConstrs(
            (
                vars["Cap_active"][cs,y] >= cap_min
                for (cs,y,cap_min) in iter_row("cap_min")
            ),
            name = "min_cap_active"
        )

        # Energy
        constrs["energy_power_out"] = model.addConstrs(
            (
                vars["Eouttot"][cs,y] == sum(vars["Eouttime"][cs,y,t] for t in get_set("time"))
                for y in get_set("year")
                for cs in get_set("conversion_subprocess")
            ),
            name = "energy_power_out"
        )
        constrs["energy_power_in"] = model.addConstrs(
            (
                vars["Eintot"][cs,y] == sum(vars["Eintime"][cs,y,t] for t in get_set("time"))
                for y in get_set("year")
                for cs in get_set("conversion_subprocess")
            ),
            name = "energy_power_in"
        )
        constrs["max_energy_out"] = model.addConstrs(
            (
                vars["Eouttot"][cs,y] <= max_eout
                for (cs,y,max_eout) in iter_row("max_eout")
            ),
            name = "max_energy_out"
        )
        constrs["min_energy_out"] = model.addConstrs(
            (
                vars["Eouttot"][cs,y] >= min_eout
                for (cs,y,min_eout) in iter_row("min_eout")
            ),
            name = "min_energy_out"
        )
        constrs["load_shape"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] == output_profile * vars["Eouttot"][cs,y]     
                for y in get_set("year")
                for (cs,t,output_profile) in iter_row("output_profile")
            ),
            name = "load_shape"
        )
        constrs["net_to_gen"] = model.addConstrs(
            (
                vars["Enetgen"][co,y,t] == sum(vars["Eouttime"][cs,y,t] for cs in get_set("conversion_subprocess") if cs.cout == co)
                for y in get_set("year")
                for t in get_set("time")
                for co in get_set("commodity")
            ),
            name = "net_to_gen"
        )
        constrs["net_to_con"] = model.addConstrs(
            (
                vars["Enetcons"][co,y,t] == sum(vars["Eintime"][cs,y,t] for cs in get_set("conversion_subprocess") if cs.cin == co)
                for y in get_set("year")
                for t in get_set("time")
                for co in get_set("commodity")
            ),
            name = "net_to_con"
        )

        # Storage
        constrs["storage_energy_limit"] = model.addConstrs(
            (
                vars["E_storage_level"][cs,y,t] <= vars["E_storage_level_max"][cs,y]
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("storage_cs")
            ),
            name = "storage_energy_limit"
        )
        constrs["charge_power_limit"] = model.addConstrs(
            (
                vars["Pin"][cs,y,t] <= vars["Cap_active"][cs,y]
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("storage_cs")
            ),
            name = "storage_charge_power_limit"
        )

        constrs["energy_balance"] = model.addConstrs(
            (
                vars["E_storage_level"][cs,y,t] == vars["E_storage_level"][cs,y,get_set("time")[get_set("time").index(t)-1]]  
                + vars["Pin"][cs,y,t] * get_row("dt","global") * get_row("efficiency_charge",cs) 
                - vars["Pout"][cs,y,t] * get_row("dt","global") / get_row("efficiency",cs) 
                for y in get_set("year")
                for t in get_set("time")
                for cs in get_set("storage_cs")
            ),
            name = "storage_energy_balance"
        )

        constrs["c_rate_relation"] = model.addConstrs(
            (
                vars["E_storage_level_max"][cs,y] == vars["Cap_active"][cs,y] / get_row("c_rate",cs)
                for y in get_set("year")
                for cs in get_set("storage_cs")
            ),
            name = "c_rate_relation"
        )

        model.setObjective(vars["TOTEX"]+0, GRB.MINIMIZE)

    def solve(self) -> None:
        return self.model.optimize()
    
    def save_output(self) -> None:
        vars = self.vars # alias for readability
        get_set = self.dao.get_set # alias for readability
        cursor = self.cursor # alias for readability
        # Y
        for y in get_set("year"):
            query = f"""
            INSERT INTO output_y (y_id, total_annual_co2_emission)
            SELECT y.id, {vars['Total_annual_co2_emission'][y].X}
            FROM year AS y 
            WHERE y.value = {y};
            """
            cursor.execute(query)
        # CS,Y
        for cs in get_set("conversion_subprocess"):
            for y in get_set("year"):
                cap_new = vars['Cap_new'][cs,y].X
                cap_active = vars['Cap_active'][cs,y].X
                cap_res = vars['Cap_res'][cs,y].X
                eouttot = vars['Eouttot'][cs,y].X
                eintot = vars['Eintot'][cs,y].X
                e_storage_level_max =  vars['E_storage_level_max'][cs,y].X
                if any(item != 0 for item in (cap_new, cap_active, cap_res, eouttot, eintot, e_storage_level_max)):
                    query = f"""
                    INSERT INTO output_cs_y (cs_id, y_id, cap_new, cap_active, cap_res, eouttot, eintot, e_storage_level_max)  
                    SELECT cs.id, y.id, {cap_new}, {cap_active}, {cap_res}, {eouttot}, {eintot}, {e_storage_level_max}
                    FROM conversion_subprocess AS cs
                    JOIN conversion_process AS cp ON cs.cp_id = cp.id
                    JOIN commodity AS cin ON cs.cin_id = cin.id
                    JOIN commodity AS cout ON cs.cout_id = cout.id
                    CROSS JOIN year AS y
                    WHERE cp.name = '{cs.cp}' AND cin.name = '{cs.cin}' AND cout.name = '{cs.cout}' AND y.value = {y};
                    """
                    cursor.execute(query)
        # CS,Y,T
        for cs in get_set("conversion_subprocess"):
            for y in get_set("year"):
                for t in get_set("time"):
                    eouttime = vars["Eouttime"][cs,y,t].X
                    eintime = vars["Eintime"][cs,y,t].X
                    pin = vars["Pin"][cs,y,t].X
                    pout = vars["Pout"][cs,y,t].X
                    e_storage_level = vars["E_storage_level"][cs,y,t].X
                    if any(item != 0 for item in (eouttime, eintime, pin, pout, e_storage_level)):
                        query = f"""
                        INSERT INTO output_cs_y_t (cs_id, y_id, t_id, eouttime, eintime, pin, pout, e_storage_level)
                        SELECT cs.id, y.id, t.id, {vars['Eouttime'][cs,y,t].X}, {vars['Eintime'][cs,y,t].X}, {vars['Pin'][cs,y,t].X}, {vars['Pout'][cs,y,t].X}, {vars['E_storage_level'][cs,y,t].X}
                        FROM conversion_subprocess AS cs
                        JOIN conversion_process AS cp ON cs.cp_id = cp.id
                        JOIN commodity AS cin ON cs.cin_id = cin.id
                        JOIN commodity AS cout ON cs.cout_id = cout.id
                        CROSS JOIN year AS y
                        CROSS JOIN time_step AS t
                        WHERE cp.name = '{cs.cp}' AND cin.name = '{cs.cin}' AND cout.name = '{cs.cout}' AND y.value = {y} AND t.value = {t};
                        """
                        cursor.execute(query)
        # CO,Y,T
        for co in get_set("commodity"):
            for y in get_set("year"):
                for t in get_set("time"):
                    enetgen = vars["Enetgen"][co,y,t].X
                    enetcons = vars["Enetcons"][co,y,t].X
                    if any(item != 0 for item in (enetgen, enetcons)):
                        query = f"""
                        INSERT INTO output_co_y_t (co_id, y_id, t_id, enetgen, enetcons)
                        SELECT co.id, y.id, t.id, {enetgen}, {enetcons}
                        FROM commodity AS co
                        CROSS JOIN year AS y
                        CROSS JOIN time_step AS t
                        WHERE co.name = '{co}' AND y.value = {y} AND t.value = {t};
                        """
                        cursor.execute(query)
        # without index
        query = f"""INSERT INTO output_global (OPEX, CAPEX, TOTEX) VALUES ({vars['OPEX'].X}, {vars['CAPEX'].X}, {vars['TOTEX'].X})"""
        cursor.execute(query)
        self.conn.commit()


# if __name__ == "__main__":
#     techmap_dir_path = Path(".").joinpath("Data", "Techmap") # techmap directory path
#     ts_dir_path = Path(".").joinpath("Data", "TimeSeries") # time series directory path
#     parser = Parser("DEModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base4twk")
#     parser.parse()
#     input = parser.get_input()
#     model = Model(input)
#     model.solve()
    
#     # save results
#     # sol_file_path = Path(".").joinpath("Runs", "sol_DEModel.sol")
#     # model.save_results(sol_file_path=sol_file_path)






        
    