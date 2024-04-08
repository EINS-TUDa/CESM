import gurobipy as gp
from gurobipy import GRB
from attack.model import AttackModel
from attack.data_access import Attack_Params, PADM_Params
import re
import logging
from sqlite3 import Connection
# from attack.params import Attack_Params, PADM_Params
from pathlib import Path

class GeneralModel():
    def __init__(self, attack_params: Attack_Params) -> None:
        logging.basicConfig(filename=Path(".").joinpath("Logs","log" + GeneralModel.gen_file_name(attack_params) +".log").absolute(), encoding='utf-8', level=logging.DEBUG)     
        self.dual_padm_model = gp.read("dual.lp")
        self.dual_padm_model.Params.OutputFlag = 0
        self.primal_padm_model = AttackModel(input, attack_params)
        self.primal_model = AttackModel(input, attack_params)
        self.primal_model.model.setObjective(self.primal_model.obj)
        primal_padm_model = self.primal_padm_model

        self.vars = {"primal":[], "dual":[], "upper":[]} # the dictionary of the all variables of the model (primal, dual , upper and ...) and type of the values is always gp.MVar   
        self.constrs = {"primal":[], "dual":[], "upper":[]} 
        self.obj = {} # to keep objective function expressions. the keys are "primal", "dual" and "upper"

        self.constrs["fix"] = {} # to keep the variable-fixing constraints: it is not needed anymore
        self.vars["dual"] = gp.MVar.fromlist(self.dual_padm_model.getVars())
        # self.vars["primal"] = gp.MVar.fromlist(GeneralModel.flatten(primal_padm_model.vars))
        # self.vars["upper"] = gp.MVar.fromlist(GeneralModel.flatten(primal_padm_model.upper_vars))
        # self.constrs["primal"] = GeneralModel.flatten(primal_padm_model.constrs)
        # self.constrs["upper"] = GeneralModel.flatten(primal_padm_model.upper_constrs)
        
        self.dual_vars_dict = self.get_dual_vars(attack_params)

        self.obj["primal"] = primal_padm_model.obj
        self.obj["upper"] = primal_padm_model.upper_vars["upper_obj"] + 0
        self.obj["dual_real"] = - self.dual_padm_model.getObjective() + 0
        self.obj["dual"] = - self.dual_padm_model.getObjective() + 0

    @staticmethod
    def gen_file_name(attack_params: Attack_Params):
        return(f"_a_{str(attack_params.attacked_cs)}_c_{str(attack_params.constrained_cs)}_{str(attack_params.constrained_cs_newval)}")
    
    @staticmethod
    def flatten(element_dict):
        element_list = []
        for value in element_dict.values():
            if isinstance(value, gp.tupledict):
                element_list.extend(value.values())
            elif isinstance(value, gp.Var) or isinstance(value, gp.Constr):
                element_list.append(value)
            else:
                print(type(value))
                # print(value.index)
                print("type is not compatible")
                # raise ValueError("the type of the value is not supported")
        return element_list

    def set_coeff(self, conn: Connection) -> None:
        """sets the coefficient of the upper level variables in the primal problem (fixed lower-level variables)

        :param output: _description_
        :type output: dtcls.Output
        """
        # dataset = self.primal_padm_model.data.dataset
        # param = self.primal_padm_model.data.param
        dao = self.primal_padm_model.dao
        for y in dao.get_set("year"):
            for (cs,t,avail) in dao.iter_param("availability_profile"):
                if cs == self.primal_padm_model.attack_params.attacked_cs:
                    self.primal_padm_model.model.chgCoeff(self.primal_padm_model.constrs["re_availability"][y,cs,t], self.primal_padm_model.upper_vars["Upper_vars"][t],- dao.get_param("Cap_active",cs,y) * avail)

    def get_dual_vars(self, attack_params) -> dict:  
        vars = {}
        main_re = re.compile(rf"re_availability\(Year\(_valuee(?P<year>[0-9]+)\),\(ConversionProcess\(_valuee'{attack_params.attacked_cs.cp}'\),Commodity\(_valuee'Dummy'\),Commodity\(_valuee'Electricity'\)\),Time\(_valuee(?P<time>[0-9]+)\)\)#[0-9]+")
        for var in self.vars["dual"].tolist():
            m = main_re.match(var.VarName)
            if m: 
                year_value = int(m.group("year"))
                time_value = int(m.group("time"))
                dataset = self.primal_padm_model.data.dataset
                for y in dataset.years:
                    if y._value == year_value:
                        year = y
                        break
                for t in dataset.times:
                    if t._value == time_value:
                        time = t
                        break
                vars[(year, time)] = var
        return vars


    def print_upper_vars(self):
        dao = self.primal_padm_model.dao
        for t in dao.get_set("time"):
            print(f"t:{t._value}, {self.primal_padm_model.upper_vars['Upper_vars'][t].X}")
        

    def fix_vars(self, name: str, fix_value:float|None = None) -> None:
        model = self.primal_padm_model.model
        # mvar_list = list(self.vars[name].values())
        constr_list = []
        self.constrs["fix"][name] = constr_list
        # for mvar in mvar_list:
        vars = []
        if isinstance(self.vars[name],dict):
            for key in sorted(self.vars[name].keys()):
                vars.extend(self.vars[name][key].tolist())
        else:
            vars = self.vars[name].tolist()
        for var in vars:
            if fix_value is None:
                constr_list.append(model.addConstr(var.X == var))
            else:
                constr_list.append(model.addConstr(fix_value == var))


    def relax_vars(self, name:str) -> None:
        for con in self.constrs["fix"][name]:
            self.primal_padm_model.model.remove(con)
        del self.constrs["fix"][name]
    
    def set_obj(self, name:str) -> None:
        if name in ("primal", "upper"):
            sense = GRB.MINIMIZE
        else:
            raise Exception(f"{name} objective function isn't defined")
        self.primal_padm_model.model.setObjective(self.obj[name], sense)
        self.primal_padm_model.model.update()
    
    def set_primal_obj(self, mu: float, output: dtcls.Output) -> None:
        dual_expr = self.get_obj_value("dual")
        cs = self.primal_padm_model.attacked_cs
        dao = self.primal_padm_model.dao
        for t in dao.get_set("time"):
            for y in dao.get_set("year"):
                dual_expr += - self.primal_padm_model.upper_vars["Upper_vars"][t] * self.dual_vars_dict[y,t].X * output.power.Cap_active[cs,y] * dao.get_param("availability_profile",cs,t)
        expr = self.obj["upper"] + mu * (self.obj["primal"] - dual_expr)
        self.primal_padm_model.model.setObjective(expr ,GRB.MINIMIZE)
    
    def set_dual_obj(self, output: dtcls.Output) -> None:
        cs = self.primal_padm_model.attacked_cs
        dao = self.primal_padm_model.dao
        expr = 0 + self.obj["dual"]
        for t in dao.get_set("time"):
            for y in dao.get_set("year"):
                expr +=  - self.primal_padm_model.upper_vars["Upper_vars"][t].X * self.dual_vars_dict[y,t] * output.power.Cap_active[cs,y] * dao.get_param("availability_profile",cs,t) 
        self.dual_padm_model.setObjective(expr ,GRB.MAXIMIZE)
        self.obj["dual_real"] = expr
    
    def get_obj_value(self, name:str) -> float:
        return self.obj[name].getValue()

    def get_values(self, name:str, indices:list[str|int]) -> dict[str, float]:
        output = {}
        def match(pattern:list[str|int],indices:list[str|int]):
            if len(pattern) != len(indices):
                return False
            for i in range(len(pattern)):
                if pattern[i] != ':' and pattern[i] != indices[i]:
                    return False
            return True
        for var in self.var_dict[name]:
            if match(indices,var.indices):
                output[name+(str(var.indices) if len(indices)>0 else '')] = var.ref.X
        return output
    
    def get_MVar_values(self, name:str):
        def get_val(m: gp.MVar):
            output = []
            for var in m.tolist():
                output.append(var.X)
            return output

        if isinstance(self.vars[name],dict):
            output = []
            for key in sorted(self.vars[name].keys()):
                output.extend(get_val(self.vars[name][key]))
        else:
            output = get_val(self.vars[name])
        return output

