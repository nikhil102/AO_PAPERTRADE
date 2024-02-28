from typing import Dict
import pandas as pd
from datetime import datetime, date
from io import BytesIO, StringIO

# CUSTOM
import LIB_MDB
from CONFIG import APP as APPCONFIG
import LIB_FUN_HELPER as HELPER
import LIB_S3 as S3L

def holiday_check():
    HOLIDAY_PATHs = APPCONFIG.HOLIDAY_PATH
    HOLIDAY_FILE_OBJ = S3L.read_s3_file(HOLIDAY_PATHs)
    x_date = datetime.now()
    x_date_str = x_date.strftime("%d-%m-%Y")
    Market_Open_Status = "YES"
    if x_date.weekday() in [5, 6]:  # 5 is Saturday, 6 is Sunday
        Market_Open_Status = "NO"
    else:
        if HELPER.check_response_is_success(HOLIDAY_FILE_OBJ): 
            HOLIDAY_FILE_DATA = HOLIDAY_FILE_OBJ.get('Data')
            csv_file = StringIO(HOLIDAY_FILE_DATA)
            HOLIDAY_DF = pd.read_csv(csv_file)
            SPL_DAY_DATA_FRAME_FILTER = pd.DataFrame(HOLIDAY_DF[(HOLIDAY_DF["date"] == x_date_str)])
            if not SPL_DAY_DATA_FRAME_FILTER.empty:
                Market_Open_Status = SPL_DAY_DATA_FRAME_FILTER.iloc[0]["market_open_status"]                
    return Market_Open_Status


def Filer_as_per_nfotypes(DF,INST_TYPE):
    Filter_DF = pd.DataFrame(DF[(DF["name"] == APPCONFIG.FUT_Name) & (DF["exch_seg"] == APPCONFIG.FUT_EXCHANGE_SEGMENT) & (DF["instrumenttype"] == INST_TYPE)])
    Filter_DF["expiry1"] = pd.to_datetime(Filter_DF["expiry"], format=APPCONFIG.DATE_FORMAT2)
    Filter_DF = Filter_DF.sort_values(by="expiry1")
    return Filter_DF

def Get_Current_Fut_Expiry_and_Token(DFF):
    if not DFF.empty:
        DFF = pd.DataFrame(DFF[(DFF["expiry1"] >= APPCONFIG.TODAY_DATE_FORM1)])
        if not DFF.empty:
            CURRENT_FUT_DATA = DFF.iloc[0]
            if not CURRENT_FUT_DATA.empty:
                EXPIRY_DATE = CURRENT_FUT_DATA["expiry1"]
                FUT_TOKEN = CURRENT_FUT_DATA["token"]
                FUT_SYMBOL = CURRENT_FUT_DATA["symbol"]
                return EXPIRY_DATE,FUT_TOKEN, FUT_SYMBOL
            
def Get_Current_OPT_Expiry(DFF):
    BN_OPT_EXPIRY_DATE_DF = pd.to_datetime(DFF['expiry1'])
    if not BN_OPT_EXPIRY_DATE_DF.empty:
        distinct_dates = BN_OPT_EXPIRY_DATE_DF.drop_duplicates()
        OPT_Expiry_DF = pd.DataFrame(distinct_dates)
        OPT_Expiry_DF_COPY = pd.DataFrame(OPT_Expiry_DF[(OPT_Expiry_DF["expiry1"] >= APPCONFIG.TODAY_DATE_FORM1)])
        OPT_Expiry_DF_COPY.sort_values(by="expiry1", inplace=True)
        if not OPT_Expiry_DF_COPY.empty:
            OPT_EXPIRY_DATE = OPT_Expiry_DF_COPY["expiry1"].iloc[0]
            return OPT_EXPIRY_DATE

def OPT_DF_FILTER(DF,UP,LOW):
    DF.reset_index(drop=True, inplace=True)
    DF["strike"] = pd.to_numeric(DF["strike"])
    DF["strike"] = DF["strike"].astype("int64")
    RANGE_DF = DF[(DF["strike"] <= UP) & (DF["strike"] >= LOW)]
    return RANGE_DF
    
def OPT_DF_SHORTER(LTP_OBJ,CELFN_DF,PELFN_DF,OEDS):
    CE_RANGE_DF, PE_RANGE_DF = pd.DataFrame(),pd.DataFrame()
    CEr, PEr = {},{}
    if 'ltp' in LTP_OBJ and 'tradingsymbol' in LTP_OBJ:
        if LTP_OBJ["ltp"] > 0:
           FUT_C_P = LTP_OBJ['ltp'] 
           Last_price = int(FUT_C_P)
           SPB = int(Last_price / 100)
           CSP, PSP = SPB * 100, SPB * 100 + 100 
           CE_SP_UP, CE_SP_LOW, PE_SP_UP, PE_SP_LOW  = CSP + 1000, CSP - 1000, PSP + 1000, PSP - 1000
           CE_RANGE_DF = OPT_DF_FILTER(CELFN_DF,CE_SP_UP,CE_SP_LOW)
           PE_RANGE_DF = OPT_DF_FILTER(PELFN_DF,PE_SP_UP,PE_SP_LOW)
           CEr = S3L.upload_dataframe_to_s3_to_pickle(CE_RANGE_DF,HELPER.FILE_NAME_FOR_CE_S_TOKENS(OEDS))
           PEr = S3L.upload_dataframe_to_s3_to_pickle(PE_RANGE_DF,HELPER.FILE_NAME_FOR_PE_S_TOKENS(OEDS))
           return CEr, PEr
    return CEr, PEr

