#import local files
from Core.model import Model
from Core.datacls import Input, Output, ConversionSubprocess, Commodity, Year, Time

#import libraries
import matplotlib.pyplot as plt
import pandas as pd
import pickle

def save_input_output(save_dict: dict, filename):
    """
    Save the input and output of the model in a .pkl file.

    Args:
        save_dict: {"input":input, "output":output} dictionary from the Model
        filename: name of the file as string
    Return: binary pkl.file with values of output of the model
    """
    filename = ".\Output\\" + filename
    with open(filename, "wb") as f:
        pickle.dump(save_dict,f)

def read_input_output(filename):
    """
    Read the output of the model from a .pkl file.

    Args:
        filename: filename of saved output

    Return: 
        output: output from the Model as in the Output dataclass
    """
    filename = ".\Output\\" + filename
    with open(filename, "rb") as f:
        save_dict = pickle.load(f)
    input = save_dict["input"]
    output = save_dict["output"]
    return input, output

def visualize_data(var, input:Input, output: Output, cs: ConversionSubprocess, co:Commodity):
    """
    Visualizes the data gained by the system model

    Args:
        var: variable chosen for visualization, it should be part of the model.vars
        model: the model used to calculate the output
        Output: the output of the system model as an Output dataclass
        cs: ConversionSubprocess chosen for visualization
        co: Commodity chosen for visualization
    """
    plot_data = []
    plot_years = [int(y) for y in input.dataset.years]
    plot_times = [repr(y) + ":" + repr(t) for t in input.dataset.times for y in input.dataset.years]
    if co in list(input.dataset.commodities):
        if cs in list(input.dataset.conversion_subprocesses):
            #CO2 Output
            if var == "Total_annual_co2_emission":
                for y in input.dataset.years:
                    plot_data.append(output.co2.Total_annual_co2_emission[y])
                output_title = var
            #Power Output
            elif var == "Cap_new":
                for y in input.dataset.years:
                    plot_data.append(output.power.Cap_new[(cs,y)])
                output_title = var + ", " + str(cs)
            elif var == "Cap_active":
                for y in input.dataset.years:
                    plot_data.append(output.power.Cap_active[(cs,y)])
                output_title = var + ", " + str(cs)
            elif var == "Cap_res":
                for y in input.dataset.years:
                    plot_data.append(output.power.Cap_res[(cs,y)])
                output_title = var + ", " + str(cs)
            elif var == "Pin":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.power.Pin[(cs,y,t)])
                output_title = var + ", " + str(cs)
            elif var == "Pout":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.power.Pout[(cs,y,t)])
                output_title = var + ", " + str(cs)
            #Energy Output
            elif var == "Eouttot":
                for y in input.dataset.years:
                    plot_data.append(output.energy.Eouttot[(cs,y)])
                output_title = var + ", " + str(cs)
            elif var == "Eintot":
                for y in input.dataset.years:
                    plot_data.append(output.energy.Eintot[(cs,y)])
                output_title = var + ", " + str(cs)
            elif var == "Eouttime":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.energy.Eouttime[(cs,y,t)])
                output_title = var + ", " + str(cs)
            elif var == "Eintime":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.energy.Eintime[(cs,y,t)])
                output_title = var + ", " + str(cs)
            elif var == "Enetgen":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.energy.Enetgen[(co,y,t)])
                output_title = var + ", " + repr(co)
            elif var == "Enetcons":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.energy.Enetcons[(co,y,t)])
                output_title = var + ", " + repr(co)
            #Storage Output
            elif var == "E_storage_level":
                for y in input.dataset.years:
                    for t in input.dataset.times:
                        plot_data.append(output.storage.E_storage_level[(cs,y,t)])
                output_title = var + ", " + str(cs)
            elif var == "E_storage_level_max":
                for y in input.dataset.years:
                    plot_data.append(output.storage.E_storage_level_max[(cs,y)])
                output_title = var + ", " + str(cs)
            else:
                print("The chosen variable " + var + " is not implemented!")
            
            #Plot data
            fig, ax = plt.subplots()

            if var in ["Pin", "Pout", "Eouttime", "Eintime", "Enetgen", "Enetcons"]:
                ax.bar(plot_times,plot_data, label=plot_times)
            else:
                ax.bar(plot_years,plot_data, label=plot_years)

            ax.set_title("Output: " + output_title)
            ax.set_ylabel(var)
            plt.show()
        else:
            print("The chosen conversion_subprocess is not implemented in the model!")
    else: 
        print("The chosen commodity is not implemented in the model!")