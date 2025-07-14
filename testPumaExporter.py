import logging
import json
from pumaExport import Exporter

logging.basicConfig(filename="logs/pumaExport.log", level=logging.DEBUG)

with open("cred/credentials.json", "r") as cred_file:
    credentials = json.load(cred_file)
    credentials["unibiblio"]["email"] = "<testmail>"
    credentials["puma"]["mailer"] = "True"

# exporter = Exporter()
exporter = Exporter(credentials)


def pumaExport(dv="ibc"):
    datasets = exporter.getDatasetsByDataverse(dv)
    p_datasets = exporter.getAllDatasetsFromUniBiblio()
    if not bool(p_datasets):
        exit("Dataset from PUMA is empty. puma-export service will fail!")
    files = exporter.writeExportFiles(datasets, p_datasets, dv)
    print(files)
    if credentials["puma"]["mailer"] == "True":
        exporter.sendMailToUniBiblio(files, credentials["puma"]["mailHost"])
        return {"message": "PUMA Export was sent"}, 200
    else:
        return {
            "message": "PUMA export result files were written, but not send due to configuration. To send the export result files set the puma-mailer configuration option to True in cred/credentials.json"}


msg = pumaExport("ibc")
print(msg)
