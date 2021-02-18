{
    'name': 'Demo website data',
    'category': 'Website',
    'summary': 'Exported Data from website',
    'version': '12.0.1.0',
    'author': 'TechnoLibre',
    'website': 'https://technolibre.ca',
    'license': 'AGPL-3',
    'depends': ['website'],
    'data': [
        'data/ir_ui_view.xml',
        'data/website_page.xml',
        'data/website_menu.xml',
    ],
    'installable': True,
    'pre_init_hook': 'pre_init_hook',
}
