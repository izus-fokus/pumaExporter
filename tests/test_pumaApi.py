import sys
import requests
from requests.auth import HTTPBasicAuth
from xml.etree import ElementTree

sys.path.append('../..')

return_value_jsonObject = {"persistentUrl": "http://dx.doi.org/10.18419", "protocol": "doi", "authority": "10.18419",
                           "identifier": "DARUS-452", "latestVersion": {'metadataBlocks': {'citation': {
        'fields': [{"typeName": "title", "value": "Testtitel"}, {"typeName": "dsDescription", "value": [
            {"dsDescriptionValue": {"value": "Testbeschreibung"}}, {"dsDescriptionValue": {"value": "Testbeschreibung2"}}]},
                   {"typeName": "author", "value": [{"authorName": {"value": "Stegmüller, Michael"},
                                                     "authorAffiliation": {"value": "Universität Stuttgart"},
                                                     "authorIdentifierScheme": {"value": "ORCID"},
                                                     "authorIdentifier": {"value": "0000-0000-0000-0001"}},
                                                    {"authorName": {"value": "Iglezakis, Dorothea"},
                                                     "authorAffiliation": {"value": "Universität Stuttgart"},
                                                     "authorIdentifierScheme": {"value": "ORCID"},
                                                     "authorIdentifier": {"value": "0000-0000-0000-0002"}}]}]}}}}

def test_get(credentials, mocker):
    url = credentials["puma"]["baseUrl"] + "users/" + credentials["puma"]["user"] + "/posts?resourcetype=bibtex"
    mocker.patch('requests.get', return_value='<bibsonomy stat="ok"><posts start="0" end="0"/></bibsonomy>', status_code=200)
    try:
        tr = requests.get(url, auth=HTTPBasicAuth(credentials["puma"]["user"], credentials["puma"]["apiKey"]),
                          headers={'content-type': 'application/json'})
        tree = tr.__str__()
        attribute = ElementTree.fromstring(tree).attrib
        assert attribute['stat'] == "ok"
    except Exception as e:
        print(e)


def test_callPumaApiGet(credentials, mocker, exporter):
    url = credentials["puma"]["baseUrl"] + "users/" + credentials["puma"]["user"] + "/posts?resourcetype=bibtex"
    mocker.patch('requests.get', return_value='<bibsonomy stat="ok"><posts start="0" end="0"/></bibsonomy>')
    res = exporter.callPumaAPI(url, data={}, method="get", expectedCode=200)

    assert res["stat"] == "ok"


def test_createAndDeletePost(credentials, mocker, exporter):
    url = credentials["puma"]["baseUrl"] + "users/" + credentials["puma"]["user"] + "/posts?resourcetype=bibtex"
    data = {"post": {
        "bibtex": {"author": "Test, Testine", "bibtexKey": "test" + exporter.randomString(5), "entrytype": "dataset",
                   "title": "Testdataset", "year": "2019"}, "tag": [{"name": "forschungsdaten"}, {"name": "DaRUS"}],
        "user": {"name": credentials["puma"]["user"]}, "description": "Test Dataset"}}
    res = exporter.callPumaAPI(url, data=data, method="post")

    assert res["stat"] == "ok"
    hashString = res["resourcehash"]
    assert hashString is not None

    url2 = credentials["puma"]["baseUrl"] + "users/" + credentials["puma"]["user"] + "/posts/" + hashString
    res = exporter.callPumaAPI(url2, data={}, method="delete", expectedCode=200)
    assert res["stat"] == "ok"
