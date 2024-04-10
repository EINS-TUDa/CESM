from Core.data_access import CS
from typing import NamedTuple

class Attack_Params(NamedTuple):
    attacked_cs: CS
    constrained_cs: CS
    constrained_cs_newval: float
    constrained_cs_inactive: float
    constrained_cs_ineq: str
    upper_ub: float
    upper_lb: float

class PADM_Params(NamedTuple):
    initial_mu: float
    increase_factor: int
    max_penalty_iter: int
    max_stationary_iter: int
    stationary_error: float
    penalty_error: float

  