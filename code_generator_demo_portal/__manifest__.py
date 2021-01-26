{
    'name': 'Code Generator Demo Portal',
    'version': '12.0.1.0',
    'author': 'TechnoLibre',
    'website': 'https://technolibre.ca',
    'license': 'AGPL-3',
    'application': True,
    'depends': [
        'code_generator',
        'code_generator_hook',
        'code_generator_portal',
    ],
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
