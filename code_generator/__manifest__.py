# -*- coding: utf-8 -*-

{
    'name': 'Code Generator',
    'summary': 'Code Generator Module',
    'description': 'A solution to export into code most of the things that we can do in Odoo, models, views, groups, '
                   'permissions, menues, etc',
    'author': 'Raisel Rodríguez Cabrera (rrcabrera@estudiantes.uci.cu), Bluisknot (bluisknot@gmail.com)',
    'category': 'Extra Tools',
    'depends': ['base'],
    'installable': True,
    'data': [
        'security/code_generator.xml',
        'security/ir.model.access.csv',
        'views/code_generator.xml',
        'views/code_generator_settings.xml',
        'views/ir_actions.xml',
        'views/ir_model.xml',
        'views/ir_uis.xml',
        'views/res_groups.xml'
    ],
    'qweb': ['static/src/xml/dashboard.xml']
}
