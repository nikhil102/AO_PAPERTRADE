from typing import Dict
from datetime import datetime, date
import os
import platform

if platform.system() == "Linux":
    ENV_TYPE : str = 'SERVER'
    MStime : str = '09:15'
    MEtime : str = '15:25'
    CURRENT_PATH_CONFIG = ''
    CURRENT_PATH_CONFIG = os.path.join("opt","AO_PAPERTRADE")
    CURRENT_Path = ''
    #CURRENT_Path = os.path.dirname(CURRENT_PATH_CONFIG)
    CURRENT_Path = CURRENT_PATH_CONFIG
else:
    ENV_TYPE : str = 'LOCAL'
    MStime : str = '01:00'
    MEtime : str = '23:57'
    CURRENT_PATH_CONFIG = ''
    CURRENT_PATH_CONFIG = os.getcwd()
    CURRENT_Path = ''
    #CURRENT_Path = os.path.dirname(CURRENT_PATH_CONFIG)
    CURRENT_Path = CURRENT_PATH_CONFIG
    
# AWS Configuration
AWS_ACCESS_KEY : str = 'AKIAWKJPM2XTVP23YD2P'
AWS_SECRET_KEY : str = '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'
AWS_REGION : str = 'ap-south-1'
AWS_S3_BUCKET_NAME : str = 'bn-ao-tokens'

# Database Configuration
MYSQL_HOST = '154.41.254.123'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Mastermind@123'
MYSQL_DATABASE = 'TVBN'

DB_CONFIG_OBJ : Dict[str, str] = {
    'host': MYSQL_HOST,
    'user': MYSQL_USER,
    'password': MYSQL_PASSWORD,
    'database': MYSQL_DATABASE
}

# Angel One API Credentials
AO_API_KEY: str = "ZZ6CRqGZ"
AO_CLIENT_ID: str = "SAHW1028"
AO_EMAIL_ID: str = "shindenikhil102@gmail.com"
AO_PASSWORD: str = "Mastermind@123"
AO_MPIN: str = "2525"
AO_TOTP_SECURITY_KEY: str = "MALBI3B35CGKNABT6LJE62SKUY"

# DATE
TODAY_DATE: date = date.today()
DATE_FORMAT1: str  = "%Y-%m-%d"
DATE_FORMAT2: str = "%d%b%Y"
DATE_FORMAT3: str = "%d-%m-%Y"
TODAY_DATE_FORM1 = TODAY_DATE.strftime(DATE_FORMAT1)
TODAY_DATE_FORM2 = datetime.strptime(TODAY_DATE_FORM1, DATE_FORMAT1)


# URLS
AO_INSTRUMENT_LIST_URL: str = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
NSE_BANKNIFTY_URL: str = 'https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY'
NSE_BANKNIFTY_OPTION_CHAIN: str = 'https://www.nseindia.com/option-chain'

# Headers
NSEAPI: Dict[str, str] = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
    'accept-language': 'en,gu;q=0.9,hi;q=0.8',
    'accept-encoding': 'gzip, deflate, br'
}

# Future Token DataFrame Filter
FUT_Name: str = 'BANKNIFTY'
FUT_Instrument_type: str = 'FUTIDX'
FUT_Lotsize: str = '15'
FUT_EXCHANGE_SEGMENT: str = 'NFO'

# Option Token DataFrame Filter
OPT_Name: str = 'BANKNIFTY'
OPT_Instrument_type: str = 'OPTIDX'
OPT_Lotsize: str = '15'
OPT_EXCHANGE_SEGMENT: str = 'NFO'

# PATH

OPT_TOKEN_FILES_LOCAL_DIRECTORY = os.path.join(CURRENT_Path, "OPT_TOKEN_FILES")
FUT_TOKEN_FILES_LOCAL_DIRECTORY = os.path.join(CURRENT_Path, "FUT_TOKEN_FILE")

ERROR_DIR : str = os.path.join(CURRENT_Path, 'ERROR')
ERROR_START_IN_SCRIPT_FILE_NAME : str = "ERROR_START.LOG"
ERROR_START_IN_SCRIPT_DIR : str = os.path.join(CURRENT_Path, 'ERROR_S')
ERROR_START_IN_SCRIPT_PATH : str = os.path.join(ERROR_START_IN_SCRIPT_DIR, ERROR_START_IN_SCRIPT_FILE_NAME)

AOAUTH_FILE_NAME : str = "AOAUTH"
AOAUTH_FILE_NAME_FILEPATH : str = os.path.join(CURRENT_Path, AOAUTH_FILE_NAME + '.json')
CURRENT_JSON_TRADING_CON : str= "AOBN_TRADE_CONFIG.json"

CURRENT_JSON_TRADING_CON_LOCAL : str = os.path.join(CURRENT_Path,'FUT_TOKEN_FILE','AOBN_TRADE_CONFIG.pkl')
JSON_TRADING_CON : str= "TRADE_CONFIG_"
JSON_OPT_CE_LONG_TOKENS : str= "OPT_CE_TOKENS_L_"
JSON_OPT_PE_LONG_TOKENS = "OPT_PE_TOKENS_L_"
JSON_OPT_CE_S_TOKENS : str = "OPT_CE_TOKENS_S_"
JSON_OPT_PE_s_TOKENS : str = "OPT_PE_TOKENS_S_"


#HOLIDAY_PATH
HOLIDAY_PATH = "config/HOLIDAY_LIST.csv"

#PAPER TRADING SCRIPT
# PTS Configuration
Symbol : str = 'BANKNIFTY'
Screener : str = 'india'
Exchange : str = 'NSE'
#market open and close time

TR_No_results = {'RECOMMENDATION': 'NO_RESPONSE', 'BUY': 0, 'SELL': 0, 'NEUTRAL': 0}

