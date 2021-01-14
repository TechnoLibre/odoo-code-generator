# -*- coding: utf-8 -*-

{
    'name': 'Code Generator',
    'version': '12.0.0',
    'summary': 'Code Generator Module',
    'description': 'A solution to export into code most of the things that we can do in Odoo, models, views, groups, '
                   'permissions, menus, etc',
    'author': 'Raisel Rodríguez Cabrera (rrcabrera@estudiantes.uci.cu), Bluisknot (bluisknot@gmail.com), '
              'Mathben (mathben@technolibre.ca)',
    'category': 'Extra Tools',
    'depends': ['base'],
    'installable': True,
    'data': [
        'security/code_generator.xml',
        'security/ir.model.access.csv',
        'wizards/code_generator_generate_views_wizard.xml',
        'wizards/code_generator_add_model_wizard.xml',
        'wizards/code_generator_add_controller_wizard.xml',
        'views/code_generator.xml',
        'views/code_generator_settings.xml',
        'views/ir_actions.xml',
        'views/ir_model.xml',
        'views/ir_uis.xml',
        'views/res_groups.xml',
    ],
    'demo': ['data/code_generator_demo.xml'],
    'post_init_hook': 'post_init_hook',
}
