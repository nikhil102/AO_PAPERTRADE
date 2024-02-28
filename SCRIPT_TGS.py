from typing import Dict
import pandas as pd
from datetime import datetime, date
from io import BytesIO

# CUSTOM
import LIB_FUN_HELPER as HELPER
import LIB_GEN_NEW as GN
import LIB_LOGGER as LOG
import SCRIPT_VALID as VALIDATOR

MODULE_NAME = 'TOKEN_GEN_SCRIPT'

T_C_DATA, CE_RANGE_R, PE_RANGE_R, Market_Open_Status = {},{},{},"NO"
Market_Open_Status = GN.holiday_check()
CELFN_DF, PELFN_DF = pd.DataFrame(),pd.DataFrame()

T_C_DATA, CELFN_DF, PELFN_DF = GN.GEN_NEW_CONFIG(Market_Open_Status)
if T_C_DATA:
    Response = GN.ADD_DATA_TO_CONFIG_TABLE(T_C_DATA)
    if 'FUT_EXPIRY_DATE_STR' in T_C_DATA and 'FUT_TOKEN' in T_C_DATA and 'OPT_EXPIRY_DATE_STR' in T_C_DATA:
        FUT_LTP_OBJ = HELPER.R_to_get_ltp(T_C_DATA['FUT_EXPIRY_DATE_STR'],T_C_DATA['FUT_TOKEN'])
        if FUT_LTP_OBJ:
           CE_RANGE_R, PE_RANGE_R = GN.OPT_DF_SHORTER(FUT_LTP_OBJ,CELFN_DF,PELFN_DF,T_C_DATA['OPT_EXPIRY_DATE_STR'])
           if CE_RANGE_R and PE_RANGE_R:
              if 'Status' in CE_RANGE_R and 'Status' in PE_RANGE_R:
                  if CE_RANGE_R['Status'] == 'SUCCESS' and PE_RANGE_R['Status'] == 'SUCCESS':
                     LOG.ADD_LOG_INTO_DB(MODULE_NAME,'SUCCESS',"GENRATED TOKENS SCRIPT COMPLETED")
                     VALIDATOR.VALIDATE()
                  else:
                     LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_RANGE_R - Status or PE_RANGE_R - Status any one not find SUCCESS")
                     exit()   
              else:
                  LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_RANGE_R or PE_RANGE_R any one object not find key Status")
                  exit() 
           else:
              LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_RANGE_R or PE_RANGE_R Tokens is empty")
              exit()  
        else:
           LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"FUTURE LAST TRADING PRICE OBJECT IS EMPTY - FUT_LTP_OBJ")
           exit() 
    else:
        LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"TRADING CONFIG DATA OBJECT any one key is not found FUT_EXPIRY_DATE_STR,FUT_TOKEN,OPT_EXPIRY_DATE_STR")
        exit()             
else:
    LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"TRADING CONFIG DATA OBJECT IS EMPTY - T_C_DATA")
    exit() 
