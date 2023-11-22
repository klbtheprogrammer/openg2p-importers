# Part of openG2P. See LICENSE file for full copyright and licensing details.

{
    "name": "G2P ODK Importer",
    "category": "Connector",
    'summary': 'Import records from ODK',
    "version": "15.0.0.0.1",
    "sequence": 3,
    "author": "Newlogic",
    "website": "https://newlogic.com/",
    "license": "LGPL-3",
    'category': 'Connector',
    "depends": [
        "connector", "base", "web",'g2p_registry_rest_api', "component", "queue_job"
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/odk_config_views.xml',
        'views/odk_import_views.xml',
        'views/odk_menu.xml',
        'data/odk_cron.xml',
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
