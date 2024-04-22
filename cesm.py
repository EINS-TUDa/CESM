# --------------------------------------------------
#  Command Line Interface (CLI) for the application
#  
#  mail@juliabarbosa.net
# -------------------------------------------------- 

import click
import os
import time 
from pathlib import Path
from distutils.dir_util import copy_tree
import pkg_resources
from InquirerPy import prompt

# -- internal imports -- #
from core.input_parser import Parser
from core.model import Model
from core.plotter import Plotter, PlotType
from core.data_access import DAO
import sqlite3

# Constants
DATA_DIR_PATH = Path(".").joinpath('Data')
TECHMAP_DIR_PATH = Path(".").joinpath('Data', 'Techmap')
TS_DIR_PATH = Path(".").joinpath('Data', 'TimeSeries')
RUNS_DIR_PATH = Path(".").joinpath('Runs')

FNAME_MODEL = 'db.sqlite'
# -- Helpers -- #
def get_existing_models():
      """Return a list of existing models"""
      # files = os.listdir(TECHMAP_DIR_PATH)
      files = [file.name for file in TECHMAP_DIR_PATH.glob("*") if file.is_file()]
      return [tm.split('.')[0] for tm in files if tm.endswith('.xlsx')]

def get_runs():
   """Return a list of existing runs"""
   return [entry.name for entry in RUNS_DIR_PATH.iterdir() if entry.is_dir()]

def get_list_inquirer_choices(choices, name=None, message=None, type='list'):
   """Return a dict of choices in the format required by PyInquirer"""
   return {
      'type': type,
      'name': name,
      'message': message,
      'choices': choices,
   }

def prompt_commodities(dao):
      cos = [str(c) for c in dao.get_set("commodity")]
      # remove Dummy
      cos.remove('Dummy')

      return prompt(get_list_inquirer_choices(cos, name='commodities', type='checkbox', message='Select commodities: Select with spacebar and confirm with enter'))['commodities']

def prompt_years(dao):
    yy = [int(y) for y in dao.get_set("year")]
    return prompt(get_list_inquirer_choices(yy, name='years', type='checkbox', message='Select years: Select with spacebar and confirm with enter'))['years']
   

# -- Main CLI Application -- #
@click.group()
def app():
   """Welcome to the Compact Energy System Modelling Tool (CESM)"""

@app.command(name='run')
def run():
   """Run the Model"""
   # print(f'Running model {model_name} with scenario {scenario}')

   # If no scenario or model is provided, prompt the user to choose one
   # if model_name is None:
   model_name = prompt(get_list_inquirer_choices(get_existing_models(), name='model_name', message='Please choose a model to run'))['model_name']
   # if scenario is None:
   scenario = click.prompt('Please enter a scenario name', type=click.STRING)

   # Create a directory for the model if it does not exist
   db_dir_path = RUNS_DIR_PATH.joinpath(model_name+'-'+scenario)
   if not os.path.exists(db_dir_path):
      os.mkdir(db_dir_path)

   # Create and Run the model
   conn = sqlite3.connect(":memory:")
   parser = Parser(model_name, techmap_dir_path=TECHMAP_DIR_PATH, ts_dir_path=TS_DIR_PATH, db_conn = conn, scenario = scenario)

   # Parse
   print("\n#-- Parsing started --#")
   st = time.time()
   parser.parse()
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

   
   db_path = db_dir_path.joinpath(FNAME_MODEL)
   if db_path.exists():
      # Delete the file using unlink()
      db_path.unlink()
   
   # write the in-memory db to disk
   disk_db_conn = sqlite3.connect(db_path)
   conn.backup(disk_db_conn)
   
   print(f"Saving model finished in {time.time()-st:.2f} seconds")
     
@app.command(name='plot')
def plot():
   """Visualize the results of a simulation"""

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

@app.command(name='init')
def initialize():
   print("Initializing CESM...")
   RUNS_DIR_PATH.mkdir(exist_ok=True)
   if not DATA_DIR_PATH.exists():
      DATA_DIR_PATH.mkdir()
      data_folder_path = pkg_resources.resource_filename('cesm', 'Data')
      copy_tree(data_folder_path, str(Path(".").joinpath("Data").absolute()))
   print("Data files are successfully structured.")

if __name__ == "__main__":
   app()