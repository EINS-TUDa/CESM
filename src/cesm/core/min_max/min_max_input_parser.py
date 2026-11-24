"""
Input parser of the min-max regret optimization.

Parses the techmap like :class:`cesm.core.input_parser.Parser` and additionally reads the worksheets
scenario_param and cs_equal, which hold the data for :class:`cesm.core.min_max.min_max_model.MinMaxModel`.
"""
import logging

import pandas as pd

from cesm.core.input_parser import Parser

logger = logging.getLogger(__name__)


class MinMaxParser(Parser):
    def _parse(self, tmap) -> None:
        super()._parse(tmap)
        self.read_min_max(tmap)

    MIN_MAX_SHEETS = ("scenario_param", "cs_equal")
    BASE_SCENARIO = "base"
    CS_COLUMNS = ["conversion_process_name", "commodity_in", "commodity_out"]

    def read_min_max(self, tmap) -> None:
        missing = [s for s in self.MIN_MAX_SHEETS if s not in tmap.sheet_names]
        if missing:
            raise ValueError(f"Min-max optimization requires the techmap worksheets {list(self.MIN_MAX_SHEETS)}. "
                             f"Missing: {missing}")
        self.read_scenario_param(tmap)
        self.read_cs_equal(tmap)
        self.conn.commit()

    @staticmethod
    def _check_columns(df, sheet, columns) -> None:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"Worksheet {sheet} is missing the columns {missing}. Expected columns: {columns}")

    def _get_cs_id(self, cp, cin, cout):
        row = self.cursor.execute("""
            SELECT cs.id FROM conversion_subprocess AS cs
            JOIN conversion_process AS cp ON cs.cp_id = cp.id
            JOIN commodity AS cin ON cs.cin_id = cin.id
            JOIN commodity AS cout ON cs.cout_id = cout.id
            WHERE cp.name = ? AND cin.name = ? AND cout.name = ?""", (cp, cin, cout)).fetchone()
        return None if row is None else row[0]

    def read_scenario_param(self, tmap) -> None:
        sheet = "scenario_param"
        columns = ["scenario_param", "param", *self.CS_COLUMNS, "year", "value"]
        df = pd.read_excel(tmap, sheet)
        self._check_columns(df, sheet, columns)
        df = df.dropna(how="all")
        years = dict(self.cursor.execute("SELECT value, id FROM year").fetchall())

        errors = []
        seen = set()
        for i, row in df.iterrows():
            where = f"{sheet} row {i + 2}"
            scenario = str(row["scenario_param"]).strip()
            p_name = str(row["param"]).strip()
            if scenario == self.BASE_SCENARIO:
                errors.append(f"{where}: scenario '{self.BASE_SCENARIO}' is the unmodified techmap and must not have parameter overrides")
                continue
            if p_name not in self.param_index_dict:
                errors.append(f"{where}: unknown parameter '{p_name}'")
                continue
            indexes = self.param_index_dict[p_name]
            if "T" in indexes:
                errors.append(f"{where}: time dependent parameter '{p_name}' can not be scenario dependent")
                continue
            if pd.isna(row["value"]):
                errors.append(f"{where}: no value given")
                continue

            cs_names = [row[c] for c in self.CS_COLUMNS]
            cs_id = None
            if "CS" in indexes:
                if any(pd.isna(c) for c in cs_names):
                    errors.append(f"{where}: parameter '{p_name}' requires {self.CS_COLUMNS}")
                    continue
                cs_names = [str(c).strip() for c in cs_names]
                cs_id = self._get_cs_id(*cs_names)
                if cs_id is None:
                    errors.append(f"{where}: unknown conversion subprocess {tuple(cs_names)}")
                    continue
            elif not all(pd.isna(c) for c in cs_names):
                errors.append(f"{where}: parameter '{p_name}' is not conversion subprocess dependent, leave {self.CS_COLUMNS} empty")
                continue

            y_id = None
            if "Y" in indexes:
                if pd.isna(row["year"]):
                    errors.append(f"{where}: parameter '{p_name}' requires a year")
                    continue
                y = int(row["year"])
                if y not in years:
                    logger.warning("%s: year %d is not a model year, ignoring it.", where, y)
                    continue
                y_id = years[y]
            elif not pd.isna(row["year"]):
                errors.append(f"{where}: parameter '{p_name}' is not year dependent, leave year empty")
                continue

            key = (scenario, p_name, cs_id, y_id)
            if key in seen:
                errors.append(f"{where}: duplicate entry")
                continue
            seen.add(key)
            self.cursor.execute(
                "INSERT INTO param_scenario (scenario_param, param, cs_id, y_id, value) VALUES (?,?,?,?,?);",
                (scenario, p_name, cs_id, y_id, self._scale(p_name, float(row["value"]))))
        if errors:
            raise ValueError(f"Worksheet {sheet} is invalid:\n  - " + "\n  - ".join(errors))

    def read_cs_equal(self, tmap) -> None:
        sheet = "cs_equal"
        df = pd.read_excel(tmap, sheet)
        self._check_columns(df, sheet, self.CS_COLUMNS)
        df = df.dropna(how="all", subset=self.CS_COLUMNS)
        errors = []
        for i, row in df.iterrows():
            cs_names = [str(row[c]).strip() for c in self.CS_COLUMNS]
            cs_id = self._get_cs_id(*cs_names)
            if cs_id is None:
                errors.append(f"{sheet} row {i + 2}: unknown conversion subprocess {tuple(cs_names)}")
                continue
            self.cursor.execute("INSERT INTO cs_equal (cs_id) VALUES (?) ON CONFLICT(cs_id) DO NOTHING;", (cs_id,))
        if errors:
            raise ValueError(f"Worksheet {sheet} is invalid:\n  - " + "\n  - ".join(errors))
