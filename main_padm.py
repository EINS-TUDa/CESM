"""
quickstart script

Author: Sina Hajikazemi
Date: 18.10.2023
"""

from Core.input_parser import Parser
from Core.data_access import CS
from pathlib import Path
from attack.padm import PADM
from attack.params import PADM_Params, Attack_Params
import sqlite3

# make Logs folder if it doesn't exist
Path('./Runs/DEModel_V2-Base-attack').mkdir(parents=True, exist_ok=True)
Path('./Logs').mkdir(parents=True, exist_ok=True)



model_name = "DEModel_V2" # model name

techmap_dir_path = Path(".").joinpath("Data", "Techmap")
ts_dir_path = Path(".").joinpath("Data", "TimeSeries")
db_dir_path = Path(".").joinpath("Runs", "DEModel_V2-Base")
primal_path = db_dir_path.joinpath("primal.sqlite")
padm_path =  db_dir_path.joinpath("padm.sqlite")

for file_path in [primal_path, padm_path]:
    if file_path.exists():
        # Delete the database file()
        file_path.unlink()
        print("File deleted successfully:", file_path)
    else:
        print("File does not exist:", file_path)

# conn_primal = sqlite3.connect(primal_path)
conn_padm = sqlite3.connect(padm_path)
# Parser("DEModel_V2",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,db_conn=conn_primal ,scenario = "Base").parse()
Parser("DEModel_V2",techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,db_conn=conn_padm ,scenario = "Base").parse()

attack_params = Attack_Params(
    attacked_cs= CS("PP_WindOn_New","Dummy","Electricity"),
    constrained_cs= CS("PP_PV_New","Dummy","Electricity"),
    constrained_cs_newval= 20,
    constrained_cs_inactive= 0,
    constrained_cs_ineq= ">",
    upper_ub= 0.5,
    upper_lb= -0.5
)
padm_params = PADM_Params(
    initial_mu= 0.0064,
    increase_factor= 2,
    max_penalty_iter= 100,
    max_stationary_iter= 30,
    stationary_error= 0.0001,
    penalty_error= 5
)


padm = PADM(conn_padm, attack_params)
padm.attack(padm_params)



# techmap_dir_path = Path(".").joinpath("Data", "Techmap") # techmap directory path
# ts_dir_path = Path(".").joinpath("Data", "TimeSeries") # time series directory path
# parser = Parser(model_name,techmap_dir_path=techmap_dir_path, ts_dir_path=ts_dir_path ,scenario = "Base")
# print("### parsing started ###")
# parser.parse()
# input = parser.get_input()
# control = PADM(input)

# attack_params.constrained_cs = "PP_Gas"
# attack_params.constrained_cs_inactive = 0
# attack_params.constrained_cs_newval = 120
# # for i in range(1,6):
# #     attack_params.constrained_cs_newval = i * 10
# control.PADM_attack(PADM_params=PADM_Params(), attack_params=attack_params)
