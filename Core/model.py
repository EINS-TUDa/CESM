"""
Energy System Planning Model in Gurobi Python API

Author: Sina Hajikazemi
Date: 10.10.2023
"""

from pathlib import Path
import gurobipy as gp
from gurobipy import GRB
from Core import datacls as dtcls
from Core.inputparse import Parser
from sqlite3 import Connection

class Model():
    def __init__(self, conn: Connection) -> None:
        self.model = gp.Model("DEModel")
        self.conn = conn
        self.dataset = {}
        self._build_dataset()
        self._add_var()
        self._add_constr()
        
    def _build_dataset(self):
        self.dataset["time_steps"] = self.conn.execute("SELECT value FROM time_step;").fetchall()
        self.dataset["years"] = self.conn.execute("SELECT value FROM year;").fetchall()
        self.dataset["conversion_processes"] = self.conn.execute("SELECT name FROM conversion_process;").fetchall()
        self.dataset["conversion_subprocesses"] = self.conn.execute(
            """
            SELECT cp.name AS conversion_process_name, 
            cin.name AS input_commodity_name, 
            cout.name AS output_commodity_name 
            FROM conversion_subprocess AS cs
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id;
            """
        ).fetchall()
        self.dataset["commodities"] = self.conn.execute("SELECT name FROM commodity;").fetchall()
    def _get_param(self, param_name, **indices):
        pass

    def _iter_param(self, param_name):
        pass

    def _get_set(self, set_name):
        conn = self.conn # defined for readability
        query = None
        match set_name:
            case "time":
                return [x[0] for x in conn.execute("SELECT value FROM time_step;").fetchall()]
            case "year":
                return [x[0] for x in conn.execute("SELECT value FROM year;").fetchall()]
            case "conversion_process":
                query = "SELECT name FROM conversion_process;"
            case "conversion_subprocess":
                query = ...
            case "storage_cs":
                query = ...




    
    def _add_var(self) -> None:
        dataset = self.dataset # alias for readability
        model = self.model # alias for readability
        self.vars = {}
        vars = self.vars # alias for readability
        # Costs
        vars["TOTEX"] = model.addVar(name="TOTEX")
        vars["CAPEX"] = model.addVar(name="CAPEX")
        vars["OPEX"] = model.addVar(name="OPEX")
        
        # CO2
        vars["Total_annual_co2_emission"] = model.addVars(dataset["years"], name="Total_annual_co2_emission")
        
        # Power
        vars["Cap_new"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], name="Cap_new")
        vars["Cap_active"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], name="Cap_active")
        vars["Cap_res"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], name="Cap_res")
        vars["Pin"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], dataset["times"], name="Pin")
        vars["Pout"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], dataset["times"], name="Pout")

        # Energy
        vars["Eouttot"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], name="Eouttot")
        vars["Eintot"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], name="Eintot")
        vars["Eouttime"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], dataset["times"], name="Eouttime")
        vars["Eintime"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], dataset["times"], name="Eintime")
        vars["Enetgen"] = model.addVars(dataset.commodities, dataset["years"], dataset["times"], name="Enetgen")
        vars["Enetcons"] = model.addVars(dataset.commodities, dataset["years"], dataset["times"], name="Enetcons")

        # Storage
        vars["E_storage_level"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], dataset["times"], name="E_storage_level")
        vars["E_storage_level_max"] = model.addVars(dataset["conversion_subprocesses"], dataset["years"], name="E_storage_level_max")

    
    def _add_constr(self) -> None:
        model = self.model
        dataset = self.dataset
        self._constrs = {}
        constrs = self._constrs # alias for readability
        vars = self.vars # alias for readability
        
        # Costs
        constrs["totex"] = model.addConstr(vars["TOTEX"] == vars["CAPEX"] + vars["OPEX"], name="totex")
        constrs["capex"] = model.addConstr(
                vars["CAPEX"] == sum(get_param("discount_factor", y)*(
                    get_param("co2_price",y) * vars["Total_annual_co2_emission"][y] +
                    sum(vars["Cap_new"][cs,y] * get_param("capex_cost_power",cs, y) for cs in dataset["conversion_subprocesses"])
                ) 
                for y in dataset.years),
                name = "capex"
            )
        
        model.addConstr(
            vars["OPEX"] == sum(
                vars["Cap_active"][cs,y] *  get_param("opex_cost_power",cs,y) +
                vars["Eouttot"][cs,y] * get_param("opex_cost_energy",cs,y)
                for cs in dataset["conversion_subprocesses"] 
                for y in dataset["years"]         
            ),
            name = "opex"
        )
        
        # Power Balance
        nondummy_commodities = {co for co in dataset.commodities if co != "Dummy"}
        constrs["power_balance"] = model.addConstrs(
            (
                sum(vars["Pin"][cs,y,t] for cs in dataset["conversion_subprocesses"] if cs.cin == co) == 
                sum(vars["Pout"][cs,y,t] for cs in dataset["conversion_subprocesses"] if cs.cout == co)
                for t in dataset["times"]
                for y in dataset["years"]
                for co in nondummy_commodities
            ),
            name = "power_balance"
        )
        
        # CO2
        constrs["co2_emission_eq"] = model.addConstrs(
            (
                vars["Total_annual_co2_emission"][y] == sum(get_param("spec_co2", cs) * vars["Eouttot"][cs,y] for cs in dataset["conversion_subprocesses"])
                for y in dataset["years"]
            ),
            name="co2_emission_eq"
        )
        constrs["co2_emission_limit"] = model.addConstrs(
            (
                vars["Total_annual_co2_emission"][y] <= limit
                for (y,limit) in iter_param("annual_co2_limit")
            ),
            name = "co2_emission_limit"
        )
        
        # Power Output Constraints
        constrs["efficiency"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] == vars["Pin"][cs,y,t] * get_param("efficiency",cs)
                for y in dataset["years"]
                for t in dataset["times"]
                for cs in dataset["conversion_subprocesses"]
                if cs not in dataset["storage_cs"]
            ),
            name = "efficiency_eq"
        )
        constrs["max_power_out"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] <= vars["Cap_active"][cs,y]
                for y in dataset["years"]
                for t in dataset["times"]
                for cs in dataset["conversion_subprocesses"]
            ),
            name = "max_power_out"
        )
        constrs["re_availability"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] <= vars["Cap_active"][cs,y] * avail
                for y in dataset.years
                for (cs,t, avail) in iter_param("availability")
            ),
            name = "re_availability"
        )
        constrs["technical_availability"] = model.addConstrs(
            (
                vars["Pout"][cs,y,t] <= vars["Cap_active"][cs,y] * get_param("technical_availability",cs)
                for cs in dataset["conversion_subprocesses"] 
                for y in dataset.years
                for t in dataset.times            
            )
        ) 
        # Power Energy Constraints
        constrs["eouttime"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] == vars["Pout"][cs,y,t] * get_param("dt") * get_param("w") 
                for y in dataset["years"]
                for t in dataset["times"]
                for cs in dataset["conversion_subprocesses"]
            ),
            name = "eouttime"
        )
        
        constrs["eintime"] = model.addConstrs(
            (
                vars["Eintime"][cs,y,t] == vars["Pin"][cs,y,t] * get_param("dt") * get_param("w")
                for y in dataset["years"]
                for t in dataset["times"]
                for cs in dataset["conversion_subprocesses"]
            ),
            name = "eintime"
        )

        # Fraction Equations
        constrs["min_cosupply"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] >= out_frac_min * vars["Enetgen"][cs[2],y,t] # cs[2] is cout
                for t in dataset.times
                for (cs,y, out_frac_min) in iter_param("out_frac_min")
                if out_frac_min != 0
            ),
            name = "min_cosupply"
        )
        constrs["max_cosupply"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] <= out_frac_max * vars["Enetgen"][cs.cout,y,t]
                for t in dataset.times
                for (cs,y,out_frac_max) in iter_param("out_frac_max")
            ),
            name = "max_cosupply"
        )
        constrs["min_couse"] = model.addConstrs(
            (
                vars["Eintime"][cs,y,t] >= in_frac_min[cs,y, in_frac_min] * vars["Enetcons"][cs[1],y,t] # cs[1] is cin
                for t in dataset.times
                for (cs,y, in_frac_min) in iter_param("in_frac_min")
            ),
            name = "min_couse"
        )
        constrs["max_couse"] = model.addConstrs(
            (
                vars["Eintime"][cs,y,t] <= in_frac_max * vars["Enetcons"][cs[1],y,t] # cs[1] is cin
                for t in dataset.times
                for (cs,y,in_frac_max) in iter_param("in_frac_max")
            name = "max_couse"
        )

        # Capacity
        constrs["max_cap_res"] = model.addConstrs(
            (
                vars["Cap_res"][cs,y] <= get_param("cap_res_max",cs,y)
                for y in dataset["years"]
                for cs in dataset["conversion_subprocesses"]
            ),
            name = "max_cap_res"
        )
        constrs["min_cap_res"] = model.addConstrs(
            (
                vars["Cap_res"][cs,y] >= param.capacity.cap_res_min[cs,y]
                for (cs,y,cap_res_min) in iter_param("cap_res_min")
            ),
            name = "min_cap_res"
        )

        constrs["cap_active"] = model.addConstrs(
            (
                vars["Cap_active"][cs,y] == vars["Cap_res"][cs,y] + sum(vars["Cap_new"][cs,yy] for yy in dataset.years if int(yy) in range(int(y)-int(get_param("technical_lifetime",cs)), int(y)+1))
                for y in dataset["years"]
                for cs in dataset["conversion_subprocesses"]
            ),
            name = "cap_active"
        )
        constrs["max_cap_active"] = model.addConstrs(
            (
                vars["Cap_active"][cs,y] <= cap_max
                for (cs,y,cap_max) in iter_param("cap_max")
            ),
            name = "max_cap_active"
        )
        constrs["min_cap_active"] = model.addConstrs(
            (
                vars["Cap_active"][cs,y] >= cap_min
                for (cs,y,cap_min) in iter_param("cap_min")
            ),
            name = "min_cap_active"
        )

        # Energy
        constrs["energy_power_out"] = model.addConstrs(
            (
                vars["Eouttot"][cs,y] == sum(vars["Eouttime"][cs,y,t] for t in dataset["times"])
                for y in dataset["years"]
                for cs in dataset["conversion_subprocesses"]
            ),
            name = "energy_power_out"
        )
        constrs["energy_power_in"] = model.addConstrs(
            (
                vars["Eintot"][cs,y] == sum(vars["Eintime"][cs,y,t] for t in dataset.times)
                for y in dataset.years
                for cs in dataset.conversion_subprocesses
            ),
            name = "energy_power_in"
        )
        constrs["max_energy_out"] = model.addConstrs(
            (
                vars["Eouttot"][cs,y] <= max_eout
                for (cs,y,max_eout) in iter_param("max_eout")
            ),
            name = "max_energy_out"
        )
        constrs["min_energy_out"] = model.addConstrs(
            (
                vars["Eouttot"][cs,y] >= min_eout
                for (cs,y,min_eout) in iter_param("min_eout")
            ),
            name = "min_energy_out"
        )
        constrs["load_shape"] = model.addConstrs(
            (
                vars["Eouttime"][cs,y,t] == output_profile * vars["Eouttot"][cs,y]     
                for y in dataset.years
                for (cs,t,output_profile) in iter_param("output_profile")
            ),
            name = "load_shape"
        )
        constrs["net_to_gen"] = model.addConstrs(
            (
                vars["Enetgen"][co,y,t] == sum(vars["Eouttime"][cs,y,t] for cs in dataset.conversion_subprocesses if cs.cout == co)
                for y in dataset.years
                for t in dataset.times
                for co in dataset.commodities
            ),
            name = "net_to_gen"
        )
        constrs["net_to_con"] = model.addConstrs(
            (
                vars["Enetcons"][co,y,t] == sum(vars["Eintime"][cs,y,t] for cs in dataset.conversion_subprocesses if cs.cin == co)
                for y in dataset.years
                for t in dataset.times
                for co in dataset.commodities
            ),
            name = "net_to_con"
        )

        # Storage
        constrs["storage_energy_limit"] = model.addConstrs(
            (
                vars["E_storage_level"][cs,y,t] <= vars["E_storage_level_max"][cs,y]
                for y in dataset.years
                for t in dataset.times
                for cs in dataset.storage_cs
            ),
            name = "storage_energy_limit"
        )
        constrs["charge_power_limit"] = model.addConstrs(
            (
                vars["Pin"][cs,y,t] <= vars["Cap_active"][cs,y]
                for y in dataset.years
                for t in dataset.times
                for cs in dataset.storage_cs
            ),
            name = "storage_charge_power_limit"
        )

        constrs["energy_balance"] = model.addConstrs(
            (
                vars["E_storage_level"][cs,y,t] == vars["E_storage_level"][cs,y,dataset.times[dataset.times.index(t)-1]]  
                + vars["Pin"][cs,y,t] * get_param("dt","global") * get_param("efficiency_charge",cs) 
                - vars["Pout"][cs,y,t] * get_param("dt","global") / get_param("efficiency",cs) 
                for y in dataset.years
                for t in dataset.times
                for cs in dataset.storage_cs
            ),
            name = "storage_energy_balance"
        )

        constrs["c_rate_relation"] = model.addConstrs(
            (
                vars["E_storage_level_max"][cs,y] == vars["Cap_active"][cs,y] / get_param("c_rate",cs)
                for y in dataset.years
                for cs in dataset.storage_cs
            ),
            name = "c_rate_relation"
        )

        model.setObjective(vars["TOTEX"]+0, GRB.MINIMIZE)

    def solve(self) -> None:
        return self.model.optimize()
    
    def get_output(self) -> dtcls.Output:
        dataset = self.data.dataset # alias for readability
        vars = self.vars # alias for readability
        # Extract solution
        cs_y_indexes = [(cs,y) for cs in dataset.conversion_subprocesses for y in dataset.years]
        cs_y_t_indexes = [(cs,y,t) for cs in dataset.conversion_subprocesses for y in dataset.years for t in dataset.times]
        co_y_t_indexes = [(co,y,t) for co in dataset.commodities for y in dataset.years for t in dataset.times]
        cost = dtcls.CostOutput(OPEX=vars["OPEX"].X, CAPEX=vars["CAPEX"].X, TOTEX=vars["TOTEX"].X)
        co2 = dtcls.CO2Output(Total_annual_co2_emission= {y:vars["Total_annual_co2_emission"][y].X for y in dataset.years})
        power = dtcls.PowerOutput(
            Cap_new= {(cs,y): vars["Cap_new"][cs,y].X for (cs,y) in cs_y_indexes},
            Cap_active= {(cs,y): vars["Cap_active"][cs,y].X for (cs,y) in cs_y_indexes},
            Cap_res= {(cs,y): vars["Cap_res"][cs,y].X for (cs,y) in cs_y_indexes},
            Pin= {(cs,y,t): vars["Pin"][cs,y,t].X for (cs,y,t) in cs_y_t_indexes},
            Pout= {(cs,y,t): vars["Pout"][cs,y,t].X for (cs,y,t) in cs_y_t_indexes},
        )
        energy = dtcls.EnergyOutput(
            Eouttot= {(cs,y): vars["Eouttot"][cs,y].X for (cs,y) in cs_y_indexes},
            Eintot= {(cs,y): vars["Eintot"][cs,y].X for (cs,y) in cs_y_indexes},
            Eouttime= {(cs,y,t): vars["Eouttime"][cs,y,t].X for (cs,y,t) in cs_y_t_indexes},
            Eintime= {(cs,y,t): vars["Eintime"][cs,y,t].X for (cs,y,t) in cs_y_t_indexes},
            Enetgen= {(co,y,t): vars["Enetgen"][co,y,t].X for (co,y,t) in co_y_t_indexes},
            Enetcons= {(co,y,t): vars["Enetcons"][co,y,t].X for (co,y,t) in co_y_t_indexes},
        )
        storage = dtcls.StorageOutput(
            E_storage_level= {(cs,y,t): vars["E_storage_level"][cs,y,t].X for (cs,y,t) in cs_y_t_indexes},
            E_storage_level_max= {(cs,y): vars["E_storage_level_max"][cs,y].X for (cs,y) in cs_y_indexes}
        )

        output = dtcls.Output(
            cost= cost,
            co2= co2,
            power= power,
            energy = energy,
            storage= storage
        )
        return output

    
    def save_results(self, sol_file_path: Path) -> None:
        self.model.write(str(sol_file_path))

    def load_results(self, sol_file_path: Path) -> None:
        self.model.update()
        self.model.read(str(sol_file_path))


if __name__ == "__main__":
    techmap_dir_path = Path(".").joinpath("Data", "Techmap") # techmap directory path
    ts_dir_path = Path(".").joinpath("Data", "TimeSeries") # time series directory path
    parser = Parser("DEModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base4twk")
    parser.parse()
    input = parser.get_input()
    model = Model(input)
    model.solve()
    
    # save results
    # sol_file_path = Path(".").joinpath("Runs", "sol_DEModel.sol")
    # model.save_results(sol_file_path=sol_file_path)






        
    