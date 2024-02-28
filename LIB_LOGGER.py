import LIB_MDB
from CONFIG import APP as APPCONFIG

def ADD_LOG_INTO_DB(MN, LOG_TYPE, MSG):
    
    LOG_OBJ = {
        'LOG_MODULE_NAME': MN,
        'LOG_TYPE': LOG_TYPE,
        'LOG_MESSAGE': MSG,
        'ENV_TYPE': APPCONFIG.ENV_TYPE,
        'LOG_CREATE_DATE': APPCONFIG.TODAY_DATE_FORM1
    }
    
    RES = LIB_MDB.Insert_Data_Into_CURR_APP_LOG_Table_by_Dict(LOG_OBJ)
    return RES


def ADD_ERR_LOG_INTO_DB(E_MN, ERR_TYPE, ERR_MSG):
    
    ERR_OBJ = {
        'ERR_MODULE_NAME': E_MN,
        'ERR_TYPE': ERR_TYPE,
        'ERR_MESSAGE': ERR_MSG,
        'ENV_TYPE': APPCONFIG.ENV_TYPE,
        'ERR_CREATE_DATE': APPCONFIG.TODAY_DATE_FORM1
    }
    
    RES = LIB_MDB.Insert_Data_Into_CURR_ERROR_LOG_Table_by_Dict(ERR_OBJ)
    return RES