def FUT_ALL_DETAILS(BN_TOKENS_DF):
    BN_FUT_DF= Filer_as_per_nfotypes(BN_TOKENS_DF,APPCONFIG.FUT_Instrument_type)
    FUT_EXPIRY_DATE, FUT_TOKEN, FUT_SYMBOL = Get_Current_Fut_Expiry_and_Token(BN_FUT_DF)
    FUT_EXPIRY_DATE_COPY =  FUT_EXPIRY_DATE.strftime(APPCONFIG.DATE_FORMAT2).upper()
    return FUT_EXPIRY_DATE, FUT_EXPIRY_DATE_COPY, FUT_TOKEN, FUT_SYMBOL
 

# print(FUT_EXPIRY_DATEs, FUT_TOKENs, FUT_SYMBOLs)
def OPT_TOKENS_DATAFRAME(BN_TOKENS_DF):
    BN_OPT_DF= Filer_as_per_nfotypes(BN_TOKENS_DF,APPCONFIG.OPT_Instrument_type)
    OPT_EXPIRY_DATE = Get_Current_OPT_Expiry(BN_OPT_DF)
    OPT_EXPIRY_DATE_d = OPT_EXPIRY_DATE.strftime('%Y-%m-%d')
    OPT_EXPIRY_DATE_COPY =  OPT_EXPIRY_DATE.strftime(APPCONFIG.DATE_FORMAT2).upper()
    C_OPT_BN_TOKEN_DF = pd.DataFrame(BN_OPT_DF[(BN_OPT_DF["expiry1"] == OPT_EXPIRY_DATE)])
    C_OPT_BN_TOKEN_DF["strike"] = pd.to_numeric(C_OPT_BN_TOKEN_DF["strike"])
    C_OPT_BN_TOKEN_DF["strike"] = C_OPT_BN_TOKEN_DF["strike"] / 100
    C_OPT_BN_TOKEN_DF["strike"] = C_OPT_BN_TOKEN_DF["strike"].astype("int64")
    C_OPT_BN_TOKEN_DF["ce_or_pe"] = C_OPT_BN_TOKEN_DF["symbol"].str[-2:].astype(str)
    CE_DF = C_OPT_BN_TOKEN_DF[(C_OPT_BN_TOKEN_DF["ce_or_pe"] == "CE")]
    PE_DF = C_OPT_BN_TOKEN_DF[(C_OPT_BN_TOKEN_DF["ce_or_pe"] == "PE")]
    
    CE_OPT_EX_STR_LST = list(CE_DF.expiry.unique())
    PE_OPT_EX_STR_LST = list(PE_DF.expiry.unique())
    CE_OPT_EX_STR, PE_OPT_EX_STR = "", ""
    if len(CE_OPT_EX_STR_LST) > 0 : 
            CE_OPT_EX_STR = CE_OPT_EX_STR_LST[0]
            CE_DF = CE_DF[["token","symbol","strike"]]
            CE_DF.sort_values('strike',inplace=True)

            
    if len(PE_OPT_EX_STR_LST) > 0 : 
            PE_OPT_EX_STR = PE_OPT_EX_STR_LST[0]
            PE_DF = PE_DF[["token","symbol","strike"]]
            PE_DF.sort_values('strike',inplace=True)

    return CE_DF, PE_DF, OPT_EXPIRY_DATE_d, OPT_EXPIRY_DATE_COPY

def ADD_DATA_TO_CONFIG_TABLE(Trading_Config_data):
    operation = LIB_MDB.Insert_Data_Into_EXP_CONFIG_Table_by_Dict(Trading_Config_data)
    if HELPER.check_response_is_success(operation): 
            return S3L.upload_json_to_s3(Trading_Config_data,APPCONFIG.CURRENT_JSON_TRADING_CON)

def GEN_NEW_CONFIG(MARKET_IS_OPEN_TODAY):
    BN_TOKENS_DF = pd.DataFrame(HELPER.ANGEL_INSTRUMENT_LIST())
    FUT_EXPIRY_DATE, FUT_EXPIRY_DATE_COPY, FUT_TOK, FUT_SYM = FUT_ALL_DETAILS(BN_TOKENS_DF)
    FUT_EXPIRY_DATE_d =  FUT_EXPIRY_DATE.strftime('%Y-%m-%d')
    CE_DF, PE_DF, OPT_EXPIRY_DATE_d, OPT_EXPIRY_DATE_COPY = OPT_TOKENS_DATAFRAME(BN_TOKENS_DF)
    PARAMLIST = [FUT_EXPIRY_DATE_d,OPT_EXPIRY_DATE_d,APPCONFIG.TODAY_DATE_FORM1,FUT_EXPIRY_DATE_COPY,OPT_EXPIRY_DATE_COPY,FUT_TOK,FUT_SYM,MARKET_IS_OPEN_TODAY,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),'NIK']
    TRADING_CONFIG_DICT = HELPER.TRADING_CONFIG_DICT(PARAMLIST)
    Fr = S3L.upload_json_to_s3(TRADING_CONFIG_DICT,HELPER.FILE_NAME_TRADING_CONFIG(FUT_EXPIRY_DATE_COPY))
    return TRADING_CONFIG_DICT, CE_DF, PE_DF
    


