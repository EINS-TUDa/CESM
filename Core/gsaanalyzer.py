import re
import os
import pickle
import time
import numpy as np
import pandas as pd
from pathlib import Path
from collections import Counter
from SALib.analyze.morris import analyze as morris_analyze

class GSAAnalyzer:
    """
    GSA Analyzer Model Class
        Analyzes the results for a given set of samples
    """
    def __init__(self, path):
        self.path = path
        self.problem_path = f'{path}/problem_def.pkl'
        self.X_path = f'{path}/X.pkl'
        self.Y_path = f'{path}/Y.pkl'
        
        temp = []
        with (open(self.problem_path, "rb")) as openfile:
            while True:
                try:
                    temp.append(pickle.load(openfile))
                except EOFError:
                    break
        self.problem = temp[0]
        self.param_names = self.problem['names']
        
        temp = []
        with (open(self.X_path, "rb")) as openfile:
            while True:
                try:
                    temp.append(pickle.load(openfile))
                except EOFError:
                    break
        self.X = temp[0]
        
        temp = []
        with (open(self.Y_path, "rb")) as openfile:
            while True:
                try:
                    temp.append(pickle.load(openfile))
                except EOFError:
                    break
        self.Y = temp[0]
        self.var_names = temp[0]['output_var_names']
        
    def analyze_morris(self):
        feasible_runs = len(self.Y['infeasible']) - np.sum(self.Y['infeasible'])
        feasible_Y = np.empty((feasible_runs,len(self.Y['runs'][1])))
        feasible_X = np.empty((feasible_runs,len(self.X[0])))

        idx = 0
        for key in self.Y['runs']:
            if not self.Y['infeasible'][key-1]:
                feasible_Y[idx] = self.Y['runs'][key]
                feasible_X[idx] = self.X[key-1]
                idx += 1
                
        if feasible_runs % 2 != 0:
            feasible_Y = feasible_Y[:-1]
            feasible_X = feasible_X[:-1]
        
        Si = {'input_params':self.param_names,'output_vars':self.var_names,'morris_results':[]}
        for i in range(feasible_Y.shape[1]):
            Si['morris_results'].append(morris_analyze(problem=self.problem,X=feasible_X,Y=feasible_Y[:,i]))
        
        df = pd.DataFrame(columns=self.param_names)

        for i in range(feasible_Y.shape[1]):
            Si = morris_analyze(problem=self.problem,X=feasible_X,Y=feasible_Y[:,i])
            # Getting only mu_star because, it's a more reliable parameter than mu, and sigma is useful for interactions, which will be better
            # assessed in the Sobol method. Here we just need mu_star
            if np.max(Si['mu_star']) == 0:
                df.loc[self.var_names[i]] = list(Si['mu_star'])
            else:
                df.loc[self.var_names[i]] = list(Si['mu_star'] / np.max(Si['mu_star']))
        
        with open(f'{self.path}/morris_results.pkl', 'wb') as f:
            pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)

        sel_num = int(len(self.param_names)*0.25)
        rows_to_drop = []
        cols_to_drop = []
        frequent_contributors = []
        for i in range(len(df)):
            if np.max(df.iloc[i]) < 0.5:
                rows_to_drop.append(self.var_names[i])
                continue
            top_contributions = df.iloc[i].sort_values(ascending=False).head(sel_num)
            frequent_contributors.append(list(top_contributions.index))
        for j in range(df.shape[1]):
            if np.max(df.iloc[:,j]) < 0.5:
                cols_to_drop.append(self.param_names[j])
        df = df.drop(rows_to_drop)
        df = df.drop(cols_to_drop,axis=1)
        
        flat_contributors = [item for sublist in frequent_contributors for item in sublist]
        counts = Counter(flat_contributors)
        top_contributors = [value for value, count in counts.most_common(sel_num)]
        
        total_contribution = df.sum(axis=0)
        top_individual_contributions = list(total_contribution.sort_values(ascending=False).head(sel_num).index)
        
        set1 = set(top_contributors)
        set2 = set(top_individual_contributions)
        
        params_for_sobol = set1.intersection(set2)
        
        with open(f'{self.path}/sobol_params.pkl', 'wb') as f:
            pickle.dump(params_for_sobol, f, protocol=pickle.HIGHEST_PROTOCOL)