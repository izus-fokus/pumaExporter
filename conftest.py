import pytest
import json
import sys
from pumaExport import Exporter

def pytest_addoption(parser):
    parser.addoption('--apikey', action='store', default='<add PUMA API-Key>', help='add PUMA API-Key')
    parser.addoption('--user', action='store', default='ffritze', help='add PUMA user')


@pytest.fixture(scope='session')
def credentials():
    with open("cred/credentials.json", "r") as cred_file:
        credentials = json.load(cred_file)
        credentials["puma"]["apiKey"] = sys.argv[1][len("--apikey="):]
        credentials["puma"]["user"] = sys.argv[2][len("--user="):]
        return credentials

@pytest.fixture(scope='session')
def exporter():
    exp = Exporter()
    return exp