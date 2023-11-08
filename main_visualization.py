"""
quickstart script for visualization
Date: 06.11.2023
"""

import Core.visualize as Visual

# load the output from the binary file saved after solving the model in main.py
input, output = Visual.read_input_output(filename="input_output.pkl")

# Plot data
cs = list(input.dataset.conversion_subprocesses)[0]
co = list(input.dataset.commodities)[0]
Visual.visualize_data("Cap_new", input, output, cs, co)