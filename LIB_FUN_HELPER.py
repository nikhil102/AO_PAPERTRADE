from typing import Dict
import ujson
import urllib.request
import pandas as pd
from datetime import datetime, date
import os
import shutil
import pickle
import pytz
import hashlib
from diskcache import FanoutCache
cache = FanoutCache(directory='/tmp/mycache')

# CUSTOM
from CONFIG import APP as APPCONFIG
from LIB_TV import TRADINGVIEW_Handler, Interval, Exchange
import LIB_AO_API as AO

# HELPER FUNCTIONS #

def R_RESPONSE(STATUS, DATA, ERROR):
    r : Dict = {}
    r['Status'] = STATUS
    r['Data'] = DATA
    r['Error_MEG'] = ERROR
    return r

def NO_DATA_RESPONSE_SUCCESS():
    return R_RESPONSE("SUCCESS",{},"")

def RESPONSE_SUCCESS(RESULT):
    return R_RESPONSE("SUCCESS",RESULT,"")

def RESPONSE_ERROR(ERROR):
    return R_RESPONSE("ERROR",{},ERROR)

def check_response_is_success(res_obj):
    if 'Status' in res_obj:
        status: str = res_obj['Status']
        return True if status == 'SUCCESS' else False
    return False

def FILE_NAME_TRADING_CONFIG(DATE):
    return f"{APPCONFIG.JSON_TRADING_CON}{DATE}"+".json"

def FILE_NAME_FOR_CE_S_TOKENS(DATE):
    return f"{APPCONFIG.JSON_OPT_CE_S_TOKENS}{DATE}"+".pkl"

def FILE_NAME_FOR_PE_S_TOKENS(DATE):
    return f"{APPCONFIG.JSON_OPT_PE_s_TOKENS}{DATE}"+".pkl"

def FILE_NAME_FOR_CURRENT_JSON_TRADING_CON():
    return f"{APPCONFIG.CURRENT_JSON_TRADING_CON}"+".json"

def PKL_LOCAL_PATH_GEN(FILE_NAME):
    return os.path.join(APPCONFIG.OPT_TOKEN_FILES_LOCAL_DIRECTORY,FILE_NAME)

def TRADING_CONFIG_DICT(PARAMLIST : list):
    if len(PARAMLIST) != 10:
        return {}

    FUT_EXPIRY_DATE_d, OPT_EXPIRY_DATE_d, TODAY_DATE_FORM1, FUT_EXPIRY_DATE_COPY, OPT_EXPIRY_DATE_COPY, FUT_TOKEN, FUT_SYMBOL, MARKET_IS_OPEN_TODAY, UPDATED_DATE_TIME, KEY = PARAMLIST[:10]

    TRADING_CONFIG = {
        'FUT_EXPIRY_DATE': FUT_EXPIRY_DATE_d,
        'OPT_EXPIRY_DATE': OPT_EXPIRY_DATE_d,
        'T_DATE': TODAY_DATE_FORM1,
        'FUT_EXPIRY_DATE_STR': FUT_EXPIRY_DATE_COPY,
        'OPT_EXPIRY_DATE_STR': OPT_EXPIRY_DATE_COPY,
        'FUT_TOKEN': FUT_TOKEN,
        'FUT_SYMBOL': FUT_SYMBOL,
        'MARKET_IS_OPEN_TODAY':MARKET_IS_OPEN_TODAY,
        'UPDATED_DATE_TIME':UPDATED_DATE_TIME,
        'ke': KEY,
    }

    return TRADING_CONFIG

def ANGEL_INSTRUMENT_LIST():
    return ujson.loads(urllib.request.urlopen(APPCONFIG.AO_INSTRUMENT_LIST_URL).read())


