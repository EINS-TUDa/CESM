"""Data access of the min-max regret optimization (worksheets scenario_param and cs_equal, perfect foresight runs)."""
from typing import Optional

from cesm.core.data_access import CS, DAO
from cesm.core.params import Param_Index_Dict


class MinMaxDAO(DAO):
    def get_scenarios(self) -> list[str]:
        """Scenarios of worksheet scenario_param in the order of their first row (without "base")."""
        rows = self.cursor.execute(
            "SELECT scenario_param FROM param_scenario GROUP BY scenario_param ORDER BY MIN(id)").fetchall()
        return [s for (s,) in rows]

    def get_cs_equal(self) -> list[CS]:
        query = """
        SELECT cp.name, cin.name, cout.name
        FROM cs_equal
        JOIN conversion_subprocess AS cs ON cs_id = cs.id
        JOIN conversion_process AS cp ON cs.cp_id = cp.id
        JOIN commodity AS cin ON cs.cin_id = cin.id
        JOIN commodity AS cout ON cs.cout_id = cout.id
        ORDER BY cs_equal.id;
        """
        return [CS(*x) for x in self.cursor.execute(query).fetchall()]

    def get_perfect_foresight(self, scenario: str) -> Optional[tuple[float, float, float]]:
        """(objective value, bound, MIP gap) of the perfect foresight run of ``scenario`` stored in this database."""
        return self.cursor.execute(
            "SELECT obj_val, obj_bound, mip_gap FROM output_perfect_foresight WHERE scenario_param = ?",
            (scenario,)).fetchone()

    def apply_scenario_params(self, scenario: str) -> None:
        """Write the parameter overrides of a scenario into the param tables of this database."""
        rows = self.cursor.execute(
            "SELECT param, cs_id, y_id, value FROM param_scenario WHERE scenario_param = ?", (scenario,)).fetchall()
        for param, cs_id, y_id, value in rows:
            match Param_Index_Dict[param]:
                case []:
                    self.cursor.execute(f"UPDATE param_global SET {param} = ?", (value,))
                case ["Y"]:
                    self.cursor.execute(f"""INSERT INTO param_y (y_id, {param}) VALUES (?, ?)
                        ON CONFLICT(y_id) DO UPDATE SET {param} = excluded.{param}""", (y_id, value))
                case ["CS"]:
                    self.cursor.execute(f"""INSERT INTO param_cs (cs_id, {param}) VALUES (?, ?)
                        ON CONFLICT(cs_id) DO UPDATE SET {param} = excluded.{param}""", (cs_id, value))
                case ["CS", "Y"]:
                    self.cursor.execute(f"""INSERT INTO param_cs_y (cs_id, y_id, {param}) VALUES (?, ?, ?)
                        ON CONFLICT(cs_id, y_id) DO UPDATE SET {param} = excluded.{param}""", (cs_id, y_id, value))
        self.conn.commit()

    def get_design(self) -> dict[tuple[CS, int], tuple[float, float, float]]:
        """Design (cap_new, cap_active, newly_installed_units) per (cs, year) of the results stored in this
        database. Missing (cs, year) have all values 0."""
        query = """
        SELECT cp.name, cin.name, cout.name, y.value, o.cap_new, o.cap_active, o.newly_installed_units
        FROM output_cs_y AS o
        JOIN conversion_subprocess AS cs ON o.cs_id = cs.id
        JOIN conversion_process AS cp ON cs.cp_id = cp.id
        JOIN commodity AS cin ON cs.cin_id = cin.id
        JOIN commodity AS cout ON cs.cout_id = cout.id
        JOIN year AS y ON o.y_id = y.id;
        """
        return {(CS(cp, cin, cout), y): (cap_new, cap_active, units)
                for cp, cin, cout, y, cap_new, cap_active, units in self.cursor.execute(query).fetchall()}
