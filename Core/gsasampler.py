import re
import os
import pickle
import time
import numpy as np
import pandas as pd
from pathlib import Path
from Core.inputparse import Parser
from SALib.sample.morris import sample as morris_sample

class GSASampler:
    """
    GSA Sampler Model Class
        Generates samples for GSA
        from given techmap file
    """
    def __init__(self, model_name, techmap_dir_path, ts_dir_path, scenario):
        self.model_name = model_name
        self.techmap_dir_path = techmap_dir_path
        self.techmap_path = techmap_dir_path.joinpath(f"{model_name}.xlsx")
        self.ts_dir_path = ts_dir_path
        self.scenario = scenario
    
    def generate_morris_samples(self,run_date):
        tmap = pd.ExcelFile(self.techmap_path)
        df = pd.read_excel(tmap,"ConversionSubProcess",skiprows=[1,2]).drop(columns=['is_storage', 'efficiency', 'technical_availability', 'output_profile', 'availability_profile'])

        cs_names = np.array([])
        cs_values = np.array([])
        pattern = re.compile(r'\s*;\s*|\s+')
        for i in range(len(df)):
            if df.iloc[i]["conversion_process_name"] == 'DEBUG':
                break
            else:
                if type(df.iloc[i]['conversion_process_name']) != str:
                    continue
                cs = df.iloc[i].dropna()
                cs_name = f'{cs["conversion_process_name"]}&{cs["commodity_in"]}&{cs["commodity_out"]}'
                remaining_columns = cs.index
                for col in remaining_columns[4:]:
                    value = cs[col]
                    if type(value) == str:
                        year_values = pattern.split(value[1:-1])
                        for j in range(0, len(year_values), 2):
                            year_value = 0 if year_values[j+1] == 'NaN' else float(year_values[j+1])
                            cs_names = np.append(cs_names, f'{cs_name}&{col}&{year_values[j]}')
                            cs_values = np.append(cs_values, year_value)
                    else:
                        cs_names = np.append(cs_names, f'{cs_name}&{col}')
                        cs_values = np.append(cs_values, value)
                
        fixed_yearly_values = np.array([])
        fixed_yearly_names = np.array([])
        fixed_values = np.array([])
        fixed_names = np.array([])
        range_values = np.empty((0,2), dtype=float)
        range_names = np.array([])

        # TODO revise these definitions
        fraction_params = ['efficiency_charge', 'out_frac_min', 'out_frac_max', 'in_frac_min', 'in_frac_max']
        params_5_percent = ['efficiency_charge', 'c_rate', 'technical_lifetime']
        params_10_percent = ['spec_co2', 'opex_cost_power', 'max_eout', 'min_eout']
        params_20_percent = ['opex_cost_energy', 'capex_cost_power']
        problem_params = ['cap_res_max', 'cap_res_min', 'cap_min', 'cap_max']
        for i in range(len(cs_names)):
            if any(substring in cs_names[i] for substring in params_20_percent):
                percentage_range = 0.2
            elif any(substring in cs_names[i] for substring in params_5_percent):
                percentage_range = 0.05
            else:
                percentage_range = 0.1
            is_fraction = True if any(substring in cs_names[i] for substring in fraction_params) else False
                
            # TODO remove second condition after determining infeasible variables
            # Only the problem_params are resulting in infeasibility (398 samples with and 298 without them for opt_t 2)
            if (cs_values[i] == 0 or cs_values[i] == 1):# or any(substring in cs_names[i] for substring in problem_params):
                split_name = cs_names[i].split('&')
                is_yearly = False if len(split_name) == 4 else True
                if is_yearly:
                    fixed_yearly_names = np.append(fixed_yearly_names, cs_names[i])
                    fixed_yearly_values = np.append(fixed_yearly_values, cs_values[i])
                else:
                    fixed_names = np.append(fixed_names, cs_names[i])
                    fixed_values = np.append(fixed_values, cs_values[i])
            else:
                value_range = [cs_values[i]*(1-percentage_range), cs_values[i]*(1+percentage_range)]
                if is_fraction:
                    if value_range[0] < 0:
                        value_range -= value_range[0]
                    elif value_range[1] > 1:
                        value_range -= (value_range[1] - 1)
                range_names = np.append(range_names, cs_names[i])
                range_values = np.vstack((range_values, value_range))
                
    
        # Define the model inputs
        
        try:
            objects = []
            with (open('GSAResults/var_names.pkl', "rb")) as openfile:
                while True:
                    try:
                        objects.append(pickle.load(openfile))
                    except EOFError:
                        break
            out_names = objects[0]
            problem = {
                'num_vars': len(range_names),
                'names': range_names.tolist(),
                'bounds': range_values.tolist(),
                'outputs': out_names
            }
        except:
            problem = {
                'num_vars': len(range_names),
                'names': range_names.tolist(),
                'bounds': range_values.tolist()
            }
        

        # Generate samples
        trajectories = 100
        optimal_trajectories = 2#4
        start_time = time.time()
        samples = morris_sample(problem, trajectories, optimal_trajectories=optimal_trajectories)
        sampling_time = time.time() - start_time

        base_cs = pd.read_excel(tmap,"ConversionSubProcess",  skiprows=[1, 2])
        input_dfs = []

        for i in range(len(samples)):
            mod_cs = base_cs.copy()
            last_yearly = ''
            yearly_input = []
            for j in range(len(range_names)):
                split_name = range_names[j].split('&')
                is_yearly = False if len(split_name) == 4 else True
                if is_yearly:
                    if range_names[j][:-5] != last_yearly:
                        last_yearly = range_names[j][:-5]
                        yearly_input = f'[{split_name[-1]} {samples[i][j]}'
                    else:
                        yearly_input = f'{yearly_input};{split_name[-1]} {samples[i][j]}'
                        if j != len(range_names) - 1:
                            if range_names[j+1][:-5] != range_names[j][:-5]:
                                yearly_input = f'{yearly_input}]'
                                mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                                        (mod_cs['commodity_in']==split_name[1])&
                                        (mod_cs['commodity_out']==split_name[2]),split_name[3]] = yearly_input
                else:
                    mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                            (mod_cs['commodity_in']==split_name[1])&
                            (mod_cs['commodity_out']==split_name[2]),split_name[3]] = samples[i][j]
            last_yearly = ''
            for j in range(len(fixed_yearly_names)):
                split_name = fixed_yearly_names[j].split('&')
                if fixed_yearly_names[j][:-5] != last_yearly:
                    last_yearly = fixed_yearly_names[j][:-5]
                    yearly_input = f';{split_name[-1]} {fixed_yearly_values[j]}'
                else:
                    yearly_input = f'{yearly_input};{split_name[-1]} {fixed_yearly_values[j]}'
                    if j != len(fixed_yearly_names) - 1:
                        if fixed_yearly_names[j+1][:-5] != fixed_yearly_names[j][:-5]:
                            yearly_input = f'{yearly_input}]'
                            current_input = mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                                                       (mod_cs['commodity_in']==split_name[1])&
                                                       (mod_cs['commodity_out']==split_name[2]),split_name[3]]
                            mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                                    (mod_cs['commodity_in']==split_name[1])&
                                    (mod_cs['commodity_out']==split_name[2]),split_name[3]] = current_input[:-1]+yearly_input
            input_dfs.append(mod_cs)
            
        parser = Parser(self.model_name, techmap_dir_path=self.techmap_dir_path, ts_dir_path=self.ts_dir_path, scenario=self.scenario)
        parsed_samples = []
        for idf in input_dfs:
            parser.parse(idf)
            parsed_samples.append(parser.get_input())
            
        with open(f'GSASamples/morris_{len(parsed_samples)}-samples_{int(np.ceil(sampling_time))}s_{run_date}.pkl', 'wb') as f:
            pickle.dump(parsed_samples, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(f'GSASamples/dfs_{len(parsed_samples)}.pkl', 'wb') as f:
            pickle.dump(input_dfs, f, protocol=pickle.HIGHEST_PROTOCOL)
            
        return parsed_samples