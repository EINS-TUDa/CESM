"""
quickstart script

Author: Sina Hajikazemi
Date: 18.10.2023
"""

from Core.inputparse import Parser
from pathlib import Path
from Core.model import Model
import pickle


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

# get and sava model output in a binay file
output = model.get_output()
with open("output.pkl", "wb") as f:
    pickle.dump(output,f)

# load tha outpout from the binary file
with open("output.pkl", "rb") as f:
    output = pickle.load(f)

print("#### solving model finished ###")
cs = list(input.dataset.conversion_subprocesses)[0]
y = input.dataset.years[0]
print(cs)
print(y)
print(model.vars["Cap_new"][cs,y].X)