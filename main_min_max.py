"""
Min-max regret run of CESM.

Solves the urban heat planning example of geopipe for the scenario "base" and all scenarios in the techmap worksheet
scenario_param with the design variables of the conversion subprocesses in worksheet cs_equal shared across scenarios.
The perfect foresight objective values are read from Runs/<model>-minmax/<model>_pf_<scenario>.sqlite. Missing
databases are computed first; delete one to recompute it.

Usage:
    python main_min_max.py [--time-limit SECONDS]
"""
import argparse
import logging
import sqlite3
import time
from pathlib import Path

from cesm.core.min_max.min_max_input_parser import MinMaxParser
from cesm.core.min_max.min_max_model import MinMaxModel

MODEL_NAME = "Example_45-4weeks"  # techmap name (without .xlsx)
SCENARIO = "45-4weeks"  # row of the techmap worksheet Scenario

TECHMAP_DIR_PATH = Path(__file__).resolve().parent.parent.joinpath(
    "geopipe", "examples", "urban_heat_planning", "output_data")
TS_DIR_PATH = TECHMAP_DIR_PATH.joinpath("profiles")
RUN_DIR_PATH = Path(__file__).resolve().parent.joinpath("Runs", f"{MODEL_NAME}-minmax")


def main(time_limit: float | None = None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    conn = sqlite3.connect(":memory:")
    parser = MinMaxParser(MODEL_NAME, techmap_dir_path=TECHMAP_DIR_PATH, ts_dir_path=TS_DIR_PATH, db_conn=conn,
                          scenario=SCENARIO)
    print("### parsing started ###")
    parser.parse()
    print("### parsing finished ###")

    print("### building base model started ###")
    st = time.time()
    model = MinMaxModel(conn)
    print(f"### building base model finished in {time.time() - st:.0f} s ###")

    if time_limit is not None:
        # applies to every single solve (perfect foresight runs and the min-max run)
        model.model.Params.TimeLimit = time_limit

    print("### solving min-max model started ###")
    st = time.time()
    result = model.solve_min_max(RUN_DIR_PATH, MODEL_NAME, mip_gap_abs=1e-3, pf_mip_gap=0.005)
    print(f"### solving min-max model finished in {time.time() - st:.0f} s ###")

    print(f"\nmax_rel_regret = {100 * result['max_rel_regret']:.3f} % "
          f"(bound {100 * result['max_rel_regret_bound']:.3f} %)")
    for s, r in result["scenarios"].items():
        print(f"  {s:>15}: TOTEX = {r['totex']:12.1f}, perfect foresight = {r['perfect_foresight_obj_value']:12.1f}, "
              f"rel. regret = {100 * r['rel_regret']:.3f} %")

    print("\n### saving results started ###")
    paths = model.save_output_min_max(RUN_DIR_PATH, MODEL_NAME)
    for s, p in paths.items():
        print(f"  {s}: {p}")
    print("### saving results finished ###")


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    arg_parser.add_argument("--time-limit", type=float, default=None,
                            help="Gurobi time limit in seconds for each solve (default: none)")
    main(arg_parser.parse_args().time_limit)
