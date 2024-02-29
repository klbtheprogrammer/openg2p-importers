# Part of openG2P. See LICENSE file for full copyright and licensing details.

{
    "name": "G2P ODK Importer",
    "category": "Connector",
    "summary": "Import records from ODK",
    "version": "15.0.0.0.1",
    "sequence": 3,
    "author": "OpenG2P",
    "website": "https://github.com/OpenG2P/openg2p-auth",
    "license": "LGPL-3",
    "depends": [
        "connector",
        "base",
        "web",
        "component",
        "queue_job",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/odk_config_views.xml",
        "views/odk_menu.xml",
        # "views/odk_import_views.xml",
    ],
    "external_dependencies": {
        "python": [
            "pyjq",
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
