from odoo import _, api, models, fields, SUPERUSER_ID
import os

MODULE_NAME = "theme_website_demo_code_generator"


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # path_module_generate = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

        # Add code generator
        value = {
            "shortdesc": "Demo theme website",
            "name": MODULE_NAME,
            "license": "AGPL-3",
            "author": "TechnoLibre",
            "website": "https://technolibre.ca",
            "application": False,
            "theme_website": True,
            'category_id': env.ref("base.module_category_theme").id,
            'sequence': 900,
            "enable_sync_code": True,
            # "path_sync_code": path_module_generate,
        }
        code_generator_id = env["code.generator.module"].create(value)

        # Generate view
        wizard_view = env['code.generator.generate.views.wizard'].create({
            'code_generator_id': code_generator_id.id,
            'enable_generate_all': False,
            'enable_generate_theme_website': True,
            'theme_website_primary_color': "#abc",
            'theme_website_secondary_color': "#def",
            'theme_website_extra_1_color': "#159",
            'theme_website_extra_2_color': "#f15",
            'theme_website_extra_3_color': "#a5c",
            'theme_website_body_color': "#1b8",
            'theme_website_footer_color': "#71f",
            'theme_website_menu_color': "#091",
            'theme_website_text_color': "#f41",
        })

        wizard_view.button_generate_views()

        # Generate module
        value = {
            "code_generator_ids": code_generator_id.ids
        }
        code_generator_writer = env["code.generator.writer"].create(value)


def uninstall_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        code_generator_id = env["code.generator.module"].search([('name', '=', MODULE_NAME)])
        if code_generator_id:
            code_generator_id.unlink()
