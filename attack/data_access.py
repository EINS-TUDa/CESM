from Core.data_access import DAO, CS
from sqlite3 import Connection
from typing import NamedTuple
from Core.params import Output_Index_Dict

class Attack_params(NamedTuple):
    attacked_cs: CS
    constrained_cs: CS
    constrained_cs_newval: float
    constrained_cs_inactive: float
    constrained_cs_ineq: str
    upper_ub: float
    upper_lb: float

class PADM_params(NamedTuple):
    initial_mu: float
    increase_factor: int
    max_penalty_iter: int
    max_stationary_iter: int
    stationary_error: float
    penalty_error: float


class AttackDOA(DAO):
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        Output_Index_Dict["Upper"] = ['T']

    # def get_upper(self, t):
    #     value = self.cursor.execute(f"""
    #         SELECT t.value, upper FROM output_t
    #         JOIN time AS t ON t_id = {t}
    #     """).fetchone()
    #     return value