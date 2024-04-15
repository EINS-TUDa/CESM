from Core.model import Model
import gurobipy as gp
from sqlite3 import Connection
import sqlite3
from attack.data_access import AttackDAO 
from attack.params import Attack_Params
from pathlib import Path

class AttackModel(Model):
    def __init__(self, conn: Connection, attack_params: Attack_Params) -> None:
        super().__init__(conn)
        
        # initialize db
        with open(Path(".").joinpath("attack","init_queries.sql"), 'r') as file:
            queries = file.read()
            self.cursor.executescript(queries)
            self.conn.commit()


        self.attack_params = attack_params

        self.dao = AttackDAO(self.conn)
        self.model.Params.OutputFlag = 0
        
        self._add_upper_var()
        self._add_upper_constr()

    
    def _add_upper_var(self) -> None:
        # dataset = self.data.dataset # alias for readability
        model = self.model # alias for readability
        self.upper_vars = {}
        upper_vars = self.upper_vars # alias for readability

        # Attack
        upper_vars["Upper_vars"] = model.addVars(self.dao.get_set("time"), name="Upper_vars", lb=-gp.GRB.INFINITY)
        upper_vars["Upper_obj"] = model.addVar(name="Upper_obj")
        upper_vars["Upper_aux"] = model.addVars(self.dao.get_set("time"), name="Upper_aux") # for abs value      
    
    def _add_upper_constr(self) -> None:#
        model = self.model # alias for readability
        attack_params = self.attack_params # alias for readability
        dao = self.dao # alias for readability
        self.upper_constrs = {}
        upper_constrs = self.upper_constrs # alias for readability
        vars = self.vars # alias for readability
        upper_vars = self.upper_vars # alias for readability

        # Upper
        upper_constrs["upper_limits_ub"] = model.addConstrs(
            (
                upper_vars["Upper_vars"][t] <= attack_params.upper_ub
                for t in dao.get_set("time")
            ),
            name = "upper_limits_ub"
        )
        upper_constrs["upper_limits_lb"] = model.addConstrs(
            (
                upper_vars["Upper_vars"][t] >= attack_params.upper_lb
                for t in dao.get_set("time")
            ),
            name = "upper_limits_lb"
        )
        upper_constrs["upper_sum"] = model.addConstr(
            0 == sum(upper_vars["Upper_vars"][t] * dao.get_row("availability_profile", self.attack_params.attacked_cs,t) for t in dao.get_set("time")),
            name="upper_sum",
        )
        if attack_params.constrained_cs_ineq == '>':
            upper_constrs["upper_cs_limit"] = model.addConstr(
                sum(vars["Cap_new"][self.attack_params.constrained_cs,y] for y in dao.get_set("year")) >= attack_params.constrained_cs_newval,
                name = "upper_cs_limit"
            )
        elif attack_params.constrained_cs_ineq == '<':
            upper_constrs["upper_cs_limit"] = model.addConstr(
                sum(vars["Cap_new"][attack_params.constrained_cs,y] for y in dao.get_set("year")) <= attack_params.constrained_cs_newval,
                name = "upper_cs_limit"
            )
        else:
            raise ValueError(f"constrained_cs_ineq {self.attack_params.constrained_cs_ineq} not recognized")

        # added for absolute value
        upper_constrs["upper_obj"] = model.addConstr(
            upper_vars["Upper_obj"] >= sum(upper_vars["Upper_aux"][t] for t in dao.get_set("time")),
            name = "upper_obj"
        )

        upper_constrs["upper_pos_aux"] = model.addConstrs(
            (
                upper_vars["Upper_aux"][t] >= upper_vars["Upper_vars"][t]
                for t in dao.get_set("time")
            ),
            name = "upper_pos_aux"
        )

        upper_constrs["upper_neg_aux"] = model.addConstrs(
            (
                upper_vars["Upper_aux"][t] >= -upper_vars["Upper_vars"][t]
                for t in dao.get_set("time")
            ),
            name = "upper_neg_aux"
        )
        self.obj = vars["TOTEX"]+0
        # model.setObjective(vars["TOTEX"]+0, GRB.MINIMIZE)
    
    def activate_upper_limit(self, is_active: bool):
        if is_active:
            self.upper_constrs["upper_cs_limit"].rhs = self.attack_params.constrained_cs_newval
        else:
            self.upper_constrs["upper_cs_limit"].rhs = self.attack_params.constrained_cs_inactive
    
    def set_coeff(self, dao: AttackDAO):
        for y in self.dao.get_set("year"):
            for (cs,t,avail) in self.dao.iter_row("availability_profile"):
                if cs == self.attack_params.attacked_cs:
                    self.model.chgCoeff(self.constrs["re_availability"][y,cs,t], self.vars["Cap_active"][cs,y], -avail * (1+dao.get_row("Upper",t)))

    def save_output(self) -> None:
        for table in ("global","t","y","cs_y","cs_y_t","co_y_t"):
            query = f""" DELETE FROM output_{table};"""
            self.cursor.execute(query)
        super().save_output()
        for t in self.dao.get_set("time"):
            query = f"""
            INSERT INTO output_t (t_id, upper)
            SELECT t.id, {self.upper_vars['Upper_vars'][t].X}
            FROM time_step AS t 
            WHERE t.value = {t};
            """
            self.cursor.execute(query)
        self.conn.commit()