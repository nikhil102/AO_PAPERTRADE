from typing import Dict
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import pickle
import ujson
# CUSTOM
from CONFIG import APP as APPCONFIG
import LIB_FUN_HELPER as HELPER
import LIB_GEN_NEW as GN
import LIB_S3 as S3L
from LIB_OPT_SP_DETAILS import FUT_PRICE_SP_DETAIL as FPSD
import LIB_LOGGER as LOG

Check_Updated_Time_ByPass = True
Check_MARKET_IS_OPEN_TODAY_ByPass = False

FPSD = FPSD()

def VALIDATE():
   MODULE_NAME = 'TOKEN VALIDATOR SCRIPT'
   HELPER.EMPTY_ALL_INIT_DIRECTORY()
   
   Key1, Key2, key3, key4 = "UPDATED_DATE_TIME", "MARKET_IS_OPEN_TODAY", "OPT_EXPIRY_DATE_STR", "Data"
   FUT_FILE_DICT, FUT_FILE_OBJ, FUT_FILE_DATA  = {}, {}, {}
   CHECKS_1, CHECKS_2, FILE_CHECKS_CE, FILE_CHECKS_PE, NOT_CE_SP_MISSING, NOT_PE_SP_MISSING  = False, False, False, False, True, True
   FUT_FILE_DICT = S3L.read_s3_file(APPCONFIG.CURRENT_JSON_TRADING_CON)
   
   if FUT_FILE_DICT is not None:
      if key4 in FUT_FILE_DICT:
         FUT_FILE_DATA = ujson.loads(FUT_FILE_DICT[key4])       
         if Key1 in FUT_FILE_DATA:
            UPDATED_DATE_TIME = FUT_FILE_DATA[Key1]
            if Check_Updated_Time_ByPass == False:
               if HELPER.CHECK_FUTURE_DATA_UPDATETIME(UPDATED_DATE_TIME) != False:
                  CHECKS_1 = True
               else:
                  LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"UPDATED_DATE_TIME CHECK FAILED and FUT_FILE_DATA not updated AFTER 9:07 AM TODAY")
                  exit()
            else:
               LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'WARNING',"BYPASSED CHECK FOR UPDATE DATE TIME GRATER THEN TODAY 9:07 AM")
               CHECKS_1 = True            

         else:
            LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',f"FUT_FILE_DATA object {Key1} key not found")
            exit()

         if Key2 in FUT_FILE_DATA:
            MARKET_IS_OPEN_TODAY = FUT_FILE_DATA[Key2]
            if Check_MARKET_IS_OPEN_TODAY_ByPass == False:
                  if MARKET_IS_OPEN_TODAY == "YES":
                     CHECKS_2 = True
                  else:
                     LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'ERROR_INFO',"MARKET IS CLOSED TODAY")
                     exit()
            else:
               LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'WARNING',"BYPASSED CHECK FOR MARKET IS OPEN")
               CHECKS_2 = True
         else:
            LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',f"FUT_FILE_DATA object {Key2} key not found")
            exit()
      else:
         LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',f"FUT_FILE_DICT object {key4} key not found")
         exit()

   else:
      LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"FUT_FILE_DICT - S3L.read_s3_file is empty")
      exit()
   
 

   if CHECKS_1 == True and CHECKS_2 == True and key3 in FUT_FILE_DATA:
      CE_PK_FILE_NAME = HELPER.FILE_NAME_FOR_CE_S_TOKENS(FUT_FILE_DATA[key3])
      PE_PK_FILE_NAME = HELPER.FILE_NAME_FOR_PE_S_TOKENS(FUT_FILE_DATA[key3])
      CE_PKL_OBJ = S3L.read_pickle_from_s3_to_dataframe(CE_PK_FILE_NAME)
      PE_PKL_OBJ = S3L.read_pickle_from_s3_to_dataframe(PE_PK_FILE_NAME)
      
      if CE_PKL_OBJ:
         if 'Status' in CE_PKL_OBJ and 'Data' in CE_PKL_OBJ:
            if CE_PKL_OBJ['Status'] == 'SUCCESS': 
               if 'CSP_UP' in FPSD and 'CSP_DOWN' in FPSD:
                  if FPSD['CSP_UP'] > 0 and  FPSD['CSP_DOWN'] > 0:
                     CSP_UP = FPSD['CSP_UP']
                     CSP_DOWN = FPSD['CSP_DOWN']
                     CUD = CSP_UP - CSP_DOWN
                     CSP_D = CSP_DOWN
                     CSP_U = CSP_UP
                     CE_DF = PE_PKL_OBJ['Data']
                     for i in range(0,round(CUD/100)+1):
                           CE_DF[(CE_DF["strike"] == CSP_D)]
                           CSP_D = CSP_D + 100
                           if not CE_DF.empty:
                              if len(CE_DF) > 0:
                                 continue
                              else:
                                 NOT_CE_SP_MISSING = False
                                 LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_PKL_OBJ IS CE STRIKE PRICE MISSING")
                                 break 
                           else: 
                              NOT_CE_SP_MISSING = False
                              LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_PKL_OBJ IS CE STRIKE PRICE MISSING")
                              break  
                  else:
                        LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR'," CSP_UP or CSP_DOWN VALUE is NOT GREATER THAN 0")
                        exit()                 
               else:
                     LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CSP_UP or CSP_DOWN key is NOT FOUND IN  FPSD - FUT_PRICE_SP_DETAIL")
                     exit()              
            else:
                  LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_PKL_OBJ Status is NOT SUCCESS")
                  exit()   
         else:
            LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_PKL_OBJ NOT FOUND STATUS OR DATA KEY")
            exit()                            
      else:
         LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CE_PKL_OBJ is empty")
         exit()        
         
      if PE_PKL_OBJ:
         if 'Status' in PE_PKL_OBJ and 'Data' in PE_PKL_OBJ:  
            if PE_PKL_OBJ['Status'] == 'SUCCESS':    
               if 'PSP_UP' in FPSD and 'PSP_DOWN' in FPSD:
                  if FPSD['PSP_UP'] > 0 and  FPSD['PSP_DOWN'] > 0: 
                     PSP_UP = FPSD['PSP_UP']
                     PSP_DOWN = FPSD['PSP_DOWN']
                     PUD = PSP_UP - PSP_DOWN
                     PSP_D = PSP_DOWN
                     PSP_U = PSP_UP
                     PE_DF = PE_PKL_OBJ['Data']
                     for i in range(0,round(PUD/100)+1):
                           PE_DF[(PE_DF["strike"] == PSP_D)]
                           PSP_D = PSP_D + 100
                           if not PE_DF.empty:
                              if len(PE_DF) > 0:
                                 continue
                              else:
                                 NOT_PE_SP_MISSING = False
                                 LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PE_PKL_OBJ IS PE STRIKE PRICE MISSING")
                                 break 
                           else: 
                              NOT_PE_SP_MISSING = False
                              LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PE_PKL_OBJ IS PE STRIKE PRICE MISSING")
                              break                  
                  else:
                        LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PSP_UP or PSP_DOWN VALUE is NOT GREATER THAN 0")
                        exit()     
               else:
                     LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PSP_UP or PSP_DOWN key is NOT FOUND IN  FPSD - FUT_PRICE_SP_DETAIL")
                     exit()             
            else:
                  LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PE_PKL_OBJ Status is NOT SUCCESS")
                  exit() 
         else:
               LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PE_PKL_OBJ NOT FOUND STATUS OR DATA KEY")
               exit()         
      else:
         LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PE_PKL_OBJ is empty")
         exit()                    
      
      CELFN_DF , PELFN_DF = pd.DataFrame(),pd.DataFrame()
      if NOT_CE_SP_MISSING  == True:
         if HELPER.check_response_is_success(CE_PKL_OBJ): 
            CELFN_DF = CE_PKL_OBJ.get(key4)
            if CELFN_DF.empty:
               LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"CELFN_DF CE_PKL_OBJ data object dataframe is empty")
               exit()  
            else:
               FILE_CHECKS_CE = True

      if NOT_PE_SP_MISSING  == True:       
         if HELPER.check_response_is_success(PE_PKL_OBJ): 
            PELFN_DF = PE_PKL_OBJ.get(key4)
            if PELFN_DF.empty:
               LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"PELFN_DF PE_PKL_OBJ data object dataframe is empty")
               exit()
            else:
               FILE_CHECKS_PE = True

      if FILE_CHECKS_CE == True and FILE_CHECKS_PE == True:
         CELFN_DF.to_pickle(HELPER.PKL_LOCAL_PATH_GEN(CE_PK_FILE_NAME))
         PELFN_DF.to_pickle(HELPER.PKL_LOCAL_PATH_GEN(PE_PK_FILE_NAME))
         with open(APPCONFIG.CURRENT_JSON_TRADING_CON_LOCAL,'wb') as pickle_file:
            pickle.dump(FUT_FILE_DATA, pickle_file)
         res = LOG.ADD_LOG_INTO_DB(MODULE_NAME,'SUCCESS',"TOKEN VALIDATOR SCRIPT IS COMPLETED AND SUCCESSFULLY VALIDATED TOKENS")
         print(res)
      else:
         LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',"FILE_CHECKS_CE or FILE_CHECKS_PE is false")
         HELPER.CREATE_ERROR_FILE_TO_STOP_CRON()
         exit()

   else:
      LOG.ADD_ERR_LOG_INTO_DB(MODULE_NAME,'CRITICAL_ERROR',f"CHECKS_1 or  CHECKS_2 is FALSE OR {key3} NOT FOUND in FUT_FILE_DATA")
      HELPER.CREATE_ERROR_FILE_TO_STOP_CRON()
      exit()
      