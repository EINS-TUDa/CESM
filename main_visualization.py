"""
quickstart script for visualization
Date: 06.11.2023
"""

from Core.inputparse import Parser
from pathlib import Path
from Core.model import Model
import Core.visualize as Visual


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

# load the output from the binary file saved after solving the model in main.py
output = Visual.read_output_pkl(filename="output.pkl")

# Plot data
cs = list(model.data.dataset.conversion_subprocesses)[0]
co = list(model.data.dataset.commodities)[0]
Visual.visualize_data("Total_annual_co2_emission", model, output, cs, co)