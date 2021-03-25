{
    'name': 'Code Generator - Cron',
    'version': '12.0.0',
    'summary': 'Code Generator - Create cron module',
    'description': 'Code generator builder to create cron for module installation',
    'author': 'Mathben (mathben@technolibre.ca)',
    'category': 'Extra Tools',
    'depends': [
        'code_generator',
        'code_generator_hook'
    ],
    'installable': True,
    'data': [
        'views/code_generator.xml',
        'views/ir_cron_views.xml',
    ]
}
