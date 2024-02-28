import boto3
from botocore.exceptions import NoCredentialsError
import urllib.request
import pandas as pd
import json
from io import BytesIO
# CUSTOM
from CONFIG import APP as APPCONFIG
import LIB_FUN_HELPER as HELPER
import pickle


# Initialize S3 client
s3 = boto3.client('s3', aws_access_key_id=APPCONFIG.AWS_ACCESS_KEY, aws_secret_access_key=APPCONFIG.AWS_SECRET_KEY, region_name=APPCONFIG.AWS_REGION)

def create_bucket():
    try:
        # Create S3 bucket
        s3.create_bucket(Bucket=APPCONFIG.AWS_S3_BUCKET_NAME)
        HELPER.NO_DATA_RESPONSE_SUCCESS()
    except NoCredentialsError:
        HELPER.RESPONSE_ERROR("Credentials not available.")


def upload_file(file_name):
    try:
        # Upload a file to the created bucket
        s3.upload_file(file_name, APPCONFIG.AWS_S3_BUCKET_NAME, file_name)
        HELPER.NO_DATA_RESPONSE_SUCCESS()
    except NoCredentialsError:
        HELPER.RESPONSE_ERROR("Credentials not available.")

def delete_file(file_name):
    try:
        # Delete a file from the bucket
        s3.delete_object(Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=file_name)
        HELPER.NO_DATA_RESPONSE_SUCCESS()
    except NoCredentialsError:
        HELPER.RESPONSE_ERROR("Credentials not available.")

def configure_public_access():
    try:
        # Configure public read access for all files in the bucket
        s3.put_bucket_acl(Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, ACL='public-read')
        HELPER.NO_DATA_RESPONSE_SUCCESS()
    except NoCredentialsError:
        HELPER.RESPONSE_ERROR("Credentials not available.")

def read_s3_file(Filename):
    try:
        response = s3.get_object(Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=Filename)
        content = response['Body'].read().decode('utf-8')
        return HELPER.RESPONSE_SUCCESS(content)
    except NoCredentialsError:
        return HELPER.RESPONSE_ERROR("Credentials not available.")
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")

def read_pickle_from_s3_to_dataframe(Filename):
    try:
        response = s3.get_object(Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=Filename)
        content = response['Body'].read()
        dataframe = pd.read_pickle(BytesIO(content))
        
        return HELPER.RESPONSE_SUCCESS(dataframe)
    except NoCredentialsError:
        return HELPER.RESPONSE_ERROR("Credentials not available.")
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")
    
def check_multiple_files_s3(Filenames: list[str]):
    res = []
    response = False
    if Filenames:
       for filename in Filenames:
           try:
              re = s3.head_object(Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=filename)
              res.append(True)
           except Exception as e:
              res.append(False) 
              return False     
    return False if False in res else True 
    
         
def read_pickle_from_s3_to_dataframe_urllib(file_key):
    try:
        url = f'https://{APPCONFIG.AWS_S3_BUCKET_NAME}.s3.{APPCONFIG.AWS_REGION}.amazonaws.com/{file_key}'
        
        with urllib.request.urlopen(url) as response:
            pickle_data = response.read()

        # Load the Pickle data into a DataFrame
        dataframe = pd.read_pickle(BytesIO(pickle_data))
        
        return HELPER.RESPONSE_SUCCESS(dataframe)
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")
    
def read_s3_file_with_urllib(file_key):
    try:
        url = f'https://{APPCONFIG.AWS_S3_BUCKET_NAME}.s3.{APPCONFIG.AWS_REGION}.amazonaws.com/{file_key}'
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')
        return HELPER.RESPONSE_SUCCESS(content)
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")

def upload_dataframe_to_s3_to_json(dataframe, object_key):
    try:
        json_data = dataframe.to_json(orient='records')
        s3.put_object(Body=json_data, Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=object_key)
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")

def upload_dataframe_to_s3_to_csv(dataframe, object_key):
    try:
        csv_data = dataframe.to_csv(index=False)
        s3.put_object(Body=csv_data, Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=object_key)
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")
 
def upload_dataframe_to_s3_to_json(dataframe, object_key):
    try:
        json_data = dataframe.to_json(orient='records')
        s3.put_object(Body=json_data, Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=object_key)
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")

def upload_dataframe_to_s3_to_pickle(dataframe, object_key):
    try:
        pickle_data = pickle.dumps(dataframe)
        s3.put_object(Body=pickle_data, Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=object_key)
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")
 
def upload_json_to_s3(data_dict, object_key):
    try:
        json_data = json.dumps(data_dict)
        # Convert JSON string to bytes
        json_data_bytes = json_data.encode('utf-8')
        s3.put_object(Body=json_data, Bucket=APPCONFIG.AWS_S3_BUCKET_NAME, Key=object_key)
        return HELPER.NO_DATA_RESPONSE_SUCCESS()
    except Exception as e:
        return HELPER.RESPONSE_ERROR(f"{e}")