class Control():
    def __init__(self, conn: Connection) -> None:
        self.conn = conn
        
    @staticmethod
    def diff_values(a: dict[str,list[float]], b: dict[str,list[float]]) -> float:
        max_diff = -float('inf')
        for i in range(len(a)):
            if abs(a[i] - b[i]) > max_diff:
                max_diff = abs(a[i] - b[i])
        return max_diff
        
    def primal_model_method(self) -> None:
        gm = GeneralModel(self.conn)
        gm.fix_vars("upper", 0)
        gm.set_obj("primal")
        gm.primal_padm_model.activate_upper_limit(False)
        gm.primal_padm_model.model.optimize()
        output = gm.attacked_model.get_output()
        return(output)
    
    def dual_model(self) -> None:
        gm = GeneralModel(self.input)
        gm.dual_padm_model.optimize()
        print("DUAL:  ")
        print(gm.obj["dual"].getValue())

    
    def PADM_attack(self, PADM_params: PADM_Params, attack_params: Attack_Params) -> None:
        gm = GeneralModel(self.input, attack_params)
        gm.primal_padm_model.model.setObjective(gm.obj["primal"])
        
        gm.fix_vars("upper", 0)
        print("############ solve initial model ############")
        gm.primal_padm_model.solve()
        gm.dual_padm_model.setObjective(gm.obj["dual"], GRB.MAXIMIZE)
        gm.dual_padm_model.optimize()
        gm.relax_vars("upper")
        primal_values = gm.get_MVar_values("primal")
        dual_values = gm.get_MVar_values("dual")
        upper_level_values = gm.get_MVar_values("upper")
        logging.info(f"primal obj: , {gm.get_obj_value('primal')}")
        logging.info(f"dual obj: , {gm.get_obj_value('dual')}")
        mu = PADM_params.initial_mu
        i = 0 # outer loop counter
        primal_obj_value = float("inf")
        dual_obj_value = - float("inf")
        algorithm_dict = {"cap_active":[], "obj":[]}
        while abs(primal_obj_value - dual_obj_value) > PADM_params.penalty_error and i < PADM_params.max_penalty_iter:
            i += 1
            logging.info(f"i = {i}")
            j = 0
            while True:
                def save_algorithm_state():
                    cap_active = {}
                    cap_active["dual"] = cap_active_dual
                    cap_active["primal"] = cap_active_primal
                    obj = {}
                    obj["upper"] = gm.get_obj_value('upper')
                    obj["primal"] = primal_obj_value
                    obj["dual"] = dual_obj_value
                    algorithm_dict["cap_active"].append(cap_active)
                    algorithm_dict["obj"].append(obj)
                break_flag = False
                if j > 0 and self.diff_values(upper_level_values, old_upper_values) < PADM_params.stationary_error:
                    break_flag = True 
                j += 1
                logging.info(f"j = {j}")
                old_upper_values = gm.get_MVar_values("upper")
                output_delta = gm.primal_padm_model.get_output()
                gm.primal_model.set_coeff(output_delta)
                gm.primal_model.activate_upper_limit(False)
                logging.info("############ solve dual ############")
                gm.primal_model.solve()
                # save cap_active
                cap_active_dual = gm.primal_model.get_output().power.Cap_active
                cap_active_dual = {y:cap_active_dual[cs,y] for (cs,y) in cap_active_dual if cs == gm.primal_model.attacked_cs}

                dual_obj_value = gm.primal_model.model.getObjective().getValue()
                logging.info(f"dual obj: , {dual_obj_value}")
                output_dual = gm.primal_model.get_output()
                gm.primal_model.activate_upper_limit(True)
                logging.info("############ solve primal ############")
                gm.primal_model.solve()
                # save cap_active
                cap_active_primal = gm.primal_model.get_output().power.Cap_active
                cap_active_primal = {y:cap_active_primal[cs,y] for (cs,y) in cap_active_primal if cs == gm.primal_model.attacked_cs}
                
                primal_obj_value = gm.primal_model.model.getObjective().getValue()
                logging.info(f"primal obj: , {primal_obj_value}")
                if abs(primal_obj_value - dual_obj_value) < PADM_params.penalty_error:
                    break_flag = True
                    
                if break_flag:    
                    save_algorithm_state()
                    break
                output_primal = gm.primal_model.get_output()
                gm.set_coeff(output_primal)
                k = 0 # inner loop counter
                while True:
                    k += 1
                    logging.info(f"k = {k}")
                    logging.info("####### solve primal #######")
                    gm.set_primal_obj(mu, output_dual)
                    gm.primal_padm_model.solve()
                    logging.info(f"primal obj: , {gm.get_obj_value('primal')}")
                    logging.info(f"real dual: , {gm.get_obj_value('dual_real')}")
                    logging.info(f"dual obj: , {gm.get_obj_value('dual')}")
                    logging.info(f"upper obj: , {gm.get_obj_value('upper')}")
                    new_primal_values = gm.get_MVar_values("primal")
                    new_upper_values = gm.get_MVar_values("upper")
                    logging.info("####### solve dual #######")
                    gm.set_dual_obj(output_dual)
                    gm.dual_padm_model.optimize()
                    logging.info(f"primal obj: , {gm.get_obj_value('primal')}")
                    logging.info(f"real dual: , {gm.get_obj_value('dual_real')}")
                    logging.info(f"dual obj: , {gm.get_obj_value('dual')}")
                    logging.info(f"upper obj: , {gm.get_obj_value('upper')}")
                    logging.info("####### diff #######")
                    new_dual_values = gm.get_MVar_values("dual")
                    # compare the new values with the old ones and the old gets the new
                    # if the difference is less than the threshold it is in a stationary point
                    # else continue the iterative process
                    primal_diff = self.diff_values(primal_values, new_primal_values)
                    logging.info(f"primal_diff: , {primal_diff}")
                    dual_diff = self.diff_values(dual_values, new_dual_values)
                    logging.info(f"dual_diff: , {dual_diff}")
                    upper_level_diff = self.diff_values(upper_level_values, new_upper_values)
                    logging.info(f"upper_level_diff: , {upper_level_diff}")
                    diff = max(primal_diff, dual_diff, upper_level_diff)
                    logging.info(f"diff: , {diff}")
                    primal_values = new_primal_values
                    dual_values = new_dual_values
                    upper_level_values = new_upper_values
                    if diff < PADM_params.stationary_error or k >= PADM_params.max_stationary_iter:
                        break
            mu *= PADM_params.increase_factor
        export = {"output": gm.primal_padm_model.get_output(), "input": gm.primal_model.data}
        with open(Path(".").joinpath("Runs","DEModel_V2-Base-attack","input_output" + GeneralModel.gen_file_name(attack_params) +".pkl"), "wb") as f:
            pickle.dump(export,f)
        with open(Path(".").joinpath("Runs","DEModel_V2-Base-attack","algorithm" + GeneralModel.gen_file_name(attack_params) +".pkl"), "wb") as f:
            pickle.dump(algorithm_dict,f)
