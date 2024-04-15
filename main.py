"""
quickstart script

Author: Sina Hajikazemi
Date: 18.10.2023
"""

from Core.input_parser import Parser
from pathlib import Path
from Core.model import Model
from Core.plotter import Plotter, PlotType
from Core.data_access import DAO
import sqlite3


model_name = "DEModel_V2" # model name

techmap_dir_path = Path(".").joinpath("Data", "Techmap")
ts_dir_path = Path(".").joinpath("Data", "TimeSeries")
db_dir_path = Path(".").joinpath("Runs", "DEModel_V2-Base")
file_path = Path(".").joinpath("Runs", "DEModel_V2-Base", "db.sqlite")
if file_path.exists():
    # Delete the file using unlink()
    file_path.unlink()
    print("File deleted successfully:", file_path)
else:
    print("File does not exist:", file_path)

db_path = db_dir_path.joinpath("db.sqlite")
conn = sqlite3.connect(":memory:")
parser = Parser("DEModel_V2",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,db_conn=conn ,scenario = "Base")
print("### parsing started ###")
parser.parse()
print("### parsing finished ###")


print("#### building model started ###")
model = Model(conn)
model.model.write("primal.lp")
print("#### building model finished ###")

# raise ValueError("stop")
print("#### solving model started ###")
model.solve()
print("#### solving model finished ###")

print("#### saving model started ###")
model.save_output()
print("#### saving model finished ###")


##### Visualization ######
dao = DAO(conn) # data access object
plotter = Plotter(dao=dao)
# # fig.write_image("images/fig1.pdf")
plotter.plot_bars(PlotType.Bar.PRIMARY_ENERGY,commodity="Electricity")
plotter.plot_timeseries(PlotType.TimeSeries.POWER_CONSUMPTION, year=2020, commodity="Electricity")
conn_file= sqlite3.connect(db_path)
conn.backup(conn_file)