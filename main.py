"""
quickstart script

Author: Sina Hajikazemi
Date: 18.10.2023
"""

from Core.inputparse import Parser
from pathlib import Path
from Core.model import Model


techmap_dir_path = Path(".").joinpath("Data", "Techmap") # techmap directory path
ts_dir_path = Path(".").joinpath("Data", "TimeSeries") # time series directory path
# parser = Parser("DEModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base4twk")
parser = Parser("TestModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base")
print("### parsing started ###")
parser.parse()
input = parser.get_input()
print("### parsing finished ###")
print("#### building model started ###")
model = Model(input)
print("#### building model finished ###")
print("#### solving model started ###")
model.solve()
print("#### solving model finished ###")
cs = list(input.dataset.conversion_subprocesses)[0]
y = input.dataset.years[0]
print(cs)
print(y)
print(model.vars["Cap_new"][cs,y].X)