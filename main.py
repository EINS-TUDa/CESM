"""
quickstart script

Author: Sina Hajikazemi
Date: 18.10.2023
"""

from Core.inputparse import Parser
from pathlib import Path
from Core.model import Model
from Core.plotter import Plotter, PlotType 
from Core.datacls import save_input_output, read_input_output
from Core.db import generate_db_input, write_to_db

# model_name = "TestModel" # model name
model_name = "DEModel_V2" # model name

techmap_dir_path = Path(".").joinpath("Data", "Techmap") # techmap directory path
ts_dir_path = Path(".").joinpath("Data", "TimeSeries") # time series directory path
parser = Parser(model_name,techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base")
print("### parsing started ###")
parser.parse()
input = parser.get_input()
db_input = generate_db_input(input)
write_to_db(db_input)
raise Exception("stop")
print("### parsing finished ###")
print("#### building model started ###")
model = Model(input)
print("#### building model finished ###")
print("#### solving model started ###")
model.solve()
print("#### solving model finished ###")

output = model.get_output()

##### Uncomment to save the input and the output ######
print("#### saving model started ###")
save_input_output(input=input, output=output,filename="input_output.pkl")
print("#### saving model finished ###")

##### Uncomment to load input and output from an already saved model ######
input, output = read_input_output(filename="input_output.pkl")

##### Uncomment to visualize a chosen variable ######
ipt, opt = read_input_output("input_output.pkl")
plotter = Plotter(ipt, opt)
fig = plotter.plot_sankey(2020)
# fig.write_image("images/fig1.pdf")
plotter.plot_bars(PlotType.Bar.PRIMARY_ENERGY,commodity="Electricity")
plotter.plot_timeseries(PlotType.TimeSeries.POWER_CONSUMPTION, year=2020, commodity="Electricity")
