# pumaExporter

Workflow-Installation und -Konfiguration auf dem Server im Verzeichnis 

    /srv/pumaExporter
    sudo chown -R pumaexporter: /srv/pumaExporter

Vorher: 

    sudo su pumaexporter

    rm -fr .venv/ && python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

Kopieren der systemd-Dienste:

    sudo cp puma-export.service /etc/systemd/system
    sudo cp test-puma-export.service /etc/systemd/system

Verzeichnis anlegen mit Datei

    cred/credentials.json
    output/test.txt

credentials.json

        {
          "darus":
        {
            "apiKey":"12345",
            "baseUrl":"https://darus.uni-stuttgart.de/",
            "apiBaseUrl":"http://localhost:8080/"
        },
        "puma": {
            "baseUrl": "https://puma.ub.uni-stuttgart.de/api/",
            "user": "<add PUMA User>",
            "apiKey": "<add PUMA API-Key>",
            "bibTexTemplate": "tpl_puma.bib",
            "jsonTemplate": "tpl_puma.txt",
            "mailTemplate": "tpl_mailAfterPumaExport.txt",
            "mailHost":"localhost",
            "mailer":"True"
        },
        "unibiblio": {
        "email": "<unibib-mail>"
        }
    }
    
