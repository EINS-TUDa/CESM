from sqlite3 import Connection
from pandas import DataFrame
from itertools import chain
from typing import NamedTuple, Optional
from functools import lru_cache
from cesm.core.params import Param_Index_Dict, Output_Index_Dict, Param_Default_Dict

class CS(NamedTuple):
    cp: str
    cin: str
    cout: str

    def __repr__(self) -> str:
        return f"CS(cp='{self.cp}',cin='{self.cin}',cout='{self.cout}')"

# Data Access Object
class DAO():
    def __init__(self, conn : Connection) -> None:
        self.conn = conn
        self.cursor = conn.cursor()
        self.output_index_dict = Output_Index_Dict
    
    def get_as_dataframe(self, name: str, **filterby) -> DataFrame:
        param_or_out = 'output' if name in self.output_index_dict else 'param'
        if name in self.output_index_dict:
            indexes = self.output_index_dict.get(name)
        elif name in Param_Index_Dict:
            indexes = Param_Index_Dict.get(name)
        else:
            raise ValueError(f"{name} is not neither input parameter nor output variable")

        # make headers
        headers = []
        for index in indexes:
            if index == 'CS':
                headers.extend(['cp','cin','cout'])
            elif index == 'CO':
                headers.append('Commodity')
            elif index == 'Y':
                headers.append('Year')
            elif index == 'T':
                headers.append('Time')
            else:
                headers.append(index)
        headers.append('value')

        rows = self.iter_row(name)
        if 'CS' in indexes:
            ind = indexes.index('CS')
            rows = [(*row[0:ind],row[ind].cp,row[ind].cin,row[ind].cout, *row[ind+1:]) for row in rows]
        df = DataFrame(rows, columns=headers)
        for k, v in filterby.items():
            try:
                df = df[df[k] == v]
            except KeyError:
                raise Exception(f"Key {k} not found in DataFrame! Existing keys: {df.columns}")
        return df

    def get_units(self):
        unit_rows = self.cursor.execute(f"""SELECT quantity, output FROM unit""").fetchall()
        return {quantity:output for (quantity, output) in unit_rows}
    
    def get_plot_settings(self):
        co_rows = self.cursor.execute(f"""SELECT name, plot_color, plot_order FROM commodity""").fetchall()
        cp_rows = self.cursor.execute(f"""SELECT name, plot_color, plot_order FROM conversion_process""").fetchall()
        return {name:{"color":color, "order": order} for (name, color, order) in chain(co_rows,cp_rows)}
    
    def iter_row(self, name:str):
        param_or_out = 'output' if name in self.output_index_dict else 'param'
        if name in self.output_index_dict:
            indexes = self.output_index_dict.get(name)
        elif name in Param_Index_Dict:
            indexes = Param_Index_Dict.get(name)
        else:
            raise ValueError(f"{name} is not neither input parameter nor output variable")
        cursor = self.cursor
        name = name.lower()
        match indexes:
            case []:
                 return [self.cursor.execute(f"SELECT {name} FROM {param_or_out}_global").fetchone()[0]]
            case ["CS"]:
                query = f"""
                SELECT {name}, cp.name, cin.name, cout.name 
                FROM {param_or_out}_cs
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                WHERE {name} IS NOT NULL;
                """
                return [(CS(*x[1:4]),x[0]) for x in cursor.execute(query).fetchall()]
            case ["Y"]:
                query = f"""
                SELECT {name}, y.value
                FROM {param_or_out}_y
                JOIN year AS y ON y_id = y.id
                WHERE {name} IS NOT NULL;
                """
                return [(x[1],x[0]) for x in cursor.execute(query).fetchall()]
            case ["CS","Y"]:
                query = f"""
                SELECT {name}, cp.name, cin.name, cout.name, y.value
                FROM {param_or_out}_cs_y
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN year AS y ON y_id = y.id
                WHERE {name} IS NOT NULL;
                """
                return [(CS(*x[1:4]),x[4],x[0]) for x in cursor.execute(query).fetchall()]
            case ["CS","T"]:
                query = f"""
                SELECT {name}, cp.name, cin.name, cout.name, ts.value
                FROM {param_or_out}_cs_t AS pct
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN time_step AS ts ON t_id = ts.id
                WHERE {name} IS NOT NULL;
                """
                return [(CS(*x[1:4]),x[4],x[0]) for x in cursor.execute(query).fetchall()]
            case ['CS','Y','T']:
                query = f"""
                    SELECT {name}, cp.name, cin.name, cout.name, y.value, t.value
                    FROM {param_or_out}_cs_y_t
                    JOIN conversion_subprocess AS cs ON cs_id = cs.id
                    JOIN conversion_process AS cp ON cs.cp_id = cp.id
                    JOIN commodity AS cin ON cs.cin_id = cin.id
                    JOIN commodity AS cout ON cs.cout_id = cout.id
                    JOIN year AS y ON y_id = y.id
                    JOIN time_step AS t ON t_id = t.id
                    WHERE {name} IS NOT NULL;
                """
                return [(CS(*x[1:4]),x[4],x[5],x[0]) for x in cursor.execute(query).fetchall()]
            case ['CO','Y','T']:
                query = f"""
                    SELECT {name}, c.name, y.value, t.value
                    FROM {param_or_out}_co_y_t
                    JOIN commodity AS c ON co_id = c.id
                    JOIN year AS y ON y_id = y.id
                    JOIN time_step AS t ON t_id = t.id
                    WHERE {name} IS NOT NULL;
                """
                return [(x[1],x[2],x[3],x[0]) for x in cursor.execute(query).fetchall()]
            
    def get_row(self, name, *indices):
        cursor = self.cursor # defined for readability
        param_or_out = 'output' if name in self.output_index_dict else 'param'
        if name in self.output_index_dict:
            indexes = self.output_index_dict.get(name)
        elif name in Param_Index_Dict:
            indexes = Param_Index_Dict.get(name)
        else:
            raise ValueError(f"{name} is not neither input parameter nor output variable")
        name = name.lower()
        match indexes:
            case []:
                x = cursor.execute(f"SELECT {name} FROM {param_or_out}_global;").fetchone()
            case ["CS"]:
                cs = indices[0]
                query = f"""
                SELECT {name}
                FROM {param_or_out}_cs
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                WHERE {name} IS NOT NULL AND cp.name ='{cs.cp}' AND cin.name ='{cs.cin}' AND cout.name ='{cs.cout}';
                """
                x = cursor.execute(query).fetchone()
            case ["Y"]:
                y = indices[0]
                query = f"""
                SELECT {name}
                FROM {param_or_out}_y
                JOIN year AS y ON y_id = y.id
                WHERE {name} IS NOT NULL AND y.value ={y};
                """
                x = cursor.execute(query).fetchone()
            case ["T"]:
                t = indices[0]
                query = f"""
                SELECT {name}
                FROM {param_or_out}_t 
                JOIN time_step AS t ON t_id = t.id
                WHERE {name} IS NOT NULL AND t.value ={t};
                """
                x = cursor.execute(query).fetchone()
            case ["CS","Y"]:
                cs, y = indices
                query = f"""
                SELECT {name}
                FROM {param_or_out}_cs_y
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN year AS y ON y_id = y.id
                WHERE {name} IS NOT NULL AND cp.name ='{cs.cp}' AND cin.name ='{cs.cin}' AND cout.name ='{cs.cout}' AND y.value ={y};
                """
                x = cursor.execute(query).fetchone()
            case ["CS","T"]:
                cs, t = indices
                query = f"""
                SELECT {name}
                FROM {param_or_out}_cs_t
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN time_step AS ts ON t_id = ts.id
                WHERE {name} IS NOT NULL AND cp.name ='{cs.cp}' AND cin.name ='{cs.cin}' AND cout.name ='{cs.cout}' AND ts.value ={t};
                """
                x = cursor.execute(query).fetchone()
        if param_or_out == 'param':
            return (x[0] if x else Param_Default_Dict[name])
        else: # out
            return (x[0] if x else 0)
    
    @lru_cache(maxsize=None)
    def get_set(self, set_name):
        cursor = self.cursor # defined for readability
        match set_name:
            case "time":
                return [x[0] for x in cursor.execute("SELECT value FROM time_step ORDER BY value;").fetchall()]
            case "year":
                return [x[0] for x in cursor.execute("SELECT value FROM year ORDER BY value;").fetchall()]
            case "conversion_process":
                return [x[0] for x in cursor.execute("SELECT name FROM conversion_process;").fetchall()]
            case "commodity":
                return [x[0] for x in cursor.execute("SELECT name FROM commodity;").fetchall()]
            case "conversion_subprocess":
                query = """
                SELECT cp.name AS conversion_process_name, 
                cin.name AS input_commodity_name, 
                cout.name AS output_commodity_name 
                FROM conversion_subprocess AS cs
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id;
                """
                return [CS(*x) for x in self.cursor.execute(query).fetchall()]
            case "conversion_subprocess_base_costs":
                query = """
                SELECT DISTINCT cp.name, cin.name, cout.name
                FROM param_cs_y
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                WHERE capex_cost_base > 0;
                """
                return [CS(*x) for x in self.cursor.execute(query).fetchall()]
            case "storage_cs":
                query = """
                SELECT cp.name AS conversion_process_name, 
                cin.name AS input_commodity_name, 
                cout.name AS output_commodity_name 
                FROM conversion_subprocess AS cs
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN param_cs AS pc ON cs.id = pc.cs_id
                WHERE pc.is_storage = true;
                """
                return [CS(*x) for x in self.cursor.execute(query).fetchall()]

    def get_discount_factor(self, y: int) -> float:
         y_0 = self.get_set("year")[0]
         return (1 + self.get_row("discount_rate"))**(y_0 - y)


