import os
import pickle
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

class GSAPlotter:
    """
    GSA Plotter Class
        Plots the generated results for a GSA analysis
    """
    def __init__(self, gsa_dir, model, scenario, date):
        """Initialize class
    
        """
        self.model = model
        self.scenario = scenario
        self.date = date
        self.results_path = os.path.join(gsa_dir,f'{model}-{scenario}-{date}')
        try:
            self.morris_results = self.read_pkl(os.path.join(self.results_path,'morris_results.pkl'))
            self.has_morris = True
        except:
            self.has_morris = False
        try:
            self.S1 = self.read_pkl(os.path.join(self.results_path,'S1.pkl'))
            self.ST = self.read_pkl(os.path.join(self.results_path,'ST.pkl'))
            self.S2 = self.read_pkl(os.path.join(self.results_path,'S2.pkl'))
            self.has_sobol = True
        except:
            self.has_sobol = False
    
    def bar_plot_morris(self,output_var,th=0.2):
        if not self.has_morris:
            return False
        param_names = self.morris_results.columns
        idx = self.morris_results.index.get_loc(output_var)

        mu = self.morris_results.iloc[idx]
        params = np.array(param_names)
        
        if np.sum(mu) == 0:
            return False

        # Sort arrays based on the first array
        sort_idx = np.argsort(mu)
        mu = mu.iloc[sort_idx]
        params = params[sort_idx]

        # Cut values under the threshold
        keep = mu >= th
        mu = mu[keep]
        params = params[keep]

        # Plotting
        bar_width = 0.8
        index = np.arange(len(params))

        plt.figure(figsize=(10, len(mu)*0.5))

        plt.barh(index, mu, bar_width, label='mu*', color='b')
        plt.yticks(index, params)
        plt.xlabel('Sensitivity Index')
        plt.title(f'Sensitivity Analysis for {output_var}')
        plt.tight_layout()
        plt.legend()
        plt.show()

    def bar_plot_sobol(self, output_var, th=0.01):
        if not self.has_sobol:
            return False
        param_names = self.ST.columns
        idx = self.ST.index.get_loc(output_var)

        S1 = self.S1.iloc[idx]
        ST = self.ST.iloc[idx]
        params = np.array(param_names)

        # Sort arrays based on the first array
        sort_idx = np.argsort(ST)
        ST = ST.iloc[sort_idx]
        S1 = S1.iloc[sort_idx]
        params = params[sort_idx]

        # Cut values under the threshold
        keep = ST >= th
        ST = ST[keep]
        S1 = S1[keep]
        params = params[keep]

        # Plotting
        bar_width = 0.8
        index = np.arange(len(params))

        plt.figure(figsize=(10, len(ST)*0.5))

        for i in range(len(params)):
            if S1.iloc[i] > ST.iloc[i]:
                if i == len(params)-1:
                    plt.legend(['ST','S1'])
                plt.barh(i, ST.iloc[i], bar_width, color='r')
                plt.barh(i, S1.iloc[i] - ST.iloc[i], bar_width, color='b', left=ST.iloc[i])
            else:
                if i == len(params)-1:
                    plt.legend(['S1','ST'])
                plt.barh(i, S1.iloc[i], bar_width, color='b')
                plt.barh(i, ST.iloc[i] - np.clip(S1.iloc[i], 0, 10), bar_width, color='r', left=np.clip(S1.iloc[i], 0, 10))

        plt.yticks(index, params)
        plt.xlabel('Sensitivity Index')
        plt.title(f'Sensitivity Analysis for {output_var}')
        plt.tight_layout()
        plt.show()
    
    def heatmap_morris(self):
        if not self.has_morris:
            return False
        # Plot heatmap
        sns.set(font_scale=0.5)
        plt.figure(figsize=(40, 40))
        sns.heatmap(self.morris_results, annot=False, cmap=sns.color_palette("Blues", as_cmap=True), fmt=".2f", vmin=0, vmax=1)
        plt.title('Sensitivity Matrix - Morris')
        plt.xlabel('Input Parameters')
        plt.ylabel('Output Variables')
        plt.show()

    def heatmap_sobol(self,index):
        if not self.has_sobol:
            return False
        if index == "S1":
            sobol_results = self.S1
        elif index == "ST":
            sobol_results = self.ST
        else:
            return False
        # Plot heatmap
        sns.set(font_scale=0.5)
        plt.figure(figsize=(5, 30))
        sns.heatmap(sobol_results, annot=False, cmap=sns.color_palette("Blues", as_cmap=True), fmt=".2f", vmin=0, vmax=1)
        plt.title(f'Sensitivity Matrix - Sobol {index}')
        plt.xlabel('Input Parameters')
        plt.ylabel('Output Variables')
        plt.show()

    def heatmap_sobol_s2(self,variable):
        if not self.has_sobol:
            return False
        param_names = self.ST.columns
        order_2_df = pd.DataFrame(columns=param_names,index=param_names)

        idx = self.S2.index.get_loc(variable)
        for i in range(len(param_names)):
            order_2 = self.S2.iloc[idx,i]
            for j in range(i):
                order_2[j] = self.S2.iloc[idx,j][i]
            order_2 = np.array(order_2).reshape(len(order_2),1)
            order_2_df.iloc[:,i] = order_2
        order_2_df = order_2_df.apply(pd.to_numeric)

        fig = plt.figure(figsize=(6, 6))
        sns.set(font_scale=0.5)
        hm = sns.heatmap(order_2_df, annot=False, cmap=sns.color_palette("coolwarm_r", as_cmap=True), fmt=".2f", vmin=-1, vmax=1)
        plt.title(f'Sensitivity Matrix - S2 - {variable}')
        plt.xlabel('Input Parameters')
        plt.ylabel('Output Variables')
        plt.show()

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
        