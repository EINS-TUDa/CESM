# --------------------------------------------------
#  Command Line Interface (CLI) for the application
#  
#  mail@juliabarbosa.net
# -------------------------------------------------- 

import click
import os
import time 
import pickle
from pathlib import Path
from datetime import datetime

from InquirerPy import prompt

# -- internal imports -- #
from Core.inputparse import Parser
from Core.model import Model
from Core.datacls import save_input_output, read_input_output
from Core.plotter import Plotter, PlotType
from Core.gsasampler import GSASampler
from Core.gsaanalyzer import GSAAnalyzer

# Constants
TECHMAP_DIR_PATH = Path(".").joinpath(os.getcwd(), 'Data', 'Techmap')
TS_DIR_PATH = Path(".").joinpath(os.getcwd(), 'Data', 'TimeSeries')
RUNS_DIR_PATH = Path(".").joinpath(os.getcwd(), 'Runs')
GSA_DIR_PATH = Path(".").joinpath(os.getcwd(), 'GSAResults')
FNAME_MODEL = 'input_output.pkl'
# -- Helpers -- #
def get_existing_models():
      """Return a list of existing models"""
      files = os.listdir(TECHMAP_DIR_PATH)
      return [tm.split('.')[0] for tm in files if tm.endswith('.xlsx')]

class ModelChoice(click.Choice):
    def convert(self, value, param, ctx):
         try:
               return super().convert(value, param, ctx)
         except click.exceptions.BadParameter:
               # print each model in one line   
               available_models = '\n\t '.join(get_existing_models())
               raise click.BadParameter(f"Model {value} not found.\n \tAvailable models are:\n\t {available_models}")

def get_runs():
   """Return a list of existing runs"""
   return os.listdir(RUNS_DIR_PATH)

class RunsChoice(click.Choice):
   def convert(self, value, param, ctx):
      try:
         return super().convert(value, param, ctx)
      except click.exceptions.BadParameter:
         # print each model in one line   
         available_runs = '\n\t '.join(get_runs())
         raise click.BadParameter(f"Run {value} not found.\n \tComputed model runs are:\n\t {available_runs}")

def get_list_inquirer_choices(choices, name=None, message=None, type='list'):
   """Return a dict of choices in the format required by PyInquirer"""
   return {
      'type': type,
      'name': name,
      'message': message,
      'choices': choices,
   }

def prompt_commodities(input):
      cos = [str(c) for c in input.dataset.commodities]
      # remove Dummy
      cos.remove('Dummy')

      return prompt(get_list_inquirer_choices(cos, name='commodities', type='checkbox', message='Select commodities: Select with spacebar and confirm with enter'))['commodities']

def prompt_years(input):
    yy = [int(y) for y in input.dataset.years]
    return prompt(get_list_inquirer_choices(yy, name='years', type='checkbox', message='Select years: Select with spacebar and confirm with enter'))['years']
   

# -- Main CLI Application -- #
@click.group()
def app():
   """Welcome to the Compact Energy System Modelling Tool (CESM)"""
   
@app.command(name='run')
@click.option("--model_name",'-m', type=ModelChoice(get_existing_models()))
@click.option("--scenario",'-s', type=click.STRING)
def run(model_name, scenario):
   """Run the Model"""
   print(f'Running model {model_name} with scenario {scenario}')

   # If no scenario or model is provided, prompt the user to choose one
   if model_name is None:
      model_name = prompt(get_list_inquirer_choices(get_existing_models(), name='model_name', message='Please choose a model to run'))['model_name']
   if scenario is None:
      scenario = click.prompt('Please enter a scenario name', type=click.STRING)

   # Create and Run the model 
   parser = Parser(model_name, techmap_dir_path=TECHMAP_DIR_PATH, ts_dir_path=TS_DIR_PATH ,scenario = scenario) 

   # Parse
   print("\n#-- Parsing started --#")
   st = time.time()
   parser.parse()
   model_input = parser.get_input()
   print(f"Parsing finished in {time.time()-st:.2f} seconds")

   # Build
   print("\n#-- Building model started --#")
   st = time.time()
   model_instance = Model(model_input)
   print(f"Building model finished in {time.time()-st:.2f} seconds")

   # Solve
   print("\n#-- Solving model started --#")
   st = time.time()
   model_instance.solve()
   print(f"Solving model finished in {time.time()-st:.2f} seconds")

   # Save
   print("\n#-- Saving model started --#")
   st = time.time()
   model_output = model_instance.get_output()
   model_instance.output_list_to_pkl()
   
   # Create a directory for the model if it does not exist
   path = os.path.join(RUNS_DIR_PATH, model_name+'-'+scenario)
   if not os.path.exists(path):
      os.mkdir(path)
   
   save_input_output(input=model_input, output=model_output,filename=os.path.join(path, FNAME_MODEL))
   print(f"Saving model finished in {time.time()-st:.2f} seconds")
     
