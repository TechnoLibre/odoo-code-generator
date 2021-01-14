# -*- coding: utf-8 -*-

{
    'name': 'Setup testing environment for website leaflet code generator',
    'author': 'TechnoLibre',
    'license': 'AGPL-3',
    'depends': [
        'code_generator',
        'code_generator_website_leaflet',
    ],
    'data': [],
    'installable': True,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
