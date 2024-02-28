from datetime import datetime
import pandas as pd
import uuid

# CUSTOM
from CONFIG import APP as APPCONFIG
import LIB_FUN_HELPER as HELPER
import LIB_MDB
import LIB_AO_API as AO
import LIB_S3 as S3L
import LIB_LOGGER as LOG

INNER_MODULE_NAME = 'METHOD_EVERY_MIN_PRO' 
TIMEFRAME_LS = ['1_MIN', '5_MIN', '15_MIN', '30_MIN', '1_HOUR']
SIGNALS_lST = []
timeframe_dict = {'1_MIN': '1m', '5_MIN': '5m', '15_MIN': '15m', '30_MIN': '30m', '1_HOUR': '1h'}
i_obj_key = ['RECOMMENDATION','BUY','SELL','NEUTRAL']
i_signalobj_key = ['SINGAL','B','S','N']
signalobj_key_dict = dict(zip(i_signalobj_key, i_obj_key))
Quantity_dict = {'1_MIN': 1, '5_MIN': 2, '15_MIN': 3 , '30_MIN': 5 , '1_HOUR': 7 }

UID,T_SIGNAL,TRADE_TYPE = "","",""
TRADE_STATUS = "OPEN"
TRADE_LOT = 0
TS_TF = ''

C_T_O = {}
Signalslst = []
C_T_O['STRONG_BUY'] = ['STRONG_SELL', 'SELL']
C_T_O['BUY'] = ['STRONG_SELL', 'SELL']
C_T_O['NEUTRAL'] = ['STRONG_BUY','STRONG_SELL','BUY','SELL']
C_T_O['ERROR'] = ['STRONG_BUY','STRONG_SELL','BUY','SELL']
C_T_O['NO_RESPONSE'] = ['STRONG_BUY','STRONG_SELL','BUY','SELL']
C_T_O['CLOSE_ALL_MARKET_TIMEOUT'] = ['STRONG_BUY','STRONG_SELL','BUY','SELL']
C_T_O['STRONG_SELL'] = ['STRONG_BUY', 'BUY']
C_T_O['SELL'] = ['STRONG_BUY', 'BUY']

SIGNALS_LIST = ['STRONG_BUY', 'BUY', 'NEUTRAL', 'SELL', 'STRONG_SELL']
DF_PART_LST = ['STRONG_BUY', 'BUY', 'SELL', 'STRONG_SELL']
NO_ACT_EXIT_MARKET_SIGNALS = ['NEUTRAL', 'ERROR', 'NO_RESPONSE','CLOSE_ALL_MARKET_TIMEOUT']

def EXTRACT_FROM_PULL_OBJECT_SIGNALS_AND_FUTURE_PRICE(temp_BI_OBJ):
    FPRICE, SIGNAL = 0 ,''
    if temp_BI_OBJ:
        if 'FPRICE' in temp_BI_OBJ:
            FPRICE = temp_BI_OBJ['FPRICE'] 
        if 'TA_SIGNAL' in temp_BI_OBJ:
            SIGNAL = temp_BI_OBJ['TA_SIGNAL']
        return SIGNAL,FPRICE

def ENTER_TRADE_DATA_MAKING(SIG, O_CSP ,O_PSP, MULTIFI):
    TTYPE = 'BUY' if SIG in ['BUY','STRONG_BUY'] else 'SELL'
    TCEPE = 'CE' if TTYPE == 'BUY' else 'PE'
    TOSP =  O_CSP if TCEPE == 'CE' else O_PSP
    TSQ = 1 if SIG in ['BUY','SELL'] else 2
    TRADE_LOT = MULTIFI * TSQ
    return TTYPE ,TCEPE ,TOSP, TSQ, TRADE_LOT

