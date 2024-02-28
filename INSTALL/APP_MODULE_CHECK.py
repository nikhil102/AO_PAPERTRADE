import importlib

modules_to_check = [
    'mysql.connector',
    'datetime',
    'typing',
    'os',
    'shutil',
    'ujson',
    'urllib.request',
    'pandas',
    'io',
    'boto3',
    'botocore.exceptions',
    'json',
    'diskcache'
]

def check_and_install_module(module_name):
    try:
        importlib.import_module(module_name)
        #print(f"{module_name} is available.")
    except ImportError:
        print(f"{module_name} Need to install")


if __name__ == "__main__":
    for module in modules_to_check:
        check_and_install_module(module)
