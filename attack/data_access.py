from Core.data_access import DAO
from sqlite3 import Connection

class AttackDAO(DAO):
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        self.output_index_dict["Upper"] = ['T']