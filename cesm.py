# --------------------------------------------------
#  Command Line Interface (CLI) for the application
#  
#  mail@juliabarbosa.net
# -------------------------------------------------- 

import click
import os
import time 
from pathlib import Path

from InquirerPy import prompt

# -- internal imports -- #
from Core.input_parser import Parser
from Core.model import Model
# from Core.datacls import save_input_output, read_input_output
from Core.plotter import Plotter, PlotType
from Core.data_access import DAO
import sqlite3

# Constants
TECHMAP_DIR_PATH = Path(".").joinpath('Data', 'Techmap')
TS_DIR_PATH = Path(".").joinpath('Data', 'TimeSeries')
RUNS_DIR_PATH = Path(".").joinpath('Runs')
FNAME_MODEL = 'db.sqlite'
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

def prompt_commodities(doa):
      cos = [str(c) for c in doa.get_set("commodity")]
      # remove Dummy
      cos.remove('Dummy')

      return prompt(get_list_inquirer_choices(cos, name='commodities', type='checkbox', message='Select commodities: Select with spacebar and confirm with enter'))['commodities']

def prompt_years(doa):
    yy = [int(y) for y in doa.get_set("year")]
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

   # Create a directory for the model if it does not exist
   db_dir_path = RUNS_DIR_PATH.joinpath(model_name+'-'+scenario)
   if not os.path.exists(db_dir_path):
      os.mkdir(db_dir_path)

   # Create and Run the model
   conn = sqlite3.connect(":memory:")
   parser = Parser(model_name, techmap_dir_path=TECHMAP_DIR_PATH, ts_dir_path=TS_DIR_PATH, db_conn = conn, scenario = scenario)
   # (self, name, techmap_dir_path, ts_dir_path, db_conn, scenario)

   # Parse
   print("\n#-- Parsing started --#")
   st = time.time()
   parser.parse()
   # model_input = parser.get_input()
   print(f"Parsing finished in {time.time()-st:.2f} seconds")

   # Build
   print("\n#-- Building model started --#")
   st = time.time()
   model_instance = Model(conn=conn)
   print(f"Building model finished in {time.time()-st:.2f} seconds")

   # Solve
   print("\n#-- Solving model started --#")
   st = time.time()
   model_instance.solve()
   print(f"Solving model finished in {time.time()-st:.2f} seconds")

   # Save
   print("\n#-- Saving model started --#")
   st = time.time()
   model_instance.save_output()

   # write the in-memory db to disk
   db_path = db_dir_path.joinpath(FNAME_MODEL)
   disk_db_conn = sqlite3.connect(db_path)
   conn.backup(disk_db_conn)
   

   
   # save_input_output(input=model_input, output=model_output,filename=os.path.join(path, FNAME_MODEL))
   print(f"Saving model finished in {time.time()-st:.2f} seconds")
     
@app.command(name='plot')
@click.option("--simulation", '-s', type=RunsChoice(get_runs()), help="Name of the simulation to visualize. If not provided user will be prompted to choose one.")
def plot(simulation):
   """Visualize the results of a simulation"""

   if simulation is None:
      simulation = prompt(get_list_inquirer_choices(get_runs(), name='simulation', message='Please choose a simulation to visualize'))['simulation'] 
      

   print(f"Visualizing simulation {simulation}")
   db_path = os.path.join(RUNS_DIR_PATH, simulation, FNAME_MODEL)
   conn = sqlite3.connect(db_path)
   dao = DAO(conn)
   
   st = time.time()
   plotter = Plotter(dao)


   while True:
      # Print available plots in a dictionary
      print('\n## Plotting Menu ##')
      plots = [i for i in PlotType.__dict__.keys() if not i.startswith('__')]
      plot_type = prompt(get_list_inquirer_choices(plots, name='plot', message='Please choose a plot type'))['plot'] 

      # Print available plots of that type
      p_type = getattr(PlotType, plot_type)
      plots = prompt(get_list_inquirer_choices(p_type.__members__, name='plot', type='checkbox', message='Please choose plots: Select with spacebar and confirm with enter'))['plot']
      
      if plot_type == 'Bar':
         commodities = prompt_commodities(dao)
         # Combination
         for p in plots:
            if p == 'PRIMARY_ENERGY':
               plotter.plot_bars(getattr(p_type, p))
            else:
               for c in commodities:
                  plotter.plot_bars(getattr(p_type, p), commodity=c)

      elif plot_type == 'TimeSeries':
         years = prompt_years(dao)
         commodities = prompt_commodities(dao)

         for p in plots:
            for y in years:
               for x in commodities:
                  plotter.plot_timeseries(getattr(p_type, p), year=y, commodity=x)
      
      elif plot_type == 'Sankey':
         years = prompt_years(dao)
         for y in years:
            f = plotter.plot_sankey(y)
            f.show()

      elif plot_type == 'SingleValue':
         plotter.plot_single_value([getattr(p_type, p) for p in plots])

      more_plots = prompt(get_list_inquirer_choices(['yes', 'no'], name='more_plots', message='Would you like to plot more?'))['more_plots']
      if more_plots == 'no':
         break
   
   click.echo("Plotting finished!")


if __name__ == "__main__":
   app()
   pass