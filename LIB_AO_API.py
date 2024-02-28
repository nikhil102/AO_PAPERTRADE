import requests
from CONFIG import APP as APPCONFIG
import pyotp
import uuid, re
import socket
import pprint
import json
import pickle
import os
import pytz
from datetime import datetime
from diskcache import FanoutCache
cache = FanoutCache(directory='/tmp/mycache')

R_URL_AO_LOGIN = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword"
R_URL_AO_REFRESH_TOKEN = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/jwt/v1/generateTokens"
R_URL_AO_GET_LTP = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/getLtpData"
R_URL_AO_GET_MARKET_DATA = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/market/v1/quote"


API_KEY = APPCONFIG.AO_API_KEY
CLIENT_ID = APPCONFIG.AO_CLIENT_ID
EMAIL_ID = APPCONFIG.AO_EMAIL_ID
PASSWORD = APPCONFIG.AO_PASSWORD
MPIN = APPCONFIG.AO_MPIN
TOTP_SECURITY_KEY = APPCONFIG.AO_TOTP_SECURITY_KEY
TOTP_OBJ = pyotp.TOTP(APPCONFIG.AO_TOTP_SECURITY_KEY)
TOTP = TOTP_OBJ.now()
MACADDRESS =':'.join(re.findall('..', '%012x' % uuid.getnode()))
AOAUTH_ACCESS_TOKEN = ''

def LOCAL_IP_ADDRESS():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    cache.set('LOCAL_IP', ip_address)
    return ip_address

def PUBLIC_IP_ADDRESS():
    try:
        response = requests.get('https://api.ipify.org')
        if response.status_code == 200:
            cache.set('PUBLIC_IP', response.text)
            return response.text
        else:
            return "106.193.147.98"
    except requests.RequestException as e:
        return "106.193.147.98"

def get_public_ip():
    if 'PUBLIC_IP' in cache:
        return cache.get('PUBLIC_IP')
    else:   
        return PUBLIC_IP_ADDRESS() 
 
def get_local_ip():
    if 'LOCAL_IP' in cache:
        return cache.get('LOCAL_IP')
    else:   
        return LOCAL_IP_ADDRESS() 
     
def is_greater_than_906_am_in_kolkata(auth_updated_datetime_str):
    auth_updated_datetime = datetime.strptime(auth_updated_datetime_str, '%Y-%m-%d %H:%M:%S')
    auth_updated_datetime = pytz.timezone('Asia/Kolkata').localize(auth_updated_datetime)
    current_datetime = datetime.now(pytz.timezone('Asia/Kolkata'))
    compare_time = current_datetime.replace(hour=9, minute=6, second=0, microsecond=0)
    return auth_updated_datetime > compare_time

def LOAD_AUTH_FILE():
    if os.path.exists(APPCONFIG.AOAUTH_FILE_NAME_FILEPATH):
        with open(APPCONFIG.AOAUTH_FILE_NAME_FILEPATH, 'r') as file:
            json_data = json.load(file)
        return json_data
    return None

def LOGIN_payload():
    lpayload = {
        "clientcode": CLIENT_ID,
        "password": MPIN,
        "totp": TOTP
    }
    return lpayload

def REQ_HEADER():
    
    r_HEADER = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': get_local_ip(),
        'X-ClientPublicIP': get_public_ip(),
        'X-MACAddress': MACADDRESS,
        'X-PrivateKey': API_KEY
    }
    return r_HEADER

def REQ_HEADER_WITH_TOKEN(jwtToken):
    REQ = REQ_HEADER()
    REQ['Authorization'] = "Bearer " + jwtToken
    return REQ

def get_jwtToken_refreshToken_from_auth_cache():
    if 'AUTH_DATA' in cache:
        AUTH_DATA_DICT =cache['AUTH_DATA']
        if 'jwtToken' in AUTH_DATA_DICT and 'refreshToken' in AUTH_DATA_DICT:
            return [AUTH_DATA_DICT['jwtToken'],AUTH_DATA_DICT['refreshToken']]
    return ['','']

def get_jwtToken_from_auth_cache():
    if 'AUTH_DATA' in cache:
        AUTH_DATA_DICT =cache['AUTH_DATA']
        if "UPDATED_DATE_TIME" in AUTH_DATA_DICT:
           AUTH_UPDATED_DATE_TIME = AUTH_DATA_DICT['UPDATED_DATE_TIME']
           if is_greater_than_906_am_in_kolkata(AUTH_UPDATED_DATE_TIME):
              if 'jwtToken' in AUTH_DATA_DICT:
                  return AUTH_DATA_DICT['jwtToken']  
    return ''
    