class ScenarioDAO():
    """Read-only view on the input parameters of one scenario.

    Returns the scenario specific value of a parameter where the scenario overrides it and the techmap value
    otherwise. Parameter lookups are cached, which speeds up building the model considerably.
    """
    _BASE_COSTS_PARAMS = {"capex_cost_base"}
    _STORAGE_PARAMS = {"is_storage"}

    def __init__(self, dao: DAO, scenario: Optional[str] = None) -> None:
        self.dao = dao
        self.scenario = scenario
        self.overrides = self._load_overrides(dao, scenario)
        self._overridden_params = {key[0] for key in self.overrides}
        self._row_cache = {}
        self._iter_cache = {}
        self._set_cache = {}

    @staticmethod
    def _load_overrides(dao: DAO, scenario: Optional[str]) -> dict[tuple, float]:
        """Parameter overrides of a scenario as {(param, *indices): value}, indices as used by get_row."""
        if scenario is None:
            return {}
        query = """
        SELECT ps.param, cp.name, cin.name, cout.name, y.value, ps.value
        FROM param_scenario AS ps
        LEFT JOIN conversion_subprocess AS cs ON ps.cs_id = cs.id
        LEFT JOIN conversion_process AS cp ON cs.cp_id = cp.id
        LEFT JOIN commodity AS cin ON cs.cin_id = cin.id
        LEFT JOIN commodity AS cout ON cs.cout_id = cout.id
        LEFT JOIN year AS y ON ps.y_id = y.id
        WHERE ps.scenario_param = ?;
        """
        overrides = {}
        for param, cp, cin, cout, y, value in dao.cursor.execute(query, (scenario,)).fetchall():
            indices = []
            for index in Param_Index_Dict[param]:
                if index == "CS":
                    indices.append(CS(cp, cin, cout))
                elif index == "Y":
                    indices.append(y)
            overrides[(param, *indices)] = value
        return overrides

    def get_row(self, name, *indices):
        key = (name, *indices)
        if key in self.overrides:
            return self.overrides[key]
        if name in self.dao.output_index_dict:
            return self.dao.get_row(name, *indices)
        try:
            return self._row_cache[key]
        except KeyError:
            value = self._row_cache[key] = self.dao.get_row(name, *indices)
            return value

    def iter_row(self, name: str):
        if name in self.dao.output_index_dict:
            return self.dao.iter_row(name)
        if name not in self._iter_cache:
            rows = self.dao.iter_row(name)
            if name in self._overridden_params:
                merged = {tuple(row[:-1]): row[-1] for row in rows}
                merged.update({key[1:]: value for key, value in self.overrides.items() if key[0] == name})
                rows = [(*idx, value) for idx, value in merged.items()]
            self._iter_cache[name] = rows
        return self._iter_cache[name]

    def get_set(self, set_name):
        if set_name not in self._set_cache:
            if set_name == "conversion_subprocess_base_costs" and self._overridden_params & self._BASE_COSTS_PARAMS:
                base_cost_cs = {cs for cs, _, v in self.iter_row("capex_cost_base") if v is not None and v > 0}
                value = [cs for cs in self.dao.get_set("conversion_subprocess") if cs in base_cost_cs]
            elif set_name == "storage_cs" and self._overridden_params & self._STORAGE_PARAMS:
                value = [cs for cs in self.dao.get_set("conversion_subprocess") if self.get_row("is_storage", cs)]
            else:
                value = self.dao.get_set(set_name)
            self._set_cache[set_name] = value
        return self._set_cache[set_name]

    def get_discount_factor(self, y: int) -> float:
        y_0 = self.get_set("year")[0]
        return (1 + self.get_row("discount_rate"))**(y_0 - y)
