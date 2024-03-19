from sqlite3 import Cursor
from pandas import DataFrame

class Output():
    output_index_dict = {
        "Total_annual_co2_emission": ['Y'],
        "Cap_new": ['CS','Y'],
        "Cap_active": ['CS','Y'],
        "Cap_res": ['CS','Y'],
        "Eouttot": ['CS','Y'],
        "Eintot": ['CS','Y'],
        "E_storage_level_max": ['CS','Y'],
        "Eouttime": ['CS','Y','T'],
        "Eintime": ['CS','Y','T'],
        "Pin": ['CS','Y','T'],
        "Pout": ['CS','Y','T'],
        "E_storage_level": ['CS','Y','T'],
        "Enetgen": ['CO','Y','T'],
        "Enetcons": ['CO','Y','T'],
        "OPEX": [],
        "CAPEX": [],
        "TOTEX": []
    }
    def __init__(self, cursor: Cursor) -> None:
        self.cursor = cursor()
    
    def get_dataframe(self, name: str, **filterby) -> DataFrame:
        # make headers
        headers = []
        for index in self.output_index_dict[name]:
            if index == 'CS':
                headers.append(['cp','cin','cout'])
            elif index == 'CO':
                headers.append('Commodity')
            elif index == 'Y':
                headers.append('Year')
            elif index == 'T':
                headers.append('Time')
            else:
                headers.append(index)
        headers.append('value')
        # add rows
        if self.output_index_dict[name] == []:
            rows = [self.cursor.execute(f"SELECT {name} FROM output_global").fetchone()[0]]
        elif self.output_index_dict[name] == ['Y']:
            rows = self.cursor.execute(f"""
                SELECT y.value, {name} FROM output_y
                JOIN years AS y ON y_id = y.id
            """).fetchall()
        elif self.output_index_dict[name] == ['CS','Y']:
            rows = self.cursor.execute(f"""
                SELECT cp.name, cin.name, cout.name, v.value , {name} FROM output_cs_y
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN years AS y ON y_id = y.id
            """).fetchall()
        elif self.output_index_dict[name] == ['CS','Y','T']:
            rows = self.cursor.execute(f"""
                SELECT cp.name, cin.name, cout.name, y.value, t.value, {name} FROM output_cs_y_t
                JOIN conversion_subprocess AS cs ON cs_id = cs.id
                JOIN conversion_process AS cp ON cs.cp_id = cp.id
                JOIN commodity AS cin ON cs.cin_id = cin.id
                JOIN commodity AS cout ON cs.cout_id = cout.id
                JOIN year AS y ON y_id = y.id
                JOIN time_step AS t ON t_id = t.id
            """).fetchall()
        elif self.output_index_dict[name] == ['CO','Y','T']:
            rows = self.cursor.execute(f"""
                SELECT c.name, y.value, t.value, {name} FROM output_co_y_t
                JOIN commodity AS c ON co_id = c.id
                JOIN year AS y ON y_id = y.id
                JOIN time_step AS t ON t_id = t.id
            """).fetchall()
        df = DataFrame(rows, columns=headers)
        for k, v in filterby.items():
            try:
                df = df[df[k] == v]
            except KeyError:
                raise Exception(f"Key {k} not found in DataFrame! Existing keys: {df.columns}")
        return df

        
        

