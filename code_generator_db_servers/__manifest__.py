# -*- coding: utf-8 -*-

{
    'name': 'Code Generator - Db Servers',
    'summary': 'Code Generator - Db Servers Module',
    'description': 'A solution to extend the Code Generator Module adding the capability to import into Odoo tables '
                   'and its content from other databases',
    'author': 'Bluisknot (bluisknot@gmail.com)',
    'category': 'Extra Tools',
    'depends': ['code_generator'],
    'installable': True,
    'data': [
        'security/ir.model.access.csv',
        'views/code_generator.xml',
        'data/code_generator.xml',
    ]
}
