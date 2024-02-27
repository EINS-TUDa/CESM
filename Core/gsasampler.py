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
    
    def generate_morris_samples(self,run_date,result_path):
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
                            year_value = -1 if year_values[j+1] == 'NaN' else float(year_values[j+1])
                            cs_names = np.append(cs_names, f'{cs_name}&{col}&{year_values[j]}')
                            cs_values = np.append(cs_values, year_value)
                    else:
                        cs_names = np.append(cs_names, f'{cs_name}&{col}')
                        cs_values = np.append(cs_values, value)
                
        original_params = {}
        modified_params = {}

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
                
            original_params[cs_names[i]] = cs_values[i]
            
            if not (cs_values[i] == 0 or cs_values[i] == 1 or cs_values[i] == -1) and not(any(substring in cs_names[i] for substring in problem_params)):
                value_range = [cs_values[i]*(1-percentage_range), cs_values[i]*(1+percentage_range)]
                if is_fraction:
                    np.clip(value_range,0,1)
                modified_params[cs_names[i]] = value_range       
    
        # Define the model inputs
        problem = {
            'num_vars': len(modified_params),
            'names': list(modified_params.keys()),
            'bounds': list(modified_params.values())
        }
        try:
            objects = []
            with (open('GSAResults/var_names.pkl', "rb")) as openfile:
                while True:
                    try:
                        objects.append(pickle.load(openfile))
                    except EOFError:
                        break
            out_names = objects[0]
            problem['outputs'] = out_names
        except:
            pass

        # Generate samples
        trajectories = 1000
        optimal_trajectories = 4
        start_time = time.time()
        samples = morris_sample(problem, trajectories, optimal_trajectories=optimal_trajectories)
        sampling_time = time.time() - start_time

        base_cs = pd.read_excel(tmap,"ConversionSubProcess",  skiprows=[1, 2])
        input_dfs = []

        for i in range(len(samples)):
            new_params = original_params
            for idx, key in enumerate(modified_params):
                new_params[key] = samples[i][idx]
            mod_cs = base_cs.copy()
            last_yearly = ''
            yearly_input = []
            range_names = list(new_params.keys())
            for j in range(len(range_names)):
                split_name = range_names[j].split('&')
                is_yearly = False if len(split_name) == 4 else True
                if is_yearly:
                    if range_names[j][:-5] != last_yearly:
                        last_yearly = range_names[j][:-5]
                        value = new_params[range_names[j]] if new_params[range_names[j]] != -1 else 'NaN'
                        yearly_input = f'[{split_name[-1]} {value}'
                    else:
                        value = new_params[range_names[j]] if new_params[range_names[j]] != -1 else 'NaN'
                        yearly_input = f'{yearly_input};{split_name[-1]} {value}'
                        if j != len(range_names) - 1:
                            if range_names[j+1][:-5] != range_names[j][:-5]:
                                yearly_input = f'{yearly_input}]'
                                mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                                        (mod_cs['commodity_in']==split_name[1])&
                                        (mod_cs['commodity_out']==split_name[2]),split_name[3]] = yearly_input
                else:
                    value = new_params[range_names[j]] if new_params[range_names[j]] != -1 else 'NaN'
                    mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                            (mod_cs['commodity_in']==split_name[1])&
                            (mod_cs['commodity_out']==split_name[2]),split_name[3]] = value
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
        with open(f'{result_path}/X.pkl', 'wb') as f:
            pickle.dump(samples, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(f'{result_path}/problem_def.pkl', 'wb') as f:
            pickle.dump(problem, f, protocol=pickle.HIGHEST_PROTOCOL)
            
        return parsed_samples