@app.command(name='plot')
@click.option("--simulation", '-s', type=RunsChoice(get_runs()), help="Name of the simulation to visualize. If not provided user will be prompted to choose one.")
def plot(simulation):
   """Visualize the results of a simulation"""

   if simulation is None:
      simulation = prompt(get_list_inquirer_choices(get_runs(), name='simulation', message='Please choose a simulation to visualize'))['simulation'] 
      

   print(f"Visualizing simulation {simulation}")
   input, output = read_input_output(os.path.join(RUNS_DIR_PATH, simulation, FNAME_MODEL))
   
   st = time.time()
   plotter = Plotter(input, output)


   while True:
      # Print available plots in a dictionary
      print('\n## Plotting Menu ##')
      plots = [i for i in PlotType.__dict__.keys() if not i.startswith('__')]
      plot_type = prompt(get_list_inquirer_choices(plots, name='plot', message='Please choose a plot type'))['plot'] 

      # Print available plots of that type
      p_type = getattr(PlotType, plot_type)
      plots = prompt(get_list_inquirer_choices(p_type.__members__, name='plot', type='checkbox', message='Please choose plots: Select with spacebar and confirm with enter'))['plot']
      
      if plot_type == 'Bar':
         commodities = prompt_commodities(input)
         # Combination
         for p in plots:
            if p == 'PRIMARY_ENERGY':
               plotter.plot_bars(getattr(p_type, p))
            else:
               for c in commodities:
                  plotter.plot_bars(getattr(p_type, p), commodity=c)

      elif plot_type == 'TimeSeries':
         years = prompt_years(input)
         commodities = prompt_commodities(input)

         for p in plots:
            for y in years:
               for x in commodities:
                  plotter.plot_timeseries(getattr(p_type, p), year=y, commodity=x)
      
      elif plot_type == 'Sankey':
         years = prompt_years(input)
         for y in years:
            f = plotter.plot_sankey(y)
            f.show()

      elif plot_type == 'SingleValue':
         plotter.plot_single_value([getattr(p_type, p) for p in plots])

      more_plots = prompt(get_list_inquirer_choices(['yes', 'no'], name='more_plots', message='Would you like to plot more?'))['more_plots']
      if more_plots == 'no':
         break
   
   click.echo("Plotting finished!")
   
@app.command(name='gsa')
@click.option("--model_name",'-m', type=ModelChoice(get_existing_models()))
@click.option("--scenario",'-s', type=click.STRING)
@click.option("--input_samples",'-i', type=click.STRING)
def run(model_name, scenario, input_samples):
   """Run the Model"""
   print(f'Running model {model_name} with scenario {scenario}')
   
   run_date = datetime.now().strftime("%d-%m-%y_%H-%M")
   
   # Create a directory for the model if it does not exist
   path = os.path.join(GSA_DIR_PATH, model_name+'-'+scenario+'-'+run_date)
   if not os.path.exists(path):
      os.mkdir(path)

   # If no scenario or model is provided, prompt the user to choose one
   if model_name is None:
      model_name = prompt(get_list_inquirer_choices(get_existing_models(), name='model_name', message='Please choose a model to run'))['model_name']
   if scenario is None:
      scenario = click.prompt('Please enter a scenario name', type=click.STRING)
       
   for mode in ['morris', 'sobol']:
      """Generate Samples"""
      print(f'\n#-- Starting {mode} method --#')
      print("\n#-- Generating input samples --#")
      sampler = GSASampler(model_name, techmap_dir_path=TECHMAP_DIR_PATH, ts_dir_path=TS_DIR_PATH ,scenario = scenario)
      st = time.time()
      if mode == 'sobol' or (mode == 'morris' and input_samples is None):
         input_samples = sampler.generate_samples(run_date,path,mode)
      else:
         sample_input = []
         with (open(f'GSASamples/{input_samples}', "rb")) as openfile:
            while True:
               try:
                  sample_input.append(pickle.load(openfile))
               except EOFError:
                  break
         input_samples = sample_input[0]
      print(f"Sampling finished in {time.time()-st:.2f} seconds")
        
      for i in range(len(input_samples)):
         # Build
         print(f"\n#-- Run {i+1}/{len(input_samples)} --#")
         print("\n#-- Building model started --#")
         st = time.time()
         model_input = input_samples[i]
         model_instance = Model(model_input)
         print(f"Building model finished in {time.time()-st:.2f} seconds")  

         # Solve
         print("\n#-- Solving model started --#")
         st = time.time()
         model_instance.solve()
         opt_status = model_instance.getStatus()
         print(f"Solving model finished in {time.time()-st:.2f} seconds") 

         # Save
         print("\n#-- Saving model started --#")
         st = time.time()
         model_instance.output_list_to_pkl(os.path.join(path, f'{mode}_Y.pkl'),opt_status)
            
         print(f"Saving model finished in {time.time()-st:.2f} seconds")
    
      print(f'Run complete at {datetime.now().strftime("%d-%m-%y %H-%M")}')


if __name__ == "__main__":
   app()
   pass