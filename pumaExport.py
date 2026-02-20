import os
import random
import re
import smtplib
import string
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from datetime import datetime, timedelta

import lxml.html
import json

import requests
from requests.auth import HTTPBasicAuth

from exporterExceptions import ApiCallFailedException

def remove_html_markup(s):
    tag = False
    quote = False
    out = ""

    for c in s:
        if c == "<" and not quote:
            tag = True
        elif c == ">" and not quote:
            tag = False
        elif (c == '"' or c == "'") and tag:
            quote = not quote
        elif not tag:
            out = out + c

    return out

def cleanString(toBeCleaned):
    return remove_html_markup(str(toBeCleaned).replace("\r", "").replace("\n", " ").replace('"', "'"))


def isDaRUSdoi(doi: str):
    doiUpper = doi.upper()
    if doiUpper.find("10.18419/DARUS") != -1:
        return True
    else:
        return False

class Exporter:

    credentials = {}

    def __init__(self, credentials=None):
        if credentials is None:
            credentials = {}
        if not credentials:
            with open("cred/credentials.json", "r") as cred_file:
                credentials = json.load(cred_file)

                if credentials["puma"]["apiKey"] is None:
                    credentials["puma"]["apiKey"] = os.environ['APIKEY']

                if credentials["puma"]["user"] is None:
                    credentials["puma"]["user"] = os.environ['USER']


        self.credentials = credentials

    def getDarusSet(self, pid):
        keysAndValues = {"authors": [], "affiliation": [], "authorAffiliation": [], "authorOrcids": [], "key": "",
                         "datasetDescription": "", "howpublished": "Dataset", "relatedPub": "", "datasetSubTitle": ""}

        if isDaRUSdoi(pid):
            try:
                resFields = self.callDarusAPI(
                    url="{}api/datasets/:persistentId/?persistentId={}".format(self.credentials["darus"]["apiBaseUrl"], pid),
                    ApiKey=False, )
                version = self.getVersion(resFields)
                if version == "DRAFT" or version == "0.0":
                    return keysAndValues
                if "1.0" != self.getVersion(resFields):
                    keysAndValues["url"] = "{}?version={}.{}".format(resFields['persistentUrl'],
                        resFields['latestVersion']['versionNumber'], resFields['latestVersion']['versionMinorNumber'])
                keysAndValues["year"] = resFields['publicationDate'][:4]
                if resFields['protocol'] == "doi":
                    keysAndValues["doi"] = '{}/{}'.format(resFields['authority'], resFields['identifier'])
                if 'codeMeta20' in resFields['latestVersion']['metadataBlocks'] and len(
                        resFields['latestVersion']['metadataBlocks']['codeMeta20']['fields']) > 0:
                    keysAndValues["howpublished"] = "Software"
                fields = resFields['latestVersion']['metadataBlocks']['citation']['fields']
                for f in fields:
                    if f["typeName"] == "dsDescription":
                        for d in f["value"]:
                            keysAndValues["datasetDescription"] += (self.removeHTML(d["dsDescriptionValue"]["value"]) + " ")
                    if f["typeName"] == "author":
                        for a in f["value"]:
                            if "authors" not in keysAndValues:
                                keysAndValues["authors"] = []
                            if "affiliation" not in keysAndValues:
                                keysAndValues["affiliation"] = []
                            keysAndValues["authors"].append(a["authorName"]["value"])
                            keysAndValues["key"] += a["authorName"]["value"].split(", ")[0]
                            affil = ""
                            if "authorAffiliation" in a:
                                if "expandedvalue" in a["authorAffiliation"]:
                                    affil = a["authorAffiliation"]["expandedvalue"]["termName"]
                                else:
                                    affil = a["authorAffiliation"]["value"]
                            if affil not in keysAndValues["affiliation"] and affil != '':
                                keysAndValues["affiliation"].append(
                                    affil if "University of Stuttgart" not in affil and "Universität Stuttgart" not in affil else "University of Stuttgart")
                            keysAndValues["authorAffiliation"].append("{}/{}".format(a["authorName"]["value"], affil))

                            if "authorIdentifier" in a:
                                if "authorIdentifierScheme" not in a or a["authorIdentifierScheme"]["value"] != "ORCID":
                                    print("no orcid id for {} in dataset {}".format(a["authorIdentifier"]["value"], pid))
                                else:
                                    keysAndValues["authorOrcids"].append(
                                        "{}/{}".format(a["authorName"]["value"], a["authorIdentifier"]["value"], ))

                    if f["typeName"] == "title":
                        keysAndValues["datasetTitle"] = f["value"]

                    if f["typeName"] == "subtitle":
                        keysAndValues["datasetSubTitle"] = f["value"]

                    if f["typeName"] == "publication":
                        pub = f["value"][0]
                        relatedPub = "Related to: "
                        if "publicationCitation" in pub:
                            relatedPub = "{}{}".format(relatedPub, pub["publicationCitation"]["value"])
                            relatedPub = (relatedPub if relatedPub[-1:] != "." else relatedPub[:-1])
                        if "publicationIDNumber" in pub and "publicationIDType" in pub:
                            relPubId = "{}: {}".format(pub["publicationIDType"]["value"], pub["publicationIDNumber"]["value"], )
                            if relatedPub.find(relPubId) == -1:
                                relatedPub = "{}. {}".format(relatedPub, relPubId)
                        keysAndValues["relatedPub"] = self.removeNewLines(self.removeHTML(relatedPub))
            except ApiCallFailedException as e:
                print("502", str(e))
            return keysAndValues
        return None

    def genBibTex(self, pid):
        setList = self.getDarusSet(pid)
        if not setList is None:
            authors = setList["authors"]
            datasetTitle = setList["datasetTitle"] if "datasetTitle" in setList else ""
            datasetSubTitle = setList["datasetSubTitle"] if "datasetSubTitle" in setList else ""
            datasetDescription = (setList["datasetDescription"] if "datasetDescription" in setList else "")
            year = setList["year"] if "year" in setList else ""
            doi = setList["doi"] if "doi" in setList else ""
            url = setList["url"] if "url" in setList else ""
            authorOrcids = setList["authorOrcids"]
            authorAffiliation = setList["authorAffiliation"]
            key = setList["key"]
            howpublished = setList["howpublished"]
            relatedPub = setList["relatedPub"] if "relatedPub" in setList else ""
            bibtexStr = ""

            if "University of Stuttgart" in setList["affiliation"] or "Universität Stuttgart" in setList["affiliation"]:
                key += year + datasetTitle.split(" ")[0] + self.randomString(8)
                template = self.credentials["puma"]["bibTexTemplate"]
                datasetTitle = self.genTitle(datasetTitle, datasetSubTitle)
                values = {"authors": self.joinAuthors(authors), "key": key.replace(" ", ""),
                          "description": self.removeNewLines(datasetDescription), "doi": doi, "howpublished": howpublished,
                          "relatedPub": relatedPub, "title": datasetTitle, "year": year, "url": url,
                          "affiliation": ", ".join(authorAffiliation), "orcid": ", ".join(authorOrcids), }
                fh = open(template)
                bibtexStr = Template(fh.read()).safe_substitute(values)
                fh.close()
            return bibtexStr
        return {}

    @staticmethod
    def getVersion(resFields):
        if "latestVersion" in resFields:
            if resFields["latestVersion"]["versionState"] == "RELEASED":
                versionMajor = resFields["latestVersion"]["versionNumber"]
                versionMinor = resFields["latestVersion"]["versionMinorNumber"]
                return "{}.{}".format(versionMajor, versionMinor)

            else:
                print("no version for dataset", "{}/{}".format(resFields["authority"], resFields["identifier"]),
                      resFields["latestVersion"]["versionState"], )
                return "DRAFT"
        else:
            print("no latest version for dataset", "{}/{}".format(resFields["authority"], resFields["identifier"]), )
            return "0.0"

    @staticmethod
    def removeHTML(strElement):
        return lxml.html.fromstring(strElement).text_content()

    @staticmethod
    def randomString(stringLength=6):
        return "".join([random.choice(string.ascii_letters) for _ in range(stringLength)])

    def getDatasets(self, toFilter, validDataverses):
        datasets = []
        start = 0
        # total = 0
        perPage = 100
        test = True
        while test:
            url = ("{}api/search?q=*&fq=publicationStatus:Published&start={}&per_page={}&type=dataset{}".format(
                self.credentials["darus"]["apiBaseUrl"], start, perPage, toFilter))
            try:
                data = self.callDarusAPI(url)
                total = data["total_count"]
                start = start + perPage
                for ds in data["items"]:
                    if len(validDataverses) == 0 or ds["identifier_of_dataverse"] in validDataverses:
                        datasets.append(ds["global_id"])
                    else:
                        print("dataset {}: dataverse_id {} not in valid dataverses {}".format(ds["global_id"],
                                                                                              ds["identifier_of_dataverse"],
                                                                                              validDataverses))
                test = start < total
            except ApiCallFailedException as e:
                print("Call failed:", str(e))
                test = False
        return datasets

    def getDatasetsSince(self, date):
        now = datetime.now() + timedelta(days=1)
        timeformat = "%Y-%m-%dT00:00:00Z"
        toFilter = "&fq=dateSort:[{}+TO+{}]".format(date.strftime(timeformat), now.strftime(timeformat))
        return self.getDatasets(toFilter, {})

    def getDatasetsByDataverse(self, dataverse):
        dvs = self.getSubDataverses(dataverse)
        dvs.append(dataverse)

        toFilter = "&subtree={}".format(dataverse)
        return self.getDatasets(toFilter, dvs)

    def getTopLevelDataverses(self):
        url = "{}/api/dataverses/{}/contents".format(self.credentials["darus"]["apiBaseUrl"], ":root")
        dvs = []
        try:
            results = self.callDarusAPI(url, ApiKey=False)
            for dv in results:
                if dv["type"] == "dataverse":
                    url_dv = "{}/api/dataverses/{}".format(self.credentials["darus"]["apiBaseUrl"], dv["id"])
                    details = self.callDarusAPI(url_dv)
                    dvs.append(details["alias"])
            return dvs
        except ApiCallFailedException as e:
            print("Call failed:", str(e))

    def getSubDataverses(self, dv):
        dvs = []
        start = 0
        # total = 0
        perPage = 100
        test = True
        while test:
            url = "{}api/search?q=*&fq=publicationStatus:Published&start={}&per_page={}&type=dataverse&subtree={}".format(
                self.credentials["darus"]["apiBaseUrl"], start, perPage, dv)
            try:
                data = self.callDarusAPI(url)
                total = data["total_count"]
                start = start + perPage
                for subdv in data["items"]:
                    dvs.append(subdv["identifier"])
                test = start < total
            except ApiCallFailedException as e:
                print("Call failed:", str(e))
                test = False
        return dvs

    def getPumaEntryByDOI(self, posts, doi):
        result = []
        for post in posts:
            # print("post:", post)
            if self.checkDOI(post, doi):
                result.append(post)
        return result

    def checkDOI(self, post, doi):
        if "bibtex" not in post or "misc" not in post["bibtex"]:
            print("No valid PUMA post:", post)
            return False
        return self.getDOI(post["bibtex"]["misc"]) == doi

    @staticmethod
    def getDOI(stringValue):
        doi = ""
        result = re.search(r"doi\s*=\s*\{(.*?)}", stringValue)

        if result is not None:
            doi = result.group(1)

        return doi

    @staticmethod
    def getShortDOI(stringValue):
        doi = ""
        result = re.search(r"10\.\d{5}/DARUS-(\d+)", stringValue)
        if result is not None:
            doi = "DARUS+" + result.group(1)
        return doi

    def getAllDatasetsFromUniBiblio(self):
        posts = {}
        start = 0
        step = 100
        ok = True
        while ok:
            end = start + step
            url = ("{}posts?user=unibiblio&tags=unibibliografie+darus&resourcetype=publication&format=json&start={}&end={"
                   "}").format(
                self.credentials["puma"]["baseUrl"], start, end)
            start = end
            # print(url)

            try:
                data = self.callPumaAPI(url, {}, expectedCode=200, method="get")
            except ApiCallFailedException as e:
                print("Call failed:", str(e))
                return None
            if data["stat"] != "ok":
                print("Call not ok:", data["stat"])
                return None
            if "post" not in data["posts"]:
                ok = False
            else:
                for post in data["posts"]["post"]:
                    posts[self.getDOI(post["bibtex"]["misc"])] = self.genDatasetFromPost(post)
        return posts

    def getDatasetFromUniBiblio(self, doi):
        posts = []
        start = 0
        step = 100
        ok = True
        while ok:
            end = start + step
            url = ("{}posts?user=unibiblio&search={"
                   "}&tags=unibibliografie+darus&resourcetype=publication&format=json&start={}&end={}").format(
                self.credentials["puma"]["baseUrl"], self.getShortDOI(doi), start, end)
            start = end
            # print(url)

            try:
                data = self.callPumaAPI(url, {}, expectedCode=200, method="get")
            except ApiCallFailedException as e:
                print("Call failed:", str(e))
                return None
            if data["stat"] != "ok":
                print("Call not ok:", data["stat"])
                return None
            if "post" not in data["posts"]:
                ok = False
            else:
                posts.extend(self.getPumaEntryByDOI(data["posts"]["post"], doi))
        if len(posts) == 0:
            print("No entry of doi {} in Uni-Bibliography".format(doi))
            return None
        elif len(posts) > 1:
            print("More than one entry of doi {} in Uni-Bibliography: {} entries".format(doi, len(posts)))
        # print(len(posts), "posts:", posts )
        return self.genDatasetFromPost(posts[0])

    @staticmethod
    def genDatasetFromPost(post):
        dataset = {"bibtex": post["bibtex"], "tags": [], "user": post["user"]}
        for tag in post["tag"]:
            dataset["tags"].append(tag["name"])
        return dataset

    @staticmethod
    def joinAuthors(authorlist, joinstr=" and "):
        return joinstr.join(authorlist)

    @staticmethod
    def genTitle(datasetTitle, datasetSubTitle):
        if datasetSubTitle != "":
            datasetTitle = "{} : {}".format(datasetTitle, datasetSubTitle)
        return datasetTitle

    def genPumaURL(self, puma_ds):
        return "{}bibtex/{}/{}".format(self.credentials["puma"]["baseUrl"].replace("/api", ""), puma_ds["bibtex"]["intrahash"],
                                       puma_ds["user"]["name"], )

    @staticmethod
    def genChangeMessage(field, version_ub, version_darus):
        msg = "Geändertes Feld: {}, \n  Version Unibiblio: '{}', \n  Version DaRUS:  '{}'".format(field, version_ub,
                                                                                                  version_darus)
        return msg

    @staticmethod
    def removeNewLines(text):
        return text.replace("\n", "").replace("\r", "")

    @staticmethod
    def removeBrackets(text):
        return text.replace("}", "").replace("{", "")

    @staticmethod
    def replaceDash(text):
        return text.replace("‐", "-").replace("‑", "-")

    def getChanges(self, darus_ds, puma_ds):
        changes = []
        p_ds = puma_ds["bibtex"]

        p_title = self.removeBrackets(p_ds["title"])
        d_title = self.replaceDash(self.genTitle(darus_ds["datasetTitle"], darus_ds["datasetSubTitle"]))
        if p_title != d_title:
            changes.append(self.genChangeMessage("Titel", p_title, d_title))

        p_author = self.removeBrackets(p_ds["author"])
        if p_author != self.joinAuthors(darus_ds["authors"]):
            changes.append(self.genChangeMessage("Author", p_ds["author"], self.joinAuthors(darus_ds["authors"])))

        if p_ds["howpublished"] != darus_ds["howpublished"]:
            changes.append(self.genChangeMessage("howpublished", p_ds["howpublished"], darus_ds["howpublished"]))

        if p_ds["year"] != darus_ds["year"]:
            changes.append(self.genChangeMessage("year", p_ds["year"], darus_ds["year"]))

        misc = self.removeNewLines(p_ds["misc"])
        p_a = re.search(r"affiliation\s*=\s*\{(.*?)}", misc)

        p_affiliation = ""
        if p_a is not None:
            p_affiliation = p_a.group(1)

        p_o = re.search(r"orcid-numbers\s*=\s*\{(.*?)}", misc)

        p_orcid = ""
        if p_o is not None:
            p_orcid = p_o.group(1)

        p_doi = self.getDOI(misc)

        d_affiliation = ", ".join(darus_ds["authorAffiliation"])
        d_orcid = ", ".join(darus_ds["authorOrcids"])

        if p_affiliation != d_affiliation:
            changes.append(self.genChangeMessage("affiliation", p_affiliation, d_affiliation))

        if p_orcid != d_orcid:
            changes.append(self.genChangeMessage("orcid", p_orcid, d_orcid))

        if p_doi != darus_ds["doi"]:
            changes.append(self.genChangeMessage("doi", p_doi, darus_ds["doi"]))

        p_relpub = p_ds["note"] if "note" in p_ds else ""
        d_relpub = self.replaceDash(self.removeNewLines(darus_ds["relatedPub"]))
        if p_relpub != d_relpub:
            changes.append(self.genChangeMessage("related publication", p_relpub, d_relpub))

        return changes

    def writeExportFiles(self, darusDatasets, pumaDatasets, dv="darus"):
        now = datetime.now()
        exportDate = now.strftime("%Y-%m-%d")

        filename = "output/{}_{}_export.bib".format(exportDate, dv)
        filename_changes = "output/{}_{}_changes.txt".format(exportDate, dv)
        # datasets = getDatasetsSince(last)
        with open(filename, "w", encoding="utf_8") as out:
            with open(filename_changes, "w", encoding="utf_8") as changes_out:
                for ds in darusDatasets:
                    doi = ds[4:] if ds[0:4] == "doi:" else ds
                    doi = doi.lower()
                    
                    if doi not in pumaDatasets:
                        bibtex = self.genBibTex(ds)
                        print("new dataset {}".format(ds))
                        out.writelines(bibtex)
                    else:
                        darus_ds = self.getDarusSet(ds)
                        if not darus_ds is None:
                            puma_ds = pumaDatasets[doi]
                            changes = self.getChanges(darus_ds, puma_ds)
                            if len(changes) > 0:
                                print("changed dataset {}".format(ds))
                                ch_str = "Änderungen in Datensatz {}:\n".format(ds)
                                ch_str += "\n".join(changes)
                                ch_str += "\nUnibibliolink: {}\n\n".format(self.genPumaURL(puma_ds))
                                changes_out.writelines(ch_str)
        files = [filename, filename_changes]
        return files

    def sendMailToUniBiblio(self, files, mailHost):
        fromAdr = "Darus Export <fokus@izus.uni-stuttgart.de>"
        toAdr = self.credentials["unibiblio"]["email"]
        message = MIMEMultipart()
        message["From"] = Header(fromAdr)
        message["To"] = Header(toAdr)
        message["Subject"] = Header("DaRUS Export")

        now = datetime.now()
        body = "wöchentlicher DaRUS Export von neuen und veränderten Datensätzen vom {}".format(now.strftime("%Y-%m-%d"))

        message.attach(MIMEText(body, "plain", "utf-8"))

        for file in files:
            att_name = os.path.basename(file)
            f = open(file, "rb")
            att = MIMEApplication(f.read(), _subtype="txt")
            f.close()
            att.add_header("Content-Disposition", "attachment", filename=att_name)
            message.attach(att)

        s = smtplib.SMTP(mailHost)
        s.sendmail(fromAdr, toAdr, message.as_string())
        s.quit()


    def callDarusAPI(self, url, method="get", data=None, expectedCode=200, nodata=False, contentType="application/json",
                     ApiKey=True, ):
        dsReq = None
        if ApiKey:
            headers = {"content-type": contentType, "X-Dataverse-key": self.credentials["darus"]["apiKey"], }
        else:
            headers = {}
        if method == "get":
            dsReq = requests.get(url, headers=headers, timeout=80)
        elif method == "post":
            if data is not None:
                dsReq = requests.post(url, headers=headers, data=json.dumps(data))
            else:
                dsReq = requests.post(url, headers=headers)
        elif method == "put":
            if data is not None:
                dsReq = requests.put(url, headers=headers, data=json.dumps(data))
            else:
                dsReq = requests.put(url, headers=headers)
        elif method == "delete":
            dsReq = requests.delete(url, headers=headers)
        # get authors

        if nodata:
            if dsReq.status_code == expectedCode:
                return True
            else:
                raise ApiCallFailedException("DaRUS-Call of {} failed: {} {}".format(url, dsReq.reason, dsReq.text))

        resDapi = dsReq.json()
        if dsReq.status_code == expectedCode and resDapi["status"] == "OK":
            return resDapi["data"]
        else:
            raise ApiCallFailedException("DaRUS-Call of {} failed: {} {}".format(url, dsReq.reason, dsReq.text))

    def callPumaAPI(self, url, data, expectedCode=201, method="post", ):
        headers = {"Content-Type": "application/json"}

        user = self.credentials["puma"]["user"]
        pw = self.credentials["puma"]["apiKey"]

        if user is None or pw is None:
            raise ApiCallFailedException("No PUMA Credentials")

        if method not in ["multipart", "get", "post", "put", "delete"]:
            raise ApiCallFailedException("Method {} not supported".format(method))
        tr = None
        try:
            if method == "get":
                tr = requests.get(url, data=json.dumps(data), auth=HTTPBasicAuth(user, pw)
                                  , headers=headers
                                  , timeout=40)
            elif method == "post":
                tr = requests.post(url, data=json.dumps(data), auth=HTTPBasicAuth(user, pw), headers=headers, )
            elif method == "multipart":
                tr = requests.post(url, files=data, auth=HTTPBasicAuth(user, pw))
            elif method == "put":
                tr = requests.put(url, data=json.dumps(data), auth=HTTPBasicAuth(user, pw), headers=headers, )
            elif method == "delete":
                tr = requests.delete(url, data=json.dumps(data), auth=HTTPBasicAuth(user, pw), headers=headers, )
        except Exception as e:
            raise ApiCallFailedException("PUMA-Call raised Exception: {}".format(e))
        if tr.status_code != expectedCode:
            raise ApiCallFailedException(
                "PUMA-Call failed: {code} {reason} {text}".format(code=tr.status_code, reason=tr.reason, text=tr.text))
        return tr.json()

    def getPUMAExport(self, datasetId):
        authors = []
        datasetTitle = ""
        datasetDescription = ""
        year = datetime.now().strftime("%Y")
        doi = ""
        # url = ""
        authorOrcids = []
        authorAffiliation = []
        key = ""
        relatedPublications = []

        if isDaRUSdoi(datasetId):
            try:
                resFields = self.callDarusAPI(
                    "{}/api/datasets/:persistentId/?persistentId={}".format(self.credentials["darus"]["apiBaseUrl"], datasetId))
                url = resFields["persistentUrl"]
                if resFields["protocol"] == "doi":
                    doi = "{}/{}".format(resFields["authority"], resFields["identifier"])
                fields = resFields["latestVersion"]["metadataBlocks"]["citation"]["fields"]
                for f in fields:
                    if f["typeName"] == "dsDescription":
                        for d in f["value"]:
                            datasetDescription += d["dsDescriptionValue"]["value"] + " "
                    if f["typeName"] == "author":
                        for a in f["value"]:
                            authors.append(a["authorName"]["value"])
                            key += a["authorName"]["value"].split(", ")[0]
                            authorAffiliation.append(a["authorAffiliation"]["value"])
                            if "authorIdentifier" in a and a["authorIdentifierScheme"]["value"] == "ORCID":
                                authorOrcids.append("{}/{}".format(a["authorName"]["value"], a["authorIdentifier"]["value"], ))

                    if f["typeName"] == "title":
                        datasetTitle = f["value"]

                    if f["typeName"] == "publication":
                        for p in f["value"]:
                            pubstring = p["publicationCitation"]["value"]
                            if "publicationIDType" in p and "publicationIDNumber" in p:
                                pubstring += " ({}:{})".format(p["publicationIDType"]["value"], p["publicationIDNumber"]["value"], )
                            # logging.debug(pubstring)
                            relatedPublications.append(pubstring)

            except ApiCallFailedException as e:
                ret = json.loads(str(e)[str(e).index('{"status"'):])
                return ret


            key += year + datasetTitle.split(" ")[0] + self.randomString(8)
            dataType = "Dataset"
            relPub = ("Related Publication: {}".format(cleanString(",\n ".join(relatedPublications))) if len(relatedPublications) > 0 else "")
            template = self.credentials["puma"]["bibTexTemplate"]
            index = 0
            for author in authors:
                if re.search(", \\b[\\D-]+", author) is None:
                    authors[index] = "{" + author + "}"
                    if len(authors) == 1:
                        authors[index]="{" + authors[index] + "}"
                index = index + 1
            values = {"authors": " and ".join(authors), "user": self.credentials["puma"]["user"], "key": key,
                      "description": cleanString(datasetDescription), "doi": doi, "title": cleanString(datasetTitle), "url": url, "year": year,
                      "affiliation": cleanString(" and ".join(authorAffiliation)), "orcid": " and ".join(authorOrcids), "type": dataType,
                      "relPub": relPub, }
            fh = open(template)
            bibtexStr = Template(fh.read()).safe_substitute(values)
            fh.close()
            template = self.credentials["puma"]["jsonTemplate"]
            fh = open(template)
            jsonStr = Template(fh.read()).safe_substitute(values)
            fh.close()

            # logging.debug('jsonStr: ' + jsonStr)
            jsonDict = {"main": ("", jsonStr.encode().decode("utf-8-sig"), "application/json"),
                        "bibtex": ("", bibtexStr.encode().decode("utf-8-sig"), "text/bibtex"), }
            return jsonDict
        return {}
