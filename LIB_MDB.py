import mysql.connector
from datetime import datetime
# CUSTOM
from CONFIG import APP as APPCONFIG
from CONFIG import SQL_QUERY as Q
from CONFIG import SQL_TABLES as TC
import LIB_QFIRE as QF
import LIB_FUN_HELPER as HELPER


def Insert_Data_Into_EXP_CONFIG_Table_by_Dict(data_dict):
    CURR_T_O = TC.TABLEOBJ.create('EXP_CONFIG')
    QUERY  = Q.INSERT(CURR_T_O.Name).QUERY(CURR_T_O.Column1,CURR_T_O.Custom_Col_Q1)
    return QF.INSERT_DICT_DATA(QUERY,data_dict)

def Insert_Data_Into_CURR_APP_LOG_Table_by_Dict(data_dict):
    CURR_T_O = TC.TABLEOBJ.create('CURR_APP_LOG')
    QUERY  = Q.INSERT(CURR_T_O.Name).QUERY(CURR_T_O.Column1,CURR_T_O.Custom_Col_Q1)
    return QF.INSERT_DICT_DATA(QUERY,data_dict)

def Insert_Data_Into_CURR_ERROR_LOG_Table_by_Dict(data_dict):
    CURR_T_O = TC.TABLEOBJ.create('CURR_ERROR_LOG')
    QUERY  = Q.INSERT(CURR_T_O.Name).QUERY(CURR_T_O.Column1,CURR_T_O.Custom_Col_Q1)
    return QF.INSERT_DICT_DATA(QUERY,data_dict)

def Insert_Data_Into_SINGALS_TA_PULL_Table_by_Dict(data_dict):
    CURR_T_O = TC.TABLEOBJ.create('SINGALS_TA_PULL')
    QUERY  = Q.INSERT(CURR_T_O.Name).QUERY(CURR_T_O.Column1,CURR_T_O.Custom_Col_Q1)
    return QF.INSERT_DICT_DATA(QUERY,data_dict)

def Insert_Bulk_Data_Into_SINGALS_TA_PULL_Table_by_Dict(data_dict_lst):
    CURR_T_O = TC.TABLEOBJ.create('SINGALS_TA_PULL')
    QUERY  = Q.INSERT(CURR_T_O.Name).QUERY(CURR_T_O.Column1)
    return QF.INSERT_DICT_DATA(QUERY,data_dict_lst,'MANY')
           
def T_check_open_trades():
    QUERY  = Q.SELECT('LIVE_TRADE_OPT').ALL_COLUMNS().WHERE({"TRADE_STATUS":"OPEN"}).QUERY()
    RES = QF.SELECT(QUERY,'DICTIONARY','ALL')
    return RES
    
def T_insert_into_LIVE_TRADE_OPT(data):
    CURR_T_O = TC.TABLEOBJ.create('LIVE_TRADE_OPT')
    QUERY  = Q.INSERT(CURR_T_O.Name).QUERY_WITH_CUSTOM_PLACE_HOLDER(data)
    return QF.INSERT_LIST_VALUE_DATA(QUERY,data)

def T_update_LIVE_TRADE_OPT(data, condition):
    CURR_T_O = TC.TABLEOBJ.create('LIVE_TRADE_OPT')
    QUERY  = Q.UPDATE(CURR_T_O.Name).QUERY1(data, condition)
    return QF.UPDATE_QUERY(QUERY)
