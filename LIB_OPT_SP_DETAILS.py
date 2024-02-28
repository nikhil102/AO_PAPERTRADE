import requests
import json

import LIB_FUN_HELPER as HELPER

scan_url = "https://scanner.tradingview.com/india/scan"
param = {'columns': ['close|1',],'symbols': {'query': {'types': []},'tickers': ['NSE:BANKNIFTY']}}
headers1  =  {'User-Agent': 'tradingview_ta/3.3.0'}


def fut_Current_Price():
    Future_price = 0 
    try:
        response = requests.post(scan_url, json=param, headers=headers1)
        
        if response.status_code == 200:
            result = json.loads(response.text)["data"]
            if result:
                Future_price = result[0]['d'][0]
                return Future_price
    except ValueError:
        return Future_price


fut_Current_Price() 



def FUT_PRICE_SP_DETAIL():
    FUT_LTP,CSP,PSP,CSP_UP,CSP_DOWN,PSP_UP,PSP_DOWN= 0,0,0,0,0,0,0
    FUT_LTP = fut_Current_Price() 
    if FUT_LTP > 0:
        CSP, PSP = HELPER.CAL_OPT_SP_F_PRI(FUT_LTP)
        if CSP > 0 and PSP > 0:
            CSP_UP = CSP + 700
            CSP_DOWN = CSP - 700
            PSP_UP = CSP + 700
            PSP_DOWN = CSP - 700
    RES = {
        'FUT_LTP':FUT_LTP,
        'CSP':CSP,
        'PSP':PSP,
        'CSP_UP':CSP_UP,
        'CSP_DOWN':CSP_DOWN,
        'PSP_UP':PSP_UP,
        'PSP_DOWN':PSP_DOWN
        }
    return RES

