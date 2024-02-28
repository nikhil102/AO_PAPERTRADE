class SELECT:
    query = ''
    def __init__(self,Table_Name):
        self.Table_Name = Table_Name
        
    def ALL_COLUMNS(self):
        self.query += f""" SELECT * FROM {self.Table_Name}"""
        return self
    
    def COLUMN(self, columns):
        column_names = ', '.join(columns)
        self.query += f"SELECT {column_names} FROM {self.table_name}"
        return self
          
    def WHERE(self, conditions):
        where_clause = ' AND '.join([f"{key} = '{value}'" for key, value in conditions.items()])
        self.query += f" WHERE {where_clause}"
        return self
    
    def QUERY(self):
        return str(self.query) + ';' if self.query !='' and self.query !=None else ''  
        
class UPDATE:
    def __init__(self,Table_Name):
        self.Table_Name = Table_Name
        
    def T_DATE(self):
        return f""" UPDATE {self.table_name} SET T_DATE = CURDATE() WHERE ke = 'NIK'; """
    
    def QUERY1(self, data, condition):
        columns_values = ', '.join([f"{key} = '{value}'" for key, value in data.items()])
        update_query = f"UPDATE LIVE_TRADE_OPT SET {columns_values} WHERE {condition}"
        return update_query
            
class INSERT:
    
    def __init__(self, table_name):
        self.table_name = table_name

    def QUERY(self, columns, custom_columns= {} ):
        col_vals_lists = [custom_columns[column] if column in custom_columns else f'%({column})s' for column in columns]
        column_names = ', '.join(columns)
        placeholders = ', '.join(col_vals_lists)
        insert_query = f"INSERT INTO {self.table_name} ({column_names}) VALUES ({placeholders})"
        return insert_query
    
    def QUERY_WITH_CUSTOM_PLACE_HOLDER(self, data):
        placeholders = ', '.join(['%s'] * len(data))
        columns = ', '.join(data.keys())
        insert_query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        return insert_query
    
    @classmethod
    def WHERE(cls, conditions):
        where_clause = ' AND '.join([f"{key} = '{value}'" for key, value in conditions.items()])
        return f" WHERE {where_clause}"

class CUSTOM_SELECT:
    def __init__(self,Table_Name):
        self.Table_Name = Table_Name

    def Check_expiry_status(self):
        return f""" SELECT DATE_FORMAT(CURDATE(), '%Y-%m-%d') <= FUT_EXPIRY_DATE AS FUT_EX_OVER, DATE_FORMAT(CURDATE(), '%Y-%m-%d') <= OPT_EXPIRY_DATE AS OPT_EX_OVER FROM {self.Table_Name}; """

