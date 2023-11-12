"""
quickstart script

Author: Sina Hajikazemi
Date: 18.10.2023
"""

from Core.inputparse import Parser
from pathlib import Path
from Core.model import Model
import Core.visualize as visual


techmap_dir_path = Path(".").joinpath("Data", "Techmap") # techmap directory path
ts_dir_path = Path(".").joinpath("Data", "TimeSeries") # time series directory path
# parser = Parser("DEModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base4twk")
parser = Parser("DEModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base")
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

output = model.get_output()

# ##### Uncomment to save the input and the output ######
print("#### saving model started ###")
save_dict = {"input":input, "output":output}
visual.save_input_output(save_dict,filename="input_output.pkl")
print("#### saving model finished ###")

# ##### Uncomment to load input and output from an already saved model ######
input, output = visual.read_input_output(filename="input_output.pkl")

# ##### Uncomment to visualize a chosen variable ######
# Choose a conversion_subprocess and a commodity
cs = list(input.dataset.conversion_subprocesses)[0]
co = list(input.dataset.commodities)[0]
# draw the bar plot
visual.visualize_data("Pin", input, output, cs, co)

