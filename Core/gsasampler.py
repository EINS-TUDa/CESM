import re
import os
import pickle
import time
import numpy as np
import pandas as pd
from pathlib import Path
from Core.inputparse import Parser
from SALib.sample.morris import sample as morris_sample
from SALib.sample.sobol import sample as saltelli_sample

class GSASampler:
    """
    GSA Sampler Model Class
        Generates samples for GSA
        from given techmap file
    """
    def __init__(self, model_name, techmap_dir_path, ts_dir_path, scenario):
        """Initialize class
    
        Args:
            model_name (str): Name of the model
            techmap_dir_path (str): Path to the directory containing techmap files
            ts_dir_path (str): Path to the directory containing time series files
            scenario (str): Name of the selected scenario
        """
        self.model_name = model_name
        self.techmap_dir_path = techmap_dir_path
        self.techmap_path = techmap_dir_path.joinpath(f"{model_name}.xlsx")
        self.ts_dir_path = ts_dir_path
        self.scenario = scenario
    
    def generate_samples(self,mode,run_date,result_path,trajectories=1000,optimal_t=4):
        """Generate samples for the simulations
    
        Args:
            mode (str): 'morris' or 'sobol'
            run_date (str): Date of the current run in format dd-mm-yy_HH-MM
            result_path (str): Path where the results will be saved
            trajectories (int): Number of trajectories for Morris (Default: 1000)
            optimal_t (int): Number of optimal trajectories for Morris (Default: 4)
    
        Returns:
            list: List of lists containing each parsed sample set
        """
        # Get full list of conversion subprocesses params used in the model
        tmap, cs_names, cs_values = self.get_conversion_subprocesses()
        # Get the ranges for the sampling of the selected params
        original_params, modified_params = self.get_param_ranges(mode,cs_names,cs_values,result_path) 
    
        # Define the model inputs
        problem = {
            'num_vars': len(modified_params),
            'names': list(modified_params.keys()),
            'bounds': list(modified_params.values())
        }
        try:
            # Add the name of the outputs if the file is available
            problem['outputs'] = self.read_pkl('GSAResults/var_names.pkl')
        except:
            pass

        # Generate samples
        start_time = time.time()
        if mode == 'morris':
            samples = morris_sample(problem, trajectories, optimal_trajectories=optimal_t)
        elif mode == 'sobol':
            N = self.get_next_pow(len(modified_params))
            samples = saltelli_sample(problem, N)
        else:
            samples = []
        sampling_time = time.time() - start_time

        # Generate dataframes for each sample
        input_dfs = self.generate_input_dfs(tmap,samples,original_params,modified_params)
        # Parse the dataframes into the model's input format
        parsed_samples = self.parse_samples(input_dfs)
            
        # Write samples and problems to .pkl files
        self.write_pkl(f'GSASamples/{mode}_{len(parsed_samples)}-samples_{int(np.ceil(sampling_time))}s_{run_date}.pkl', parsed_samples)
        self.write_pkl(f'{result_path}/{mode}_X.pkl', samples)
        self.write_pkl(f'{result_path}/{mode}_problem_def.pkl', problem)
            
        return parsed_samples
    
    def get_conversion_subprocesses(self):
        """Get list of existent subprocesses
    
        Returns:
            tmap (obj): Pandas instance of techmap file
            cs_names (list): List of input param names
            cs_values (list): List of values for each input param
        """
        # Read model's techmap from the corresponding Excel file
        tmap = pd.ExcelFile(self.techmap_path)
        df = pd.read_excel(tmap,"ConversionSubProcess",skiprows=[1,2]).drop(columns=['is_storage', 'efficiency', 'technical_availability', 'output_profile', 'availability_profile'])

        cs_names = np.array([])
        cs_values = np.array([])
        # Pattern for splitting multiyear input
        pattern = re.compile(r'\s*;\s*|\s+')
        for i in range(len(df)):
            if df.iloc[i]["conversion_process_name"] == 'DEBUG':
                # Stop the iterations if reach the DEBUG params (last ones of the techmap)
                break
            else:
                if type(df.iloc[i]['conversion_process_name']) != str:
                    # Possible case of blank lines, skip to next iteration
                    continue
                # Remove NaN values from the Subprocess line
                cs = df.iloc[i].dropna()
                # Create Subprocess name by concatenating components
                cs_name = f'{cs["conversion_process_name"]}&{cs["commodity_in"]}&{cs["commodity_out"]}'
                # Iterate over non-NaN values of CS
                remaining_columns = cs.index
                for col in remaining_columns[4:]:
                    value = cs[col]
                    if type(value) == str:
                        # Split year values and store each as a individual param
                        # NaN values in this case will be switched to -1 for compatibility with the pipeline
                        year_values = pattern.split(value[1:-1])
                        for j in range(0, len(year_values), 2):
                            year_value = -1 if year_values[j+1] == 'NaN' else float(year_values[j+1])
                            cs_names = np.append(cs_names, f'{cs_name}&{col}&{year_values[j]}')
                            cs_values = np.append(cs_values, year_value)
                    else:
                        cs_names = np.append(cs_names, f'{cs_name}&{col}')
                        cs_values = np.append(cs_values, value)
        
        return tmap, cs_names, cs_values
    
    def get_param_ranges(self,mode,cs_names,cs_values,result_path):
        """Generate ranges for the relevant parameters
    
        Args:
            mode (str): 'morris' or 'sobol'
            cs_names (list): List containing the names of all input params
            cs_values (list): List containing the values of all input params
            result_path (str): Path where the files will be written

        Returns:
            original_params (list): List with all original params
            modified_params (list): List with the params that will vary during sampling
        """
        original_params = {}
        modified_params = {}
        
        # Retrieve the selected params for sobol analysis
        if mode == 'sobol':
            sobol_params = self.read_pkl(f'{result_path}/sobol_params.pkl')

        # TODO revise these definitions
        # Define variation range for each param, and which ones are fractions
        fraction_params = ['efficiency_charge', 'out_frac_min', 'out_frac_max', 'in_frac_min', 'in_frac_max']
        params_5_percent = ['efficiency_charge', 'c_rate', 'technical_lifetime']
        params_10_percent = ['spec_co2', 'opex_cost_power', 'max_eout', 'min_eout']
        params_20_percent = ['opex_cost_energy', 'capex_cost_power']
        problem_params = ['cap_res_max', 'cap_res_min', 'cap_min', 'cap_max']
        for i in range(len(cs_names)):
            # Set variation and fraction status
            if any(substring in cs_names[i] for substring in params_20_percent):
                percentage_range = 0.2
            elif any(substring in cs_names[i] for substring in params_5_percent):
                percentage_range = 0.05
            else:
                percentage_range = 0.1
            is_fraction = True if any(substring in cs_names[i] for substring in fraction_params) else False
            
            # Store all checked params in an array
            original_params[cs_names[i]] = cs_values[i]
            
            # Different selection conditions for each method:
            # - Morris: Keep 0's, 1's and NaNs (-1) fixed and ignore problematic params
            # - Sobol: Create a range only for the selected params
            if mode == 'morris':
                condition = not (cs_values[i] == 0 or cs_values[i] == 1 or cs_values[i] == -1) and not(any(substring in cs_names[i] for substring in problem_params))
            elif mode == 'sobol':
                condition = any(substring in cs_names[i] for substring in sobol_params)
            else:
                condition = False
            
            # Generate an array of ranges for each selected input param
            if condition:
                value_range = [cs_values[i]*(1-percentage_range), cs_values[i]*(1+percentage_range)]
                if is_fraction:
                    # If the param is a fraction, clip the values to 0 and 1
                    np.clip(value_range,0,1)
                modified_params[cs_names[i]] = value_range
        
        return original_params, modified_params
    
    def get_next_pow(self,N):
        """Computes the next power of 2 of a number
    
        Args:
            N (int): A numerical value
    
        Returns:
            int: The next power of 2 after N
        """
        if not N & (N - 1) == 0:
            power = 1
            while power < N:
                power <<= 1
            N = power
        return N
    
    def generate_input_dfs(self,tmap,samples,original_params,modified_params):
        """Generate sampled dataframes
    
        Args:
            tmap (obj): Pandas object of the techmap file
            samples (list): List of samples generated by the sampling functions
            original_params (list): List of the original values of the techmap
            modified_params (list): List of the sampled params
    
        Returns:
            list: List of dataframes, each containing a sampled input
        """
        base_cs = pd.read_excel(tmap,"ConversionSubProcess",  skiprows=[1, 2])
        input_dfs = []

        for i in range(len(samples)):
            # Use the list of modified params to iterate over the original params
            # modifying their values
            new_params = original_params
            for idx, key in enumerate(modified_params):
                new_params[key] = samples[i][idx]
            mod_cs = base_cs.copy()
            last_yearly = ''
            yearly_input = []
            range_names = list(new_params.keys())
            # Iterates over the params to include them in the modified CS sheet
            for j in range(len(range_names)):
                # Checks if it's a multiyear param by the number of components in the name
                # (multiyear has an extra component for the year)
                split_name = range_names[j].split('&')
                is_yearly = False if len(split_name) == 4 else True
                if is_yearly:
                    # Checks if it's still the same CS with the next year, or a new yearly CS
                    if range_names[j][:-5] != last_yearly:
                        # If it's different, store the current yearly param name
                        last_yearly = range_names[j][:-5]
                        # Convert back -1 to NaN if necessary 
                        value = new_params[range_names[j]] if new_params[range_names[j]] != -1 else 'NaN'
                        # Start to write the multiyear string (format: [year value; year value; year value])
                        yearly_input = f'[{split_name[-1]} {value}'
                    else:
                        # If it's still the same, just add the new entry to the string
                        value = new_params[range_names[j]] if new_params[range_names[j]] != -1 else 'NaN'
                        yearly_input = f'{yearly_input};{split_name[-1]} {value}'
                        # If it's not the last param, verify if the next has the same base name
                        # If not, complete the string and store it
                        if j != len(range_names) - 1:
                            if range_names[j+1][:-5] != range_names[j][:-5]:
                                yearly_input = f'{yearly_input}]'
                                mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                                        (mod_cs['commodity_in']==split_name[1])&
                                        (mod_cs['commodity_out']==split_name[2]),split_name[3]] = yearly_input
                        # If it's the last param, just complete the string and store it
                        else:
                            yearly_input = f'{yearly_input}]'
                            mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                                    (mod_cs['commodity_in']==split_name[1])&
                                    (mod_cs['commodity_out']==split_name[2]),split_name[3]] = yearly_input
                # If it's not multiyear, simply store the value     
                else:
                    value = new_params[range_names[j]] if new_params[range_names[j]] != -1 else 'NaN'
                    mod_cs.loc[(mod_cs['conversion_process_name']==split_name[0])&
                            (mod_cs['commodity_in']==split_name[1])&
                            (mod_cs['commodity_out']==split_name[2]),split_name[3]] = value
            input_dfs.append(mod_cs)
            
        return input_dfs
    
    def parse_samples(self,input_dfs):
        """Pass the sample dataframes through CESM's parsing function
    
        Args:
            input_dfs (list): List of dataframes, each containing a sampled input
    
        Returns:
            list: List of parsed CESM inputs
        """
        # Instantiate the parser and parse each of the sampled dataframes to CESM format
        parser = Parser(self.model_name, techmap_dir_path=self.techmap_dir_path, ts_dir_path=self.ts_dir_path, scenario=self.scenario)
        parsed_samples = []
        for idf in input_dfs:
            parser.parse(idf)
            parsed_samples.append(parser.get_input())
        
        return parsed_samples

    def read_pkl(self,path):
        """Reads a .pkl file
    
        Args:
            path (str): Path of the file to be read
    
        Returns:
            Content of the file
        """
        objects = []
        with (open(path, "rb")) as openfile:
            while True:
                try:
                    objects.append(pickle.load(openfile))
                except EOFError:
                    break
        
        return objects[0]
    
    def write_pkl(self,path,data):
        """Just to compute the square of a value
    
        Args:
            path (str): Path where to write the file (in format /path/to/file/filename)
            data: Data to be written in the file
        """
        with open(path, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)