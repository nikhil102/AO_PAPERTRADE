import mysql.connector
from datetime import datetime
# CUSTOM
from CONFIG import APP as APPCONFIG
from CONFIG import SQL_QUERY as Q
import LIB_S3
import LIB_FUN_HELPER as HELPER

connection = {}
DB_CONFIG_OBJ = APPCONFIG.DB_CONFIG_OBJ


def connect():
    global connection
    connection = mysql.connector.connect(**DB_CONFIG_OBJ)
    return connection

def dbconnect():
    global connection
    if connection:
        return connection
    else:
        return connect()
    

def SELECT(QUERY,CUR_Type,FETCH_Type):
    try:
        db_connection = dbconnect()
        if CUR_Type == 'NORMAL' or CUR_Type == '':
            cursor = db_connection.cursor()
        elif CUR_Type == 'DICTIONARY':
            cursor = db_connection.cursor(dictionary=True)
        cursor.execute(QUERY)
        if FETCH_Type == 'ALL' or FETCH_Type == '':
           result = cursor.fetchall()
        elif FETCH_Type == 'one':
           result = cursor.fetchone()
        return HELPER.RESPONSE_SUCCESS(result) if result else HELPER.NO_DATA_RESPONSE_SUCCESS()
    except mysql.connector.Error as err:
        return HELPER.RESPONSE_ERROR(err)
    
def UPDATE(QUERY,Execute=''):
    try:
        db_connection = dbconnect()
        cursor = db_connection.cursor()
        if Execute == 'NORMAL' or Execute == '':
           cursor.execute(QUERY)
        elif Execute == 'MANY':
           cursor.executemany(QUERY)
        db_connection.commit()
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except mysql.connector.Error as err:
        return HELPER.RESPONSE_ERROR(err)
    
def UPDATE_QUERY(QUERY):
    try:
        db_connection = dbconnect()
        cursor = db_connection.cursor()
        print(QUERY)
        cursor.execute(QUERY)
        db_connection.commit()
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except mysql.connector.Error as err:
        return HELPER.RESPONSE_ERROR(err)
    
def INSERT_DICT_DATA(QUERY,Data,Execute=''):
    try:
        db_connection = dbconnect()
        cursor = db_connection.cursor()
        if Execute == 'NORMAL' or Execute == '':
           cursor.execute(QUERY,Data)
        elif Execute == 'MANY':
           cursor.executemany(QUERY,Data)
        db_connection.commit()
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except mysql.connector.Error as err:
        return HELPER.RESPONSE_ERROR(err)

def INSERT_LIST_VALUE_DATA(QUERY,Data,Execute=''):
    try:
        db_connection = dbconnect()
        cursor = db_connection.cursor()
        if Execute == 'NORMAL' or Execute == '':
           cursor.execute(QUERY,list(Data.values()))
        elif Execute == 'MANY':
           cursor.executemany(QUERY,list(Data.values()))
        db_connection.commit()
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except mysql.connector.Error as err:
        return HELPER.RESPONSE_ERROR(err)
    
# Close the connection
def dbdisconnect():
    global connection
    if connection:
       connection.close()