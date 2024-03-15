import re
import os
import pickle
import time
import numpy as np
import pandas as pd
from pathlib import Path
from collections import Counter
from SALib.analyze.morris import analyze as morris_analyze
from SALib.analyze.sobol import analyze as sobol_analyze

class GSAAnalyzer:
    """
    GSA Analyzer Model Class
        Analyzes the results for a given set of samples
    """
    def __init__(self, path, mode):
        """Initialize class
    
        Args:
            path (str): Path to the results
            mode (str): 'morris' or 'sobol'
        """
        # Set the paths according to the operation mode
        self.path = path
        self.problem_path = f'{path}/{mode}_problem_def.pkl'
        self.X_path = f'{path}/{mode}_X.pkl'
        self.Y_path = f'{path}/{mode}_Y.pkl'
        
        # Get the problem definition and the param names of the run
        self.problem = self.read_pkl(self.problem_path)
        self.param_names = self.problem['names']
        
        # Get the inputs of the run (X)
        self.X = self.read_pkl(self.X_path)
        
        # Get the outputs of the run (Y) and the var names used
        self.Y = self.read_pkl(self.Y_path)
        self.var_names = self.Y['output_var_names']
        
    def analyze_morris(self):
        """Analyze the Morris case and store the results as
        .pkl files. The path is the same used to initialize
        the class.
        """
        # Filter out infeasible results from the result set
        feasible_Y, feasible_X = self.get_feasible_runs()
        
        # Morris analyzer requires even elements, remove last one if odd
        if len(feasible_Y) % 2 != 0:
            feasible_Y = feasible_Y[:-1]
            feasible_X = feasible_X[:-1]
        
        df_mu_star = pd.DataFrame(columns=self.param_names)
        df_mu = pd.DataFrame(columns=self.param_names)

        # Run the Morris analysis for each of the output vars
        for i in range(feasible_Y.shape[1]):
            Si = morris_analyze(problem=self.problem,X=feasible_X,Y=feasible_Y[:,i])
            # Getting only mu_star because, it's a more reliable parameter than mu,
            # and sigma is useful for interactions, which will be better assessed
            # in the Sobol method. Here we just need mu_star
            if np.max(Si['mu_star']) == 0:
                df_mu_star.loc[self.var_names[i]] = list(Si['mu_star'])
            else:
                df_mu_star.loc[self.var_names[i]] = list(Si['mu_star'] / np.max(Si['mu_star']))
            df_mu.loc[self.var_names[i]] = list(Si['mu'])
        
        # Save the full results as a dataframe
        self.write_pkl(f'{self.path}/morris_mu_star.pkl', df_mu_star)
        self.write_pkl(f'{self.path}/morris_mu.pkl', df_mu)

        # Set the number of relevant parameters to be selected as 25% of the total
        sel_num = int(len(self.param_names)*0.25)
        rows_to_drop = []
        cols_to_drop = []
        frequent_contributors = []
        # Filter all rows with only low contributions (the output var is not really influenced by any param)
        for i in range(len(df_mu_star)):
            if np.max(df_mu_star.iloc[i]) < 0.5:
                rows_to_drop.append(self.var_names[i])
                continue
            # Select the params with the biggest contribution for each output var
            top_contributions = df_mu_star.iloc[i].sort_values(ascending=False).head(sel_num)
            frequent_contributors.append(list(top_contributions.index))
        # Filter all columns with only low contributions (the input param doesn't have big influences over any output var)
        for j in range(df_mu_star.shape[1]):
            if np.max(df_mu_star.iloc[:,j]) < 0.5:
                cols_to_drop.append(self.param_names[j])
        # Drop selected rows and columns
        df_mu_star = df_mu_star.drop(rows_to_drop)
        df_mu_star = df_mu_star.drop(cols_to_drop,axis=1)
        
        # Flatten the biggest contributors list and select the most frequent ones (input params that appears the most as influential)
        flat_contributors = [item for sublist in frequent_contributors for item in sublist]
        counts = Counter(flat_contributors)
        top_contributors = [value for value, count in counts.most_common(sel_num)]
        
        # Sum each column and select the ones with the higher total contribution (input params that influence more output vars)
        total_contribution = df_mu_star.sum(axis=0)
        top_individual_contributions = list(total_contribution.sort_values(ascending=False).head(sel_num).index)
        
        # Create a set for both lists
        set1 = set(top_contributors)
        set2 = set(top_individual_contributions)
        
        # Get the intersection of the sets to be the focus for Sobol analysis
        params_for_sobol = set1.intersection(set2)
        
        # Store the params that will be used for Sobol
        self.write_pkl(f'{self.path}/sobol_params.pkl', params_for_sobol)
            
    def analyze_sobol(self):
        """Analyze the Morris case and store the results as
        .pkl files. The path is the same used to initialize
        the class.
        """
        feasible_Y, feasible_X = self.get_feasible_runs()
        
        df_s1 = pd.DataFrame(columns=self.param_names)
        df_s2 = pd.DataFrame(columns=self.param_names)
        df_st = pd.DataFrame(columns=self.param_names)

        # Run the Sobol analysis for each of the output vars
        for i in range(feasible_Y.shape[1]):
            Si = sobol_analyze(problem=self.problem,Y=feasible_Y[:,i])
            # Store each of the indices to a dataframe
            # S1: individual contribution of the param
            # S2: interaction contribution of the param (needs calc_second_order in the sampling)
            # ST: total contribution of the param
            df_s1.loc[self.var_names[i]] = list(Si['S1'])
            df_s2.loc[self.var_names[i]] = list(Si['S2'])
            df_st.loc[self.var_names[i]] = list(Si['ST'])
        
        self.write_pkl(f'{self.path}/S1.pkl',df_s1)
        self.write_pkl(f'{self.path}/S2.pkl',df_s2)
        self.write_pkl(f'{self.path}/ST.pkl',df_st)
            
    
    def get_feasible_runs(self):
        """Filter out infeasible runs from the result set
    
        Returns:
            feasible_Y (list): List with the output values for the feasible runs
            feasible_X (list): List with the input values for the feasible runs
        """
        # Calculate the number of feasible runs based on the input dict fields
        feasible_runs = len(self.Y['infeasible']) - np.sum(self.Y['infeasible'])
        feasible_Y = np.empty((feasible_runs,len(self.Y['runs'][1])))
        feasible_X = np.empty((feasible_runs,len(self.X[0])))

        # Include only the feasible ones in the output lists
        idx = 0
        for key in self.Y['runs']:
            if not self.Y['infeasible'][key-1]:
                feasible_Y[idx] = self.Y['runs'][key]
                feasible_X[idx] = self.X[key-1]
                idx += 1
        
        return feasible_Y, feasible_X
    
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