def ENTER_TRADE(UID,TS_TF,TRADE_TYPE,EN_T_SIGNAL,EN_FUT_PRICE,T_CE_PE,OPT_STRIKE_PRICE,OPT_SYMBOL,OPT_TOKEN,EN_OPT_PRICE,TRADE_STATUS,TRADE_LOT,C_NUM):
    variable_dict = {}
    variable_dict['UID'] = UID
    variable_dict['TS_TF'] = TS_TF
    variable_dict['TRADE_TYPE'] = TRADE_TYPE
    variable_dict['EN_T_SIGNAL'] = EN_T_SIGNAL
    variable_dict['EN_FUT_PRICE'] = EN_FUT_PRICE
    variable_dict['OPT_STRIKE_PRICE'] = OPT_STRIKE_PRICE
    variable_dict['OPT_SYMBOL'] = OPT_SYMBOL
    variable_dict['OPT_TOKEN'] = OPT_TOKEN
    variable_dict['EN_OPT_PRICE'] = EN_OPT_PRICE
    variable_dict['TRADE_STATUS'] = TRADE_STATUS
    variable_dict['TRADE_LOT'] = TRADE_LOT
    variable_dict['T_DAY'] = APPCONFIG.TODAY_DATE.day
    variable_dict['T_MONTH'] = APPCONFIG.TODAY_DATE.month
    variable_dict['T_YEAR'] = APPCONFIG.TODAY_DATE.year
    variable_dict['T_DATE'] = APPCONFIG.TODAY_DATE_FORM1
    variable_dict['T_CE_PE'] = T_CE_PE
    variable_dict['EX_OPT_PRICE'] = 0
    variable_dict['EX_T_SIGNAL'] = ''
    variable_dict['EX_FUT_PRICE'] = 0
    variable_dict['EN_C_NUM'] = C_NUM
    variable_dict['EX_C_NUM'] = 0
    variable_dict['UPDATED_DATETIME'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variable_dict['CREATE_DATETIME'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    res = LIB_MDB.T_insert_into_LIVE_TRADE_OPT(variable_dict)
    return res

def EXIT_TRADE(RUID,EX_T_SIGNAL,EX_FUT_PRICE,EX_OPT_PRICE,C_NUM):
    data_to_update = {
        "EX_C_NUM": C_NUM,
        "EX_T_SIGNAL": EX_T_SIGNAL,
        "EX_FUT_PRICE": EX_FUT_PRICE,
        "EX_OPT_PRICE": EX_OPT_PRICE,
        "TRADE_STATUS": "CLOSE",
        "UPDATED_DATETIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    res = LIB_MDB.T_update_LIVE_TRADE_OPT(data_to_update, f"UID ='{RUID}'")
    return res
      
def Every_Minute_PROCESS(FUTC,opt_t_ce_df,opt_t_pe_df):

    SID = str(uuid.uuid4())
    if opt_t_ce_df.empty or opt_t_pe_df.empty:
       if opt_t_ce_df.empty:
          LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'CRITICAL_ERROR',f"OPTION TOKEN CE DATA FRME is empty")
          exit() 
       if opt_t_ce_df.empty:
          LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'CRITICAL_ERROR',f"OPTION TOKEN PE DATA FRME is empty")
          exit() 
            
    FLAG_NEW_TRADE_STOP, FLAG_CLOSE_ALL_TRADE = HELPER.Check_Market_stop_new_entry_and_close_all_timeout()
    
    C_NUM = HELPER.C_NUM_INCREMENT()
    Signalslst = []
    OPEN_TRADES_OBJ = LIB_MDB.T_check_open_trades()
    OPEN_TRADES_Data = {}
    OPEN_TRADESDB = {}
    OPEN_TRADES_DF = pd.DataFrame()
    
    if HELPER.check_response_is_success(OPEN_TRADES_OBJ):
        if 'Data' in OPEN_TRADES_OBJ:
            OPEN_TRADESDB = OPEN_TRADES_OBJ['Data']
            if OPEN_TRADESDB:
                OPEN_TRADES_DF = pd.DataFrame(OPEN_TRADESDB)
                
    for TF in TIMEFRAME_LS:
        TS_TF = TF
        UID, TRADE_TYPE, EN_T_SIGNAL= "", "", ""
        OSP, TRADE_LOT, EN_FUT_PRICE, SQ = 0, 0, 0, 0
        UID = str(uuid.uuid4())
        Tinterval = timeframe_dict[TF]
        PULL_OBJ = HELPER.Ta_handler_obj(Tinterval)
        PULL_OBJ['TF'] = TS_TF
        PULL_OBJ['UID'] = UID
        PULL_OBJ['SID'] = SID
        PULL_OBJ['CSP'] = 0
        PULL_OBJ['PSP'] = 0
        PULL_OBJ['UPDATED_DATE_TIME'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        EN_T_SIGNAL,FPRICE = EXTRACT_FROM_PULL_OBJECT_SIGNALS_AND_FUTURE_PRICE(PULL_OBJ)
        if FLAG_CLOSE_ALL_TRADE:
           EN_T_SIGNAL = 'CLOSE_ALL_MARKET_TIMEOUT'  
           PULL_OBJ['TA_SIGNAL'] = 'CLOSE_ALL_MARKET_TIMEOUT'
           
        EN_FUT_PRICE = FPRICE
        CSP, PSP = HELPER.CAL_OPT_SP_F_PRI(EN_FUT_PRICE)
        CE_F = pd.DataFrame()
        PE_F = pd.DataFrame()
        PULL_OBJ['CSP'] = CSP
        PULL_OBJ['PSP'] = PSP
        Signalslst.append(PULL_OBJ)
        
        CE_C_SYMBOL, CE_C_TOKEN = '',''
        PE_C_SYMBOL, PE_C_TOKEN = '',''
        OPT_SYMBOL, OPT_TOKEN = '',''
        EN_OPT_PRICE, EX_OPT_PRICE = 0, 0
                
        CE_F = opt_t_ce_df[(opt_t_ce_df["strike"] == CSP)]
        PE_F = opt_t_pe_df[(opt_t_pe_df["strike"] == PSP)]

        if not CE_F.empty:
           CE_C_SYMBOL = CE_F.iloc[0]["symbol"]
           CE_C_TOKEN = CE_F.iloc[0]["token"]
        else:
           LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"NOT ABLE TO FIND THE CE CURRENT STRIKE PRICE IN CE TOKEN DATA FRAME")
           continue

        if not PE_F.empty:
           PE_C_SYMBOL = PE_F.iloc[0]["symbol"]
           PE_C_TOKEN = PE_F.iloc[0]["token"]
        else:
           
           LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"NOT ABLE TO FIND THE PE CURRENT STRIKE PRICE IN PE TOKEN DATA FRAME")
           continue
        
        MULTIFIER = Quantity_dict[TF]
        if OPEN_TRADES_DF.empty:
            if not EN_T_SIGNAL in NO_ACT_EXIT_MARKET_SIGNALS:
                                
                TRADE_TYPE,T_CE_PE,OSP,SQ,TRADE_LOT = ENTER_TRADE_DATA_MAKING(EN_T_SIGNAL,CSP,PSP,MULTIFIER)
                OPT_SYMBOL = CE_C_SYMBOL if T_CE_PE == 'CE' else PE_C_SYMBOL
                OPT_TOKEN = CE_C_TOKEN if T_CE_PE == 'CE' else PE_C_TOKEN
                
                if OPT_SYMBOL != '' and OPT_TOKEN != '':
                    LTP_OBJ = HELPER.R_to_get_ltp(OPT_SYMBOL,OPT_TOKEN)
                    print(LTP_OBJ)
                    if LTP_OBJ:
                       if 'ltp' in LTP_OBJ:
                          LTP = LTP_OBJ['ltp']
                          if LTP > 0: 
                             EN_OPT_PRICE = LTP
                             if FLAG_NEW_TRADE_STOP == False:
                                RE = ENTER_TRADE(UID,TS_TF,TRADE_TYPE,EN_T_SIGNAL,EN_FUT_PRICE,T_CE_PE,OSP,OPT_SYMBOL,OPT_TOKEN,EN_OPT_PRICE,TRADE_STATUS,TRADE_LOT,C_NUM)
                             else:
                                LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERRORINFO',f"STOP FOR ENTER IN NEW TRADE -- 9-15 AM TO 3-15 PM Allowed for new trade ")
                          else:
                            LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE LESS THEN 0")
                            continue     
                       else:
                          LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE GetError NOT FINDING KEY IN LTP OBJECT")
                          continue
                    else:
                        LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_SYMBOL or OPT_TOKEN GetError WHILE ENTER INTO TRADE")
                        continue
                else:
                   LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_SYMBOL or OPT_TOKEN GetError")
                   continue
        else:
            
            OPEN_TRADES_DF_FILTER_BY_TF = pd.DataFrame() 
            OPEN_TRADES_DF_FILTER_BY_TF = OPEN_TRADES_DF[(OPEN_TRADES_DF["TS_TF"] == TF)]
            # CLOSE TRADE 
            close_trade_order_list = []
            if C_T_O:
                if EN_T_SIGNAL in C_T_O:
                    close_trade_order_list =  C_T_O[EN_T_SIGNAL]
                    if close_trade_order_list:
                        for index, row in OPEN_TRADES_DF_FILTER_BY_TF.iterrows():
                            row_UID =  row['UID']
                            row_EN_T_SIGNAL =  row['EN_T_SIGNAL']
                            row_OPT_SYMBOL =  row['OPT_SYMBOL']
                            row_OPT_TOKEN =  row['OPT_TOKEN']
                            row_EN_OPT_PRICE =  row['EN_OPT_PRICE']
                            row_T_CE_PE =  row['T_CE_PE']
                            if row_OPT_SYMBOL != '' and row_OPT_TOKEN != '' and row_EN_OPT_PRICE > 0:
                               EXIT_LTP_OBJ = HELPER.R_to_get_ltp(row_OPT_SYMBOL,row_OPT_TOKEN) 
                               if row_EN_T_SIGNAL in close_trade_order_list:
                                    if EXIT_LTP_OBJ:
                                       if 'ltp' in EXIT_LTP_OBJ:
                                           EX_LTP = EXIT_LTP_OBJ['ltp']
                                           if EX_LTP > 0:
                                              EX_OPT_PRICE = EX_LTP 
                                              EXIT_TRADE(row_UID,EN_T_SIGNAL,FPRICE,EX_OPT_PRICE,C_NUM)
                                           else:
                                              LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE LESS THEN 0 WHILE EXIT THE TRADE")
                                              continue 
                                       else:
                                            LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE GetError NOT FINDING KEY IN LTP OBJECT WHILE EXIT THE TRADE")
                                            continue
                                    else:
                                        LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE GetError EXIT_LTP_OBJ iS EMPTY WHILE EXIT THE TRADE")
                                        continue
                            else:
                                LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"row_OPT_SYMBOL or row_OPT_TOKEN or row_EN_OPT_PRICE GetError WHILE EXIT INTO TRADE")
                                continue
            
            if not EN_T_SIGNAL in NO_ACT_EXIT_MARKET_SIGNALS:
                CHK_SAME_DIR_TRADE_DF = OPEN_TRADES_DF_FILTER_BY_TF[(OPEN_TRADES_DF_FILTER_BY_TF["EN_T_SIGNAL"] == EN_T_SIGNAL)]
                if CHK_SAME_DIR_TRADE_DF.empty:
                   TRADE_TYPE,T_CE_PE,OSP,SQ,TRADE_LOT = ENTER_TRADE_DATA_MAKING(EN_T_SIGNAL,CSP,PSP,MULTIFIER)
                   OPT_SYMBOL = CE_C_SYMBOL if T_CE_PE == 'CE' else PE_C_SYMBOL
                   OPT_TOKEN = CE_C_TOKEN if T_CE_PE == 'CE' else PE_C_TOKEN
                   if OPT_SYMBOL != '' and OPT_TOKEN != '':
                      LTP_OBJ = HELPER.R_to_get_ltp(OPT_SYMBOL,OPT_TOKEN) 
                      if LTP_OBJ:
                         if 'ltp' in LTP_OBJ:
                            LTP = LTP_OBJ['ltp']
                            if LTP > 0: 
                                EN_OPT_PRICE = LTP
                                if FLAG_NEW_TRADE_STOP == False:
                                   RE = ENTER_TRADE(UID,TS_TF,TRADE_TYPE,EN_T_SIGNAL,EN_FUT_PRICE,T_CE_PE,OSP,OPT_SYMBOL,OPT_TOKEN,EN_OPT_PRICE,TRADE_STATUS,TRADE_LOT,C_NUM)
                                   if RE:
                                      if 'Status' in RE:
                                         if RE['Status'] == 'ERROR':
                                            LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'CRITICAL_ERROR',f"ENTER_TRADE FUNCTION RETUNING STATUS ERROR")                                    
                                   else:
                                      LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'CRITICAL_ERROR',f"ENTER_TRADE FUNCTION RETURN OBJECT IS EMPTY")

                                else:
                                   LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERRORINFO',f"STOP FOR ENTER IN NEW TRADE -- 9-15 AM TO 3-15 PM Allowed for new trade")
                            else:
                                LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE LESS THEN 0 WHILE ENTER INTO TRADE")
                                continue     
                         else:
                            LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE GetError NOT FINDING KEY IN LTP OBJECT WHILE ENTER INTO TRADE")
                            continue
                      else:
                          LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_PRICE GetError LTP_OBJ iS EMPTY WHILE ENTER INTO TRADE")
                          continue
                   else:
                        LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'ERROR',f"OPT_SYMBOL or OPT_TOKEN GetError WHILE ENTER INTO TRADE")
                        continue
    
    if Signalslst:
       res = LIB_MDB.Insert_Bulk_Data_Into_SINGALS_TA_PULL_Table_by_Dict(Signalslst)
       if res:
          if 'Status' in res:
             if res['Status'] == 'ERROR':
               LOG.ADD_ERR_LOG_INTO_DB(INNER_MODULE_NAME,'CRITICAL_ERROR',f"SINGALS FAILED to insert into SINGALS_TA_PULL table")                 