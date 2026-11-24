"""
Min-max regret model of CESM.

Extends :class:`cesm.core.model.Model` by one block of variables and constraints per scenario of worksheet
scenario_param and minimizes the maximum relative regret over all scenarios.
"""
import logging
import sqlite3
from pathlib import Path
from sqlite3 import Connection
from typing import Optional

from gurobipy import GRB

from cesm.core.min_max.min_max_dao import MinMaxDAO
from cesm.core.model import BASE_SCENARIO, Model

logger = logging.getLogger(__name__)


class MinMaxModel(Model):
    def __init__(self, conn: Connection, big_m: float = 1e6) -> None:
        """Build the base block. The blocks of the other scenarios are added by :meth:`solve_min_max`.

        Requires the techmap to be parsed with ``MinMaxParser``.
        """
        super().__init__(conn, big_m=big_m, scenario=BASE_SCENARIO)
        self.min_max_dao = MinMaxDAO(conn)
        self.min_max_vars: dict = {}
        self.min_max_constrs: dict = {}
        self.min_max_result: Optional[dict] = None

    def _pre_solve_min_max(self, pf_obj: str) -> tuple[list[str], list]:
        if pf_obj not in ("val", "bound"):
            raise ValueError(f"pf_obj must be 'val' or 'bound', not '{pf_obj}'")
        if len(self.sdao) > 1:
            raise RuntimeError("solve_min_max must be called once on a freshly built MinMaxModel(conn)")

        other_scenarios = self.min_max_dao.get_scenarios()
        if not other_scenarios:
            raise ValueError("No scenarios for the min-max optimization found in worksheet scenario_param. "
                             "Did you parse the techmap with MinMaxParser?")
        scenarios = [BASE_SCENARIO] + other_scenarios
        cs_equal = self.min_max_dao.get_cs_equal()
        if not cs_equal:
            logger.warning("Worksheet cs_equal is empty: no design variables are shared between the scenarios.")
        return scenarios, cs_equal

    # Gurobi parameters that are passed on to the perfect foresight models solved by solve_min_max
    _PF_COPIED_PARAMS = ("TimeLimit", "Threads", "OutputFlag", "LogToConsole", "MIPFocus", "NodefileStart")

    @staticmethod
    def perfect_foresight_db_path(pf_dir: Path, run_name: str, scenario: str) -> Path:
        """Database of the perfect foresight run of ``scenario``."""
        return Path(pf_dir) / f"{run_name}_pf_{scenario}.sqlite"

    def solve_min_max(self, pf_dir: Path, run_name: str, mip_gap: Optional[float] = None,
                      mip_gap_abs: Optional[float] = None, pf_mip_gap: Optional[float] = None,
                      pf_obj: str = "val", pf_start: bool = True) -> dict:
        """Minimize the maximum relative regret over all scenarios.

        Requires the techmap to be parsed with ``MinMaxParser``. The scenarios are "base" (the
        unmodified techmap) and the scenarios of worksheet scenario_param. Each scenario s gets its own copy of all
        variables and constraints with its parameter values. The design variables of every conversion subprocess
        in worksheet cs_equal are equal across all scenarios.

        The perfect foresight objective value f_s* of scenario s is read from the database
        ``pf_dir/{run_name}_pf_{s}.sqlite`` (table output_perfect_foresight). If that database does not exist, the
        perfect foresight run of s is solved and its results are written to it. Delete a database to recompute it,
        e.g. after changing the techmap.

        Parameters
        ----------
        pf_dir : directory of the perfect foresight databases.
        run_name : prefix of the perfect foresight database names.
        mip_gap : relative MIP gap of the min-max model. Note that the objective max_rel_regret is close to 0,
            so a relative gap is very strict; prefer ``mip_gap_abs``.
        mip_gap_abs : absolute MIP gap of the min-max model in units of max_rel_regret (e.g. 0.001 = 0.1 %-points).
        pf_mip_gap : relative MIP gap of the perfect foresight runs that compute missing f_s*.
        pf_obj : "val" uses the objective value (best solution found) of the perfect foresight runs as f_s*,
            "bound" uses the best bound. Equal if the perfect foresight runs are solved to optimality.
        pf_start : if True, the design of every perfect foresight solution becomes a MIP start of the min-max model:
            the design variables of the cs_equal conversion subprocesses of all blocks are set to that design,
            gurobi completes the remaining variables.
        """
        scenarios, cs_equal = self._pre_solve_min_max(pf_obj)
        logger.info("Min-max regret over scenarios %s with %d shared conversion subprocesses", scenarios, len(cs_equal))

        # 1. perfect foresight objective values
        pf_obj_vals = {}
        source = {}
        pf_paths = {}
        for s in scenarios:
            path = pf_paths[s] = self.perfect_foresight_db_path(pf_dir, run_name, s)
            if path.exists():
                source[s] = "read"
                logger.info("Perfect foresight database of scenario '%s' found: %s", s, path)
            else:
                source[s] = "computed"
                self._solve_perfect_foresight(s, pf_mip_gap, path)
            f = self._read_perfect_foresight(path, s, pf_obj)
            if f <= 0:
                raise ValueError(f"Perfect foresight objective value of scenario '{s}' is {f:g}, but the relative "
                                 "regret requires a positive value")
            pf_obj_vals[s] = f
        logger.info("Perfect foresight objective values:\n  %s",
                    "\n  ".join(f"{s}: {f:g} ({source[s]})" for s, f in pf_obj_vals.items()))

        # 2. one block of variables and constraints per scenario
        for s in scenarios[1:]:
            logger.info("Building block of scenario '%s'", s)
            self._add_scenario(s)

        # 3. equal design variables across all scenarios
        model = self.model
        years = self.dao.get_set("year")
        base_vars = self.scenario_vars[BASE_SCENARIO]
        base_units_cs = set(self.sdao[BASE_SCENARIO].get_set("conversion_subprocess_base_costs"))
        for s in scenarios[1:]:
            vars = self.scenario_vars[s]
            units_cs = set(self.sdao[s].get_set("conversion_subprocess_base_costs"))
            for var_name in ("Cap_new", "Cap_active"):
                self.scenario_constrs[s][f"equal_{var_name}"] = model.addConstrs(
                    (vars[var_name][cs, y] == base_vars[var_name][cs, y] for cs in cs_equal for y in years),
                    name=f"equal_{var_name}_{s}")
            mismatch = [cs for cs in cs_equal if (cs in units_cs) != (cs in base_units_cs)]
            if mismatch:
                raise ValueError(f"Scenario '{s}' changes whether these cs_equal conversion subprocesses have base "
                                 f"costs (capex_cost_base > 0), so their NewlyInstalledUnits can not be equal: {mismatch}")
            # equal NewlyInstalledUnits also makes the number of built units (their sum over the lifetime) equal
            self.scenario_constrs[s]["equal_NewlyInstalledUnits"] = model.addConstrs(
                (vars["NewlyInstalledUnits"][cs, y] == base_vars["NewlyInstalledUnits"][cs, y]
                 for cs in cs_equal if cs in units_cs for y in years),
                name=f"equal_NewlyInstalledUnits_{s}")

        # 4. relative regret
        max_rel_regret = model.addVar(lb=-GRB.INFINITY, name="max_rel_regret")
        self.min_max_vars = {"max_rel_regret": max_rel_regret}
        self.min_max_constrs = {
            "rel_regret": {
                s: model.addConstr(
                    (self.scenario_vars[s]["TOTEX"] - pf_obj_vals[s]) / pf_obj_vals[s] <= max_rel_regret,
                    name=f"rel_regret_{s}")
                for s in scenarios
            }
        }
        model.setObjective(max_rel_regret, GRB.MINIMIZE)

        # 5. perfect foresight designs as MIP starts
        if pf_start:
            self._set_perfect_foresight_starts(scenarios, cs_equal, pf_paths)

        # 6. solve
        if mip_gap_abs is not None:
            model.Params.MIPGapAbs = mip_gap_abs
        self.solve(mip_gap=mip_gap)
        if model.SolCount == 0:
            raise RuntimeError(f"Min-max optimization found no solution (gurobi status {model.Status})")

        totex = {s: self.scenario_vars[s]["TOTEX"].X for s in scenarios}
        self.min_max_result = {
            "max_rel_regret": max_rel_regret.X,
            "max_rel_regret_bound": model.ObjBound if model.IsMIP else max_rel_regret.X,
            "scenarios": {
                s: {
                    "totex": totex[s],
                    "perfect_foresight_obj_value": pf_obj_vals[s],
                    "rel_regret": (totex[s] - pf_obj_vals[s]) / pf_obj_vals[s],
                }
                for s in scenarios
            },
        }
        logger.info("Min-max regret: max_rel_regret = %.4f %%\n  %s", 100 * max_rel_regret.X, "\n  ".join(
            f"{s}: TOTEX = {r['totex']:g}, f* = {r['perfect_foresight_obj_value']:g}, rel. regret = {100 * r['rel_regret']:.4f} %"
            for s, r in self.min_max_result["scenarios"].items()))
        return self.min_max_result

    def _set_perfect_foresight_starts(self, scenarios: list[str], cs_equal: list, pf_paths: dict[str, Path]) -> None:
        model = self.model
        years = self.dao.get_set("year")
        model.NumStart = len(pf_paths)
        model.update()
        for k, (s_pf, path) in enumerate(pf_paths.items()):
            disk = sqlite3.connect(path)
            try:
                design = MinMaxDAO(disk).get_design()
            finally:
                disk.close()
            start_vars, start_vals = [], []
            for s in scenarios:
                vars = self.scenario_vars[s]
                units_cs = set(self.sdao[s].get_set("conversion_subprocess_base_costs"))
                for cs in cs_equal:
                    for y in years:
                        cap_new, cap_active, units = design.get((cs, y), (0.0, 0.0, 0.0))
                        start_vars += [vars["Cap_new"][cs, y], vars["Cap_active"][cs, y]]
                        start_vals += [cap_new, cap_active]
                        if cs in units_cs:
                            start_vars.append(vars["NewlyInstalledUnits"][cs, y])
                            start_vals.append(round(units or 0.0))
            model.Params.StartNumber = k
            model.setAttr("Start", start_vars, start_vals)
            model.update()
            logger.info("MIP start %d: design of the perfect foresight solution of scenario '%s' (%s)", k, s_pf, path)
        model.Params.StartNumber = 0

    def _solve_perfect_foresight(self, s: str, mip_gap: Optional[float], path: Path) -> None:
        """Solve scenario s on its own and write its results to the database ``path``."""
        if s == self.scenario:
            pf = self  # the base block is already built, solve it before the other blocks are added
        else:
            logger.info("Building perfect foresight model of scenario '%s'", s)
            pf = Model(self.conn, big_m=self.big_m, scenario=s)
            for param in self._PF_COPIED_PARAMS:
                pf.model.setParam(param, self.model.getParamInfo(param)[2])
        logger.info("Solving perfect foresight model of scenario '%s'", s)
        mip_gap_before = pf.model.Params.MIPGap
        pf.solve(mip_gap=mip_gap)
        pf.model.Params.MIPGap = mip_gap_before
        if pf.model.SolCount == 0:
            raise RuntimeError(f"Perfect foresight model of scenario '{s}' found no solution "
                               f"(gurobi status {pf.model.Status})")
        val = pf.model.ObjVal
        bound = pf.model.ObjBound if pf.model.IsMIP else val
        gap = pf.model.MIPGap if pf.model.IsMIP else 0.0

        def write(disk: Connection) -> None:
            pf.save_output(scenario=s, conn=disk)
            disk.execute("INSERT INTO output_perfect_foresight (scenario_param, obj_val, obj_bound, mip_gap) "
                         "VALUES (?, ?, ?, ?)", (s, val, bound, gap))
            disk.commit()

        self._write_scenario_db(path, s, write)
        logger.info("Perfect foresight results of scenario '%s' written to %s", s, path)
        if pf is not self:
            pf.model.dispose()

    @staticmethod
    def _read_perfect_foresight(path: Path, s: str, pf_obj: str) -> float:
        """Read f_s* (objective value or bound) from the perfect foresight database ``path``."""
        disk = sqlite3.connect(path)
        try:
            row = MinMaxDAO(disk).get_perfect_foresight(s)
        except sqlite3.OperationalError as e:
            raise ValueError(f"{path} is not a perfect foresight database of scenario '{s}': {e}") from e
        finally:
            disk.close()
        if row is None:
            raise ValueError(f"{path} has no perfect foresight result of scenario '{s}' "
                             "(table output_perfect_foresight). Delete it to recompute it.")
        val, bound, gap = row
        f = val if pf_obj == "val" else bound
        logger.info("Perfect foresight objective value of scenario '%s': %g (objective %g, bound %g, gap %.3f %%)",
                    s, f, val, bound, 100 * gap)
        return f

    _OUTPUT_TABLES = ("output_global", "output_y", "output_cs_y", "output_cs_y_t", "output_co_y_t", "output_min_max",
                      "output_perfect_foresight")

    def _write_scenario_db(self, path: Path, s: str, write) -> None:
        """Write a database with the techmap (parameter values of scenario s) and empty output tables to ``path``,
        then fill it with ``write(conn)``."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        disk = sqlite3.connect(path)
        try:
            self.conn.backup(disk)
            for table in self._OUTPUT_TABLES:
                disk.execute(f"DELETE FROM {table}")
            if s != BASE_SCENARIO:
                MinMaxDAO(disk).apply_scenario_params(s)
            write(disk)
        finally:
            disk.close()

    def save_output_min_max(self, output_dir: Path, run_name: str) -> dict[str, Path]:
        """Write one sqlite database per scenario of the min-max optimization.

        ``output_dir/{run_name}_{scenario}.sqlite`` holds the techmap with the scenario's parameter values, the
        results of that scenario and the table output_min_max with the regret of all scenarios.
        """
        if self.min_max_result is None:
            raise RuntimeError("Call solve_min_max before save_output_min_max")
        paths = {}
        for s in self.min_max_result["scenarios"]:
            path = Path(output_dir) / f"{run_name}_{s}.sqlite"

            def write(disk: Connection, s=s) -> None:
                self.save_output(scenario=s, conn=disk)
                self._write_min_max_result(disk)

            self._write_scenario_db(path, s, write)
            paths[s] = path
            logger.info("Results of scenario '%s' written to %s", s, path)
        return paths

    def _write_min_max_result(self, conn: Connection) -> None:
        for s, r in self.min_max_result["scenarios"].items():
            conn.execute(
                "INSERT INTO output_min_max (scenario_param, totex, perfect_foresight_obj_value, rel_regret, max_rel_regret) "
                "VALUES (?, ?, ?, ?, ?)",
                (s, r["totex"], r["perfect_foresight_obj_value"], r["rel_regret"], self.min_max_result["max_rel_regret"]))
        conn.commit()