def get_jwtToken_from_auth_file():
    AUTH_FILE_DATA = LOAD_AUTH_FILE()
    if AUTH_FILE_DATA:
       if "UPDATED_DATE_TIME" in AUTH_FILE_DATA:
          AUTH_UPDATED_DATE_TIME = AUTH_FILE_DATA['UPDATED_DATE_TIME'] 
          if is_greater_than_906_am_in_kolkata(AUTH_UPDATED_DATE_TIME):
             if 'jwtToken' in AUTH_FILE_DATA:
                return AUTH_FILE_DATA['jwtToken'] 
    return ''
    
    #AOAUTH_DATA = pickle.loads(AOAUTH_DATA)
    #AOAUTH_ACCESS_TOKEN = "Bearer " + AUTH_FILE_DATA['jwtToken']

def r_refersh_token():
    RES,data  = {},{}
    r_payload, status, data, errorcode = {} ,False, {}, None
    jwtToken,refreshToken =  get_jwtToken_refreshToken_from_auth_cache()
    if refreshToken != '' and jwtToken != '':
        r_payload['refreshToken'] = refreshToken
        response = requests.post(R_URL_AO_REFRESH_TOKEN, json=r_payload, headers=REQ_HEADER_WITH_TOKEN(jwtToken))

    if response.status_code == 200:
       data = response.json() 
       status = data.get("status")
       rdata = data.get("data")
       message = data.get("message")
       errorcode = data.get("errorcode")

    if status and data != None and errorcode == '' or errorcode == None:   
       rdata['UPDATED_DATE_TIME'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
       cache.set('AUTH_DATA', rdata) 
       RES['status'] = True
       RES['data'] = rdata
       RES['errorcode'] = ''
       RES['message'] = ''
       with open(APPCONFIG.AOAUTH_FILE_NAME_FILEPATH, "w") as outfile:
            json.dump(rdata, outfile)
            return RES
    else:
        
        RES['status'] = False
        RES['DATA'] = {}
        RES['errorcode'] = errorcode
        RES['message'] = message
        return RES

def r_login():
    RES,data  = {},{}
    response = requests.post(R_URL_AO_LOGIN, json=LOGIN_payload(), headers=REQ_HEADER())

    if response.status_code == 200:
       data = response.json() 
       status = data.get("status")
       rdata = data.get("data")
       message = data.get("message")
       errorcode = data.get("errorcode")

    if status and data != None and errorcode == '' or errorcode == None:   
       rdata['UPDATED_DATE_TIME'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
       cache.set('AUTH_DATA', rdata) 
       RES['status'] = True
       RES['data'] = rdata
       RES['errorcode'] = ''
       RES['message'] = ''
       with open(APPCONFIG.AOAUTH_FILE_NAME_FILEPATH, "w") as outfile:
            json.dump(rdata, outfile)
            return RES
    else:
        
        if errorcode == 'AG8002' and status == False:
            res = r_refersh_token()
            status = res.get("status")
            RES['status'] = True
            RES['data'] = res
            RES['errorcode'] = ''
            RES['message'] = ''
            return RES 
        else:    
            RES['status'] = False
            RES['DATA'] = {}
            RES['errorcode'] = errorcode
            RES['message'] = message
            return RES

def get_jwtToken_from_login_fun():
    AUTH_LOGIN_DATA = r_login()
    if 'status' in AUTH_LOGIN_DATA and 'data' in AUTH_LOGIN_DATA:
        Adata = AUTH_LOGIN_DATA['data']
        if 'jwtToken' in Adata:
            return Adata['jwtToken'] 
    return ''

def get_jwtToken():
    jwtToken = get_jwtToken_from_auth_cache()
    if jwtToken == '':
       jwtToken = get_jwtToken_from_login_fun()  
    return '' if jwtToken == '' else jwtToken  

def i_request(url,payload):
    
    data,rdata  = {},{}
    status, data, errorcode = False, {}, None
    message = ''
    jwtToken = get_jwtToken()
    
    response = requests.post(url, json=payload, headers=REQ_HEADER_WITH_TOKEN(jwtToken))
    if response.status_code == 200:
       data = response.json() 
       status = data.get("status")
       rdata = data.get("data")
       message = data.get("message")
       errorcode = data.get("errorcode")

    return [data,status,rdata,message,errorcode]    
             
def i_r_caller(url,payload):
    
    data,rdata  = {},{}
    data,status,rdata,message,errorcode = {},False,{},'',''
    data,status,rdata,message,errorcode = i_request(url,payload)    
    if status and data != None and errorcode == '' or errorcode == None:
       return rdata
    else:
       if errorcode == 'AG8002' and status == False:
          res = r_refersh_token()  
          statusr = res.get("status") 
          if statusr == True:
             data,status,rdata,message,errorcode = i_request(url,payload) 
       return rdata

def r_get_ltp(payload):
    return i_r_caller(R_URL_AO_GET_LTP,payload)

def r_get_market_data(payload):
    return i_r_caller(R_URL_AO_GET_MARKET_DATA,payload)
    
#     # payload = {
#     #     "exchange": APPCONFIG.FUT_EXCHANGE_SEGMENT,
#     #     "tradingsymbol": tradingsymbol,
#     #     "symboltoken": symboltoken
#     # }
# #get_jwtToken_from_auth_cache()
# LR = r_get_ltp()
# print(LR)
