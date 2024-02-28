import multiprocessing
import schedule
import time
from datetime import datetime
import hashlib
import os
import pickle
import time
import asyncio
import pprint
import pandas as pd
from diskcache import FanoutCache

# CUSTOM
from CONFIG import APP as APPCONFIG
import LIB_FUN_HELPER as HELPER
import LIB_AO_API as AO
import LIB_S3 as S3L
import LIB_LOGGER as LOG
import METHOD_EVERY_MIN_PRO as PROC

MODULE_NAME = 'PAPER TRADING SCRIPT'

cache = FanoutCache(directory='/tmp/mycache')

FUT_CONFIG_DATA, Signals, BI_OBJ = {},{},{}

# NOT MANDATORY
TOKEN = AO.get_jwtToken()

LOG.ADD_LOG_INTO_DB(MODULE_NAME,'INFO',"PTS SCRIPT START")
# MANDATORY To check FUT_CONFIG_DATA OPT_TOK_CE_DF OPT_TOK_PE_DF
FUT_CONFIG_DATA, OPT_TOK_CE_DF, OPT_TOK_PE_DF = HELPER.check_fut_opt_daily_config()

if not OPT_TOK_CE_DF.empty and not OPT_TOK_PE_DF.empty and FUT_CONFIG_DATA:
    
    HELPER.C_NUM_init()
    schedule.every().minute.at(":00").do(PROC.Every_Minute_PROCESS,FUT_CONFIG_DATA,OPT_TOK_CE_DF,OPT_TOK_PE_DF)
    
    while HELPER.Check_Market_is_open():
        schedule.run_pending()  
        time.sleep(1)
    else:
        LOG.ADD_LOG_INTO_DB(MODULE_NAME,'INFO',"MARKET SESSION IS OVER")