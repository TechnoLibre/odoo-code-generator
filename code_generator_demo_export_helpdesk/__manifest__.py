# -*- coding: utf-8 -*-

{
    'name': 'Setup testing environment for export data from helpdesk code generator',
    'author': 'TechnoLibre',
    'license': 'AGPL-3',
    'depends': [
        'code_generator',
        'helpdesk_mgmt'
    ],
    'data': [
    ],
    'installable': True,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
