# -*- coding: utf-8 -*-
"""
Input Parsing Module

author: Sina Hajikazemi
date: 13.10.2023
"""
from pathlib import Path
import pandas as pd
import numpy as np
import scipy.interpolate
import Core.datacls as dtcls

              

class Parser:
    """
    Input Model Class
        Import techmap and timeseries
        Generates .dat input file
    """
    def __init__(self, name, techmap_dir_path, ts_dir_path, scenario):
        self.name = name
        self.techmap_path = techmap_dir_path.joinpath(f"{name}.xlsx")
        self.ts_dir_path = ts_dir_path

        self.scenario = scenario
        self.tss_name = None
        
        self.units = None
        self.datasets = {
            "Y": None,
            "T": None,
            "CS": None,
            "CP": None,
            "CO": None
        }

        # Add here if model is changed
        self.param_index_dict = {
            "dt": [], 
            "w": [],
            "discount_rate": [],
            "annual_co2_limit": ["Y"],
            "co2_price" : ["Y"],
            "opex_cost_energy": ["CS","Y"],
            "opex_cost_power" :["CS","Y"],
            "capex_cost_power":["CS","Y"], 
            "efficiency": ["CS"],
            "technical_lifetime": ["CS"],
            "cap_min":["CS", "Y"],
            "cap_max":["CS", "Y"],
            "cap_res_min":["CS", "Y"],
            "cap_res_max":["CS", "Y"],
            "availability_profile": ["CS", "T"],
            "technical_availability": ["CS"],
            "output_profile": ["CS", "T"],
            "max_eout":["CS","Y"],
            "min_eout" :["CS","Y"],
            "out_frac_min":["CS","Y"],
            "out_frac_max":["CS","Y"],
            "in_frac_min":["CS","Y"],
            "in_frac_max":["CS","Y"],
            "spec_co2": ["CS"],
            "is_storage": ["CS"], 
            "c_rate": ["CS"], 
            "efficiency_charge": ["CS"]
        }

        self.params = {name:None for name in self.param_index_dict.keys()}
        

    # @property
    # def sim_folder(self):
    #     if self.tss_name is None:
    #         raise InputProcessingError("Time step selection must be done before building simulation folder")

    #     sim_folder = os.sep.join([self.path_dir, "Runs", "%s_%s_%s"%(self.name, self.scenario, self.tss_name)])
    #     if not os.path.exists(sim_folder):
    #         os.makedirs(sim_folder)

    #     return sim_folder

    
    def parse(self):
        tmap = pd.ExcelFile(self.techmap_path)
        self.read_units(tmap)
        self.read_scenario(tmap)
        self.read_tss(tmap)
        self.read_co(tmap)
        self.read_cp(tmap)
        self.read_cs(tmap)
        
    def read_units (self, tmap) -> None:
        df = pd.read_excel(tmap,"Units")
        self.units = dtcls.Units(**dict(zip(df["quantity"].str.strip(),df["scale_factor"])))
            
    def read_cp(self,tmap) -> None:
        df = pd.read_excel(tmap,"ConversionProcess")
        self.datasets["CP"] = {dtcls.ConversionProcess(cp.strip()) for cp in df["conversion_process_name"] if not pd.isna(cp)}
        
    def read_co(self, tmap) -> None:
        df = pd.read_excel(tmap,"Commodity")
        self.datasets["CO"] = {dtcls.Commodity(co) for co in df["commodity_name"].str.strip()}
    
    def read_scenario(self, tmap):
        df = pd.read_excel(tmap,"Scenario")
        
        row_index = df.index[df["scenario_name"]==self.scenario].tolist()[0]
        # Get years set

        self.params["discount_rate"] = df["discount_rate"][row_index]
        self.datasets["Y"] = [dtcls.Year(x) for x in 
            range(
                int(df["from_year"][row_index]),
                int(df["until_year"][row_index])+1,
                int(df["year_step"][row_index])
            )
        ]
        
        self.tss_name = df["TSS"][row_index]
        
        co2_param = ["annual_co2_limit", "co2_price"]
        for pp in co2_param:
            v = df[pp][row_index]
            self.params[pp] = {}
            if not pd.isna(v):
                if '[' in v:
                    int_fun = self.get_interpolation_f(v)
                    for y in self.datasets["Y"]:
                        val = int_fun(int(y))
                        if not np.isnan(val):
                            self.params[pp][y] = int_fun(int(y))
                else:
                    for y in self.datasets["Y"]:
                        self.params[pp][dtcls.Year(y)] = v
                   
    def read_tss(self,tmap):
        df = pd.read_excel(tmap,"TSS")
        row_index = df.index[df["TSS_name"]==self.tss_name].tolist()[0]

        self.params["dt"] = df["dt"][row_index]
        tss_file_path = self.ts_dir_path.joinpath(f"{self.tss_name}.csv")
        df = pd.read_csv(tss_file_path , header=None)
        
        tss_values = df[3].values
        self.datasets["T"] = [dtcls.Time(ts) for ts in tss_values]
        self.params["w"] = (8760/len(self.datasets["T"]))/self.params["dt"]
        
    def read_cs(self, tmap):
        df = pd.read_excel(tmap,"ConversionSubProcess",  skiprows=[1, 2])
        
        # TO DO - verify the scenario of the conversion process
        self.datasets["CS"] = []
        param_names= df.columns[df.columns.to_list().index("scenario")+1:].to_list()
        for p_name in param_names:
            self.params[p_name] = {}
        for _, row in df.iterrows():
            cp = row["conversion_process_name"]
            if not pd.isna(cp):
                cin = row["commodity_in"]
                cout = row["commodity_out"]
                cs = dtcls.ConversionSubprocess(dtcls.ConversionProcess(cp),dtcls.Commodity(cin),dtcls.Commodity(cout))
                self.datasets["CS"].append(cs)
                for p_name in param_names:
                    p = row[p_name]
                    if not pd.isna(p):
                        if "T" not in self.param_index_dict[p_name]: # not time dependent
                            if "Y" in self.param_index_dict[p_name]:
                                #see if interval
                                if '[' in str(p): # inveterval given
                                    f_int = self.get_interpolation_f(p)
                                    for y in self.datasets["Y"]:
                                        key = (cs , y)
                                        val = f_int(int(y))
                                        if not np.isnan(val):                                        
                                            self.params[p_name][key] = float(f_int(int(y)))
                                else: # no interval given - constant
                                    for y in self.datasets["Y"]:
                                        key = (cs , y) 
                                        self.params[p_name][key] = p
                            else: # not dependent on the year
                                key = cs
                                self.params[p_name][key] = p
                        else: # time dependent
                            ts_file_path = self.ts_dir_path.joinpath(f"{p}.txt")
                            ts_file = open(ts_file_path)
                            ts = ts_file.read().split(" ")
                            ts = [float(x) for x in ts if x != ""]
                            ts.insert(0,0) # add to match index
                            ts = np.array(ts)
                            ts = ts[[int(x) for x in self.datasets["T"]]]
                            
                            #Potentential normalization
                            if p_name in ["output_profile"]:
                                ts = ts/sum(ts)
                            for i,t in enumerate(self.datasets["T"]):
                                key = (cs,t)
                                self.params[p_name][key] = ts[i]

    def get_interpolation_f(self, param):
        """
        Get the interpolation function for the pairs inputed in the techmap
        Pairs must be in the form: [ YYYY value ; YYYY value; ...]

        Parameters
        ----------
        param : string
           parameters to make the interpolate function.
           Must be in the form: [YYYY value ; YYYY value; ...]

        Returns
        -------
        int_f : function
            anomymus function to calculate the interpolation of a Year Y

        """
        yy = []
        vals = []
        #remove brackes
        param = param.split("[")[1].split("]")[0]
        points = param.split(";")
        for pair in points:
            pair = pair.split(" ")
            #remove aditional white spaces
            [year, val] = [x for x in pair if x != ""]
            if val != "NaN":
                yy.append(int(year))
                vals.append(float(val))
                
        if len(yy) > 1:
            f = scipy.interpolate.interp1d(yy, vals, bounds_error = False, fill_value = (vals[0], vals[-1]))
        else:
            f = lambda x: vals[0] if x == yy[0] else np.nan  
        return f
    
    def get_input(self) -> dtcls.Input:

        global_param = dtcls.GlobalParam(dt = self.params['dt'], w = self.params['w'], discount_rate=self.params['discount_rate'])

        cost_param = dtcls.CostParam(
            opex_cost_energy = self.params['opex_cost_energy'],
            opex_cost_power = self.params['opex_cost_power'],
            capex_cost_power = self.params['capex_cost_power']
        )

        co2_param = dtcls.CO2Param(
            spec_co2 = self.params['spec_co2'],
            annual_co2_limit = self.params['annual_co2_limit'],
            co2_price = self.params['co2_price']
        )

        energy_param = dtcls.EnergyParam(
            max_eout = self.params['max_eout'],
            min_eout = self.params['min_eout']
        )

        capacity_param = dtcls.CapacityParam(
            cap_min = self.params['cap_min'],
            cap_max = self.params['cap_max'], 
            cap_res_min = self.params['cap_res_min'],
            cap_res_max = self.params['cap_res_max'] 
        )

        technology_param = dtcls.TechnologyParam(
            efficiency = self.params['efficiency'],
            technical_lifetime = self.params['technical_lifetime']
        )

        availability_param = dtcls.AvailabilityParam(
            availability_factor= self.params['availability_profile'],
            technical_availability = self.params['technical_availability'],
            output_factor = self.params['output_profile']
        )

        fraction_param = dtcls.FractionParam(
            out_frac_min=self.params['out_frac_min'],
            out_frac_max=self.params['out_frac_max'],
            in_frac_min=self.params['in_frac_min'],
            in_frac_max=self.params['in_frac_max']
        )


        storage_param = dtcls.StorageParam(
            c_rate = self.params['c_rate'],
            efficiency_charge = self.params['efficiency_charge']
        )

        param = dtcls.Param(
            globalparam = global_param,
            cost = cost_param,
            co2 = co2_param,
            energy = energy_param,
            capacity = capacity_param,
            technology = technology_param,
            availability = availability_param,
            fractions = fraction_param,
            storage = storage_param,
            units = self.units
        )

        dataset = dtcls.Dataset(
            years = self.datasets["Y"],
            times = self.datasets["T"],
            commodities = self.datasets["CO"],
            conversion_processes = self.datasets["CP"],
            conversion_subprocesses= self.datasets["CS"],
            storage_cs = {cs for cs in self.params['is_storage'] if self.params['is_storage'][cs]}
        )

        input = dtcls.Input(dataset=dataset, param=param)
        return input


if __name__ == '__main__':
    techmap_dir_path = Path(".").joinpath("Data", "Techmap")
    ts_dir_path = Path(".").joinpath("Data", "TimeSeries")
    parser = Parser("DEModel",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base4twk")
    parser.parse()
    parser.get_input()