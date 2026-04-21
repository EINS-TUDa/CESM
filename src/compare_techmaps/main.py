"""
Compare two CESM techmap Excel files (v1 vs v2) and highlight differences.

Usage:
    python main.py

Place exactly one Excel techmap (.xlsx) in each of the v1/ and v2/ subdirectories.
The two files are compared regardless of their filenames.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SHEET_NAMES = [
    "Units",
    "Scenario",
    "TSS",
    "Commodity",
    "ConversionProcess",
    "ConversionSubProcess",
]

# Composite key that uniquely identifies a ConversionSubProcess row
CSP_KEY_COLS = [
    "conversion_process_name",
    "commodity_in",
    "commodity_out",
    "scenario",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SheetDiff:
    """Holds the comparison result for a single worksheet."""
    sheet_name: str
    added_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    removed_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    changed_cells: pd.DataFrame = field(default_factory=pd.DataFrame)
    # columns only in one version
    cols_only_v1: list[str] = field(default_factory=list)
    cols_only_v2: list[str] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return (
            len(self.added_rows) > 0
            or len(self.removed_rows) > 0
            or len(self.changed_cells) > 0
            or len(self.cols_only_v1) > 0
            or len(self.cols_only_v2) > 0
        )


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_techmap_pair(v1_dir: Path, v2_dir: Path) -> tuple[Path, Path]:
    """Return the single .xlsx techmap file from each directory.

    Each directory must contain exactly one ``.xlsx`` file (temporary
    files starting with ``~$`` are ignored).
    """
    def _single_xlsx(directory: Path) -> Path:
        candidates = [
            f for f in directory.glob("*.xlsx")
            if not f.name.startswith("~$")
        ]
        if len(candidates) == 0:
            print(f"ERROR: No .xlsx file found in {directory}")
            sys.exit(1)
        if len(candidates) > 1:
            print(f"ERROR: Multiple .xlsx files found in {directory}:")
            for c in candidates:
                print(f"  - {c.name}")
            print("Each directory must contain exactly one techmap.")
            sys.exit(1)
        return candidates[0]

    return _single_xlsx(v1_dir), _single_xlsx(v2_dir)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_techmap(path: Path) -> dict[str, pd.DataFrame]:
    """Load all relevant sheets from a techmap Excel file."""
    xl = pd.ExcelFile(path)
    sheets: dict[str, pd.DataFrame] = {}
    for name in SHEET_NAMES:
        if name in xl.sheet_names:
            df = pd.read_excel(xl, name)
            # Drop completely empty rows (separators in the Excel)
            df = df.dropna(how="all").reset_index(drop=True)
            sheets[name] = df
        else:
            print(f"  WARNING: Sheet '{name}' not found in {path.name}")
    return sheets


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _values_equal(a, b) -> bool:
    """Compare two scalar values, treating NaN == NaN as True."""
    if isinstance(a, float) and isinstance(b, float):
        if np.isnan(a) and np.isnan(b):
            return True
        return np.isclose(a, b, rtol=1e-9, atol=1e-12)
    return a == b


def _make_key(row: pd.Series, key_cols: list[str]) -> str:
    """Build a string key from the given columns of a row."""
    parts = []
    for c in key_cols:
        val = row.get(c, "")
        parts.append("" if pd.isna(val) else str(val))
    return " | ".join(parts)


def compare_generic_sheet(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    sheet_name: str,
) -> SheetDiff:
    """Compare two DataFrames row-by-row (positional) for simple sheets."""
    diff = SheetDiff(sheet_name=sheet_name)

    # Column differences
    cols1, cols2 = set(df1.columns), set(df2.columns)
    diff.cols_only_v1 = sorted(cols1 - cols2)
    diff.cols_only_v2 = sorted(cols2 - cols1)

    common_cols = sorted(cols1 & cols2, key=lambda c: list(df1.columns).index(c))

    # Align lengths
    max_len = max(len(df1), len(df2))
    if len(df1) < max_len:
        diff.added_rows = df2.iloc[len(df1):].copy()
    elif len(df2) < max_len:
        diff.removed_rows = df1.iloc[len(df2):].copy()

    # Cell-level comparison for overlapping rows
    min_len = min(len(df1), len(df2))
    changes = []
    for col in common_cols:
        for i in range(min_len):
            v1, v2 = df1[col].iloc[i], df2[col].iloc[i]
            if not _values_equal(v1, v2):
                changes.append({
                    "row": i,
                    "column": col,
                    "v1": v1,
                    "v2": v2,
                })
    if changes:
        diff.changed_cells = pd.DataFrame(changes)

    return diff


def compare_by_key(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    sheet_name: str,
    key_cols: list[str],
) -> SheetDiff:
    """Key-based comparison: rows are matched by *key_cols*, order is ignored.

    Parameters that differ between matched rows are reported individually.
    Rows present only in one version are reported as added / removed.
    """
    diff = SheetDiff(sheet_name=sheet_name)

    # Column differences
    cols1, cols2 = set(df1.columns), set(df2.columns)
    diff.cols_only_v1 = sorted(cols1 - cols2)
    diff.cols_only_v2 = sorted(cols2 - cols1)

    common_cols = [c for c in df1.columns if c in cols2]
    param_cols = [c for c in common_cols if c not in key_cols]

    df1 = df1.copy()
    df2 = df2.copy()
    df1["_key"] = df1.apply(lambda r: _make_key(r, key_cols), axis=1)
    df2["_key"] = df2.apply(lambda r: _make_key(r, key_cols), axis=1)

    keys1 = set(df1["_key"])
    keys2 = set(df2["_key"])

    # Rows only in v2 (added)
    added_keys = keys2 - keys1
    if added_keys:
        diff.added_rows = df2[df2["_key"].isin(added_keys)].drop(columns=["_key"])

    # Rows only in v1 (removed)
    removed_keys = keys1 - keys2
    if removed_keys:
        diff.removed_rows = df1[df1["_key"].isin(removed_keys)].drop(columns=["_key"])

    # Changed rows (common keys) – compare every parameter column
    if not param_cols:
        return diff

    common_keys = keys1 & keys2
    changes = []
    df1_indexed = df1.set_index("_key")
    df2_indexed = df2.set_index("_key")

    for key in sorted(common_keys):
        row1 = df1_indexed.loc[key]
        row2 = df2_indexed.loc[key]
        # Handle duplicate keys (take first occurrence)
        if isinstance(row1, pd.DataFrame):
            row1 = row1.iloc[0]
        if isinstance(row2, pd.DataFrame):
            row2 = row2.iloc[0]

        for col in param_cols:
            v1 = row1.get(col)
            v2 = row2.get(col)
            if not _values_equal(v1, v2):
                entry: dict = {}
                for kc in key_cols:
                    entry[kc] = row1.get(kc, "")
                entry["parameter"] = col
                entry["v1"] = v1
                entry["v2"] = v2
                changes.append(entry)

    if changes:
        diff.changed_cells = pd.DataFrame(changes)

    return diff


# ---------------------------------------------------------------------------
# Reporting – Console
# ---------------------------------------------------------------------------

def print_sheet_diff(diff: SheetDiff) -> None:
    """Print a human-readable summary of a SheetDiff to the console."""
    if not diff.has_differences:
        print(f"  ✓ {diff.sheet_name}: identical")
        return

    print(f"\n  ✗ {diff.sheet_name}:")

    if diff.cols_only_v1:
        print(f"    Columns only in v1: {diff.cols_only_v1}")
    if diff.cols_only_v2:
        print(f"    Columns only in v2: {diff.cols_only_v2}")

    if len(diff.added_rows) > 0:
        print(f"    Added rows (only in v2): {len(diff.added_rows)}")
    if len(diff.removed_rows) > 0:
        print(f"    Removed rows (only in v1): {len(diff.removed_rows)}")
    if len(diff.changed_cells) > 0:
        print(f"    Changed values: {len(diff.changed_cells)}")
        # Show first few changes
        preview = diff.changed_cells.head(20)
        print(preview.to_string(index=False))
        if len(diff.changed_cells) > 20:
            print(f"    ... and {len(diff.changed_cells) - 20} more changes")


# ---------------------------------------------------------------------------
# Reporting – HTML
# ---------------------------------------------------------------------------

def _html_escape(val) -> str:
    if pd.isna(val):
        return '<span class="na">NaN</span>'
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_html_report(
    pair_name: str,
    diffs: dict[str, SheetDiff],
    output_path: Path,
) -> None:
    """Generate an HTML report highlighting all differences."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head><meta charset='utf-8'>",
        f"<title>Techmap Comparison – {pair_name}</title>",
        "<style>",
        "  body { font-family: 'Segoe UI', Arial, sans-serif; margin: 2em; background: #fafafa; }",
        "  h1 { color: #333; }",
        "  h2 { color: #555; border-bottom: 2px solid #ddd; padding-bottom: .3em; margin-top: 2em; }",
        "  .identical { color: #2a2; }",
        "  .different { color: #c22; }",
        "  table { border-collapse: collapse; margin: 1em 0; font-size: 0.9em; }",
        "  th, td { border: 1px solid #ccc; padding: 4px 10px; text-align: left; }",
        "  th { background: #eee; position: sticky; top: 0; }",
        "  .added { background: #d4edda; }",
        "  .removed { background: #f8d7da; }",
        "  .changed-v1 { background: #fff3cd; }",
        "  .changed-v2 { background: #cce5ff; }",
        "  .na { color: #999; font-style: italic; }",
        "  .summary { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 1em; margin: 1em 0; }",
        "  .arrow { color: #888; }",
        "</style>",
        "</head><body>",
        f"<h1>Techmap Comparison: {pair_name}</h1>",
    ]

    # Summary
    html_parts.append('<div class="summary"><h3>Summary</h3><ul>')
    for sheet_name in SHEET_NAMES:
        diff = diffs.get(sheet_name)
        if diff is None:
            html_parts.append(f'<li>{sheet_name}: <em>sheet missing in one version</em></li>')
        elif not diff.has_differences:
            html_parts.append(f'<li class="identical">✓ {sheet_name}: identical</li>')
        else:
            parts = []
            if len(diff.added_rows) > 0:
                parts.append(f"{len(diff.added_rows)} added")
            if len(diff.removed_rows) > 0:
                parts.append(f"{len(diff.removed_rows)} removed")
            if len(diff.changed_cells) > 0:
                parts.append(f"{len(diff.changed_cells)} changed values")
            if diff.cols_only_v1:
                parts.append(f"cols only v1: {diff.cols_only_v1}")
            if diff.cols_only_v2:
                parts.append(f"cols only v2: {diff.cols_only_v2}")
            html_parts.append(f'<li class="different">✗ {sheet_name}: {", ".join(parts)}</li>')
    html_parts.append('</ul></div>')

    # Detail sections per sheet
    for sheet_name in SHEET_NAMES:
        diff = diffs.get(sheet_name)
        if diff is None or not diff.has_differences:
            continue

        html_parts.append(f'<h2>{sheet_name}</h2>')

        # Column differences
        if diff.cols_only_v1:
            html_parts.append(f'<p><strong>Columns only in v1:</strong> {", ".join(diff.cols_only_v1)}</p>')
        if diff.cols_only_v2:
            html_parts.append(f'<p><strong>Columns only in v2:</strong> {", ".join(diff.cols_only_v2)}</p>')

        # Added rows
        if len(diff.added_rows) > 0:
            html_parts.append('<h3>Added rows (only in v2)</h3>')
            html_parts.append(_df_to_html_table(diff.added_rows, row_class="added"))

        # Removed rows
        if len(diff.removed_rows) > 0:
            html_parts.append('<h3>Removed rows (only in v1)</h3>')
            html_parts.append(_df_to_html_table(diff.removed_rows, row_class="removed"))

        # Changed values
        if len(diff.changed_cells) > 0:
            html_parts.append('<h3>Changed values</h3>')
            html_parts.append(_changed_cells_to_html(diff.changed_cells))

    html_parts.append("</body></html>")

    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"\n  HTML report written to: {output_path}")


