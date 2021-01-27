{
    'name': 'Demo Portal',
    'version': '12.0.1.0',
    'author': 'TechnoLibre',
    'website': 'https://technolibre.ca',
    'license': 'AGPL-3',
    'application': True,
    'depends': ['portal'],
    'data': [
        'security/ir.model.access.csv',
        'views/demo_model_2_portal.xml',
        'views/demo_model_portal.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