def DO_THE_EMPTY_INIT_ERROR_FILES_LOCAL_DIRECT():
    try:
        for filename in os.listdir(APPCONFIG.ERROR_START_IN_SCRIPT_DIR):
            file_path = os.path.join(APPCONFIG.ERROR_START_IN_SCRIPT_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                return False
        return True
    except OSError as e:
        return False

def DO_THE_EMPTY_FUT_FILES_LOCAL_DIRECT():
    try:
        for filename in os.listdir(APPCONFIG.FUT_TOKEN_FILES_LOCAL_DIRECTORY):
            file_path = os.path.join(APPCONFIG.FUT_TOKEN_FILES_LOCAL_DIRECTORY, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                return False
        return True
    except OSError as e:
        return False
    
def DO_THE_EMPTY_OPT_FILES_LOCAL_DIRECT():
    try:
        for filename in os.listdir(APPCONFIG.OPT_TOKEN_FILES_LOCAL_DIRECTORY):
            file_path = os.path.join(APPCONFIG.OPT_TOKEN_FILES_LOCAL_DIRECTORY, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                return False
        return True
    except OSError as e:
        return False
    

def CREATE_ERROR_FILE_TO_STOP_CRON():
    try:
        with open(APPCONFIG.ERROR_START_IN_SCRIPT_PATH, 'w') as file:
            return True
    except Exception as e:
        return False
    
# FUNCTIONS FOR PTS
# CALCULATE_OPT_STRIKE_PRICE_FROM_FUT_PRICE(FUT_LTP)   
def CAL_OPT_SP_F_PRI(FUT_LTP):
    
    CSP, PSP = 0, 0
    Round_true = True
    if isinstance(FUT_LTP, str):
        Round_true = False
        try:
            FUT_LTP = int(FUT_LTP)
            Round_true = True
        except ValueError:
            return  CSP, PSP
        
    if Round_true == True:
       FUT_LTP = round(FUT_LTP)
       SPB = int(FUT_LTP / 100)
       CSP, PSP = SPB * 100, SPB * 100 + 100 

    return CSP, PSP
   
def local_pkl_file(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
                return data
        except Exception as e:
            return {}
    else:
        return {}
    
def check_fut_opt_daily_config():
    fut_config_data = local_pkl_file(APPCONFIG.CURRENT_JSON_TRADING_CON_LOCAL)
    opt_t_ce_df,opt_t_pe_df = pd.DataFrame(),pd.DataFrame()
    if not fut_config_data:
       print("ERROR: NO DATA FOUND IN AOBN_TRADE_CONFIG.pkl FILE OR FILE NOT GENERATED..")
       exit()
    else:
        if 'T_DATE' not in fut_config_data or 'OPT_EXPIRY_DATE_STR' not in fut_config_data:
            print("ERROR: T_DATE or OPT_EXPIRY_DATE_STR IS MISSING LOCAL AOBN_TRADE_CONFIG")
            exit()
        else:
            opt_ex_date = fut_config_data['OPT_EXPIRY_DATE_STR']
            opt_ce_tfilepath = PKL_LOCAL_PATH_GEN(FILE_NAME_FOR_CE_S_TOKENS(opt_ex_date))
            opt_pe_tfilepath = PKL_LOCAL_PATH_GEN(FILE_NAME_FOR_PE_S_TOKENS(opt_ex_date))
            if not os.path.exists(opt_ce_tfilepath) or not os.path.exists(opt_pe_tfilepath):
               print("ERROR: OPT TOKENS file does not exist to local machine or server machine")
               exit() 
            else:     
                opt_t_ce_df = pd.read_pickle(opt_ce_tfilepath)
                opt_t_pe_df = pd.read_pickle(opt_pe_tfilepath)
                if opt_t_ce_df.empty or opt_t_pe_df.empty:
                   print("ERROR: OPT_T_CE_DF or OPT_T_PE_DF DATA FRAME IS EMPTY")
                   exit() 
                else:
                   return fut_config_data,opt_t_ce_df,opt_t_pe_df       
                    
            


def Check_Market_is_open():
    current_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    return datetime.strptime(APPCONFIG.MStime, '%H:%M').time() <= current_time <= datetime.strptime(APPCONFIG.MEtime, '%H:%M').time()


def Check_Market_stop_new_entry_and_close_all_timeout():
    SNT = True 
    CAT = True 
    current_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    STOP_new_trade = current_time.replace(hour=15, minute=15, second=0, microsecond=0)
    close_all_trade = current_time.replace(hour=15, minute=20, second=0, microsecond=0)

    SNT = True if current_time >= STOP_new_trade else False
    CAT = True if current_time >= close_all_trade else False
    return [SNT, CAT]

    
def Ta_handler_obj(interval_OBJ):
    try:
        return TRADINGVIEW_Handler(symbol=APPCONFIG.Symbol,screener=APPCONFIG.Screener,exchange=APPCONFIG.Exchange,interval=interval_OBJ).get_analysis().custom
    except:
        return APPCONFIG.TR_No_results


def C_NUM_init():
    cache.set('C_NUM', 0)
    return True

def C_NUM_INCREMENT():
    C_NUM = cache.get('C_NUM')
    C_NUM = C_NUM + 1
    cache.set('C_NUM', C_NUM)
    return C_NUM

def Md5hash():
    current_timestamp = datetime.now().timestamp()
    timestamp_str = str(current_timestamp).encode('utf-8')
    md5_hash = hashlib.md5(timestamp_str).hexdigest()
    return md5_hash
    
def R_to_get_ltp(C_symbol,C_token):
    res = {}
    payload = {}
    if C_symbol != "" and C_token != "" :
        payload = {    
            "exchange": APPCONFIG.FUT_EXCHANGE_SEGMENT,
            "tradingsymbol": C_symbol,
            "symboltoken":C_token
        }
    else:
        print("Error: Invalid tradingsymbol and symboltoken it's having empty value")
        return APPCONFIG.TR_No_results
    if payload:
        try:
            LTP = AO.r_get_ltp(payload)
            return LTP
        except:
            return APPCONFIG.TR_No_results
    else:
        print("Error: PAYLOAD IS BLANK ")
        return APPCONFIG.TR_No_results
    
def CHECK_FUTURE_DATA_UPDATETIME(updated_date_time_str):
    updated_date_time = datetime.strptime(updated_date_time_str, "%Y-%m-%d %H:%M:%S")
    today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    reference_time = today_date.replace(hour=9, minute=7, second=0)
    if updated_date_time.date() == today_date.date() and updated_date_time.time() > reference_time.time():
      return True
    else:
      return False
        
def EMPTY_ALL_INIT_DIRECTORY():
    try:
        DO_THE_EMPTY_FUT_FILES_LOCAL_DIRECT()
        DO_THE_EMPTY_OPT_FILES_LOCAL_DIRECT()
        DO_THE_EMPTY_INIT_ERROR_FILES_LOCAL_DIRECT()
        return True
    except:
        return False
        