def _df_to_html_table(df: pd.DataFrame, row_class: str = "") -> str:
    """Convert a DataFrame to an HTML table string."""
    cls = f' class="{row_class}"' if row_class else ""
    lines = ["<table>", "<tr>"]
    for col in df.columns:
        lines.append(f"  <th>{_html_escape(col)}</th>")
    lines.append("</tr>")
    for _, row in df.iterrows():
        lines.append(f"<tr{cls}>")
        for col in df.columns:
            lines.append(f"  <td>{_html_escape(row[col])}</td>")
        lines.append("</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _changed_cells_to_html(df: pd.DataFrame) -> str:
    """Render the changed-cells DataFrame as an HTML table with v1→v2 highlighting."""
    lines = ["<table>", "<tr>"]
    for col in df.columns:
        lines.append(f"  <th>{_html_escape(col)}</th>")
    lines.append("</tr>")

    for _, row in df.iterrows():
        lines.append("<tr>")
        for col in df.columns:
            val = row[col]
            if col == "v1":
                lines.append(f'  <td class="changed-v1">{_html_escape(val)}</td>')
            elif col == "v2":
                lines.append(f'  <td class="changed-v2">{_html_escape(val)}</td>')
            else:
                lines.append(f"  <td>{_html_escape(val)}</td>")
        lines.append("</tr>")

    lines.append("</table>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Key columns used for matching rows in each sheet (order-independent).
# Sheets not listed here fall back to positional (row-by-row) comparison.
SHEET_KEY_COLS: dict[str, list[str]] = {
    "Commodity":            ["commodity_name"],
    "ConversionProcess":    ["conversion_process_name"],
    "ConversionSubProcess": CSP_KEY_COLS,
}


def main() -> None:
    # Look for v1/ and v2/ next to this file first, then in common locations
    base_dir = Path(__file__).parent
    if not (base_dir / "v1").is_dir():
        base_dir = Path.cwd() / "CESM" / "compare_techmaps"
    if not (base_dir / "v1").is_dir():
        base_dir = Path.cwd() / "compare_techmaps"
    if not (base_dir / "v1").is_dir():
        base_dir = Path.cwd()

    v1_dir = base_dir / "v1"
    v2_dir = base_dir / "v2"

    if not v1_dir.is_dir() or not v2_dir.is_dir():
        print("ERROR: Could not find v1/ and v2/ directories.")
        print("       Run this command from the project root, from CESM/, or from CESM/compare_techmaps/.")
        sys.exit(1)

    path_v1, path_v2 = find_techmap_pair(v1_dir, v2_dir)

    pair_name = f"{path_v1.name}  ↔  {path_v2.name}"
    print("=" * 70)
    print(f"Comparing: {pair_name}")
    print("=" * 70)

    sheets_v1 = load_techmap(path_v1)
    sheets_v2 = load_techmap(path_v2)

    diffs: dict[str, SheetDiff] = {}

    for sheet_name in SHEET_NAMES:
        df1 = sheets_v1.get(sheet_name)
        df2 = sheets_v2.get(sheet_name)

        if df1 is None or df2 is None:
            if df1 is None and df2 is None:
                continue
            d = SheetDiff(sheet_name=sheet_name)
            if df1 is None:
                d.added_rows = df2
            else:
                d.removed_rows = df1
            diffs[sheet_name] = d
            print_sheet_diff(d)
            continue

        if sheet_name in SHEET_KEY_COLS:
            d = compare_by_key(df1, df2, sheet_name, SHEET_KEY_COLS[sheet_name])
        else:
            d = compare_generic_sheet(df1, df2, sheet_name)

        diffs[sheet_name] = d
        print_sheet_diff(d)

    # Generate HTML report
    safe_name = path_v2.stem
    report_path = base_dir / f"comparison_{safe_name}.html"
    generate_html_report(pair_name, diffs, report_path)

def compare_techmaps(
    path_v1: Path | str,
    path_v2: Path | str,
    path_output: Path | str,
) -> dict[str, SheetDiff]:
    """Compare two techmap Excel files and write an HTML report.

    Parameters
    ----------
    path_v1:     Path to the v1 techmap .xlsx file.
    path_v2:     Path to the v2 techmap .xlsx file.
    path_output: Path for the generated HTML report.

    Returns
    -------
    Dictionary mapping sheet names to their :class:`SheetDiff` results.
    """
    path_v1 = Path(path_v1)
    path_v2 = Path(path_v2)
    path_output = Path(path_output)

    pair_name = f"{path_v1.name}  ↔  {path_v2.name}"
    print("=" * 70)
    print(f"Comparing: {pair_name}")
    print("=" * 70)

    sheets_v1 = load_techmap(path_v1)
    sheets_v2 = load_techmap(path_v2)

    diffs: dict[str, SheetDiff] = {}

    for sheet_name in SHEET_NAMES:
        df1 = sheets_v1.get(sheet_name)
        df2 = sheets_v2.get(sheet_name)

        if df1 is None or df2 is None:
            if df1 is None and df2 is None:
                continue
            d = SheetDiff(sheet_name=sheet_name)
            if df1 is None:
                d.added_rows = df2
            else:
                d.removed_rows = df1
            diffs[sheet_name] = d
            print_sheet_diff(d)
            continue

        if sheet_name in SHEET_KEY_COLS:
            d = compare_by_key(df1, df2, sheet_name, SHEET_KEY_COLS[sheet_name])
        else:
            d = compare_generic_sheet(df1, df2, sheet_name)

        diffs[sheet_name] = d
        print_sheet_diff(d)

    generate_html_report(pair_name, diffs, path_output)
    return diffs


if __name__ == "__main__":
    main()
