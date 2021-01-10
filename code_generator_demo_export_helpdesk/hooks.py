from odoo import _, api, models, fields, SUPERUSER_ID
import os

MODULE_NAME = "demo_helpdesk_data"


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # path_module_generate = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

        model_name = "helpdesk.ticket"

        if not len(env[model_name].search([])):
            value1 = {
                "name": "test1",
                "description": "Description 1",
            }
            ticket1 = env[model_name].create(value1)
            value2 = {
                "name": "test2",
                "description": "Description 2",
            }
            ticket2 = env[model_name].create(value2)
            ticket2.assign_to_me()

        # Add code generator
        value = {
            "shortdesc": "Demo helpdesk data",
            "name": MODULE_NAME,
            "license": "AGPL-3",
            "author": "TechnoLibre",
            "website": "https://technolibre.ca",
            "application": False,
            # 'category_id': env.ref("base.module_category_theme").id,
            "enable_sync_code": True,
            # "path_sync_code": path_module_generate,
            # "o2m_models": [(0, 0, models_id)],
            "nomenclator_only": True,
        }
        code_generator_id = env["code.generator.module"].create(value)

        # Select models and blacklist some fields
        models_id = env["ir.model"].search([('model', '=', model_name)])
        lst_ignored_field_name = [
            "message_follower_ids",
            "message_ids",
            "message_is_follower",
            "message_partner_ids",
            "website_message_ids",
        ]

        lst_field = env["ir.model.fields"].search(
            [("model_id", "=", models_id.id), ("name", "in", lst_ignored_field_name)])

        # Generate view
        wizard_view = env['code.generator.add.model.wizard'].create({
            'code_generator_id': code_generator_id.id,
            'model_ids': [(6, 0, [models_id.id])],
            'field_ids': [(6, 0, [a.id for a in lst_field])],
            'option_blacklist': 'blacklist',
        })

        wizard_view.button_generate_add_model()

        # Generate module
        value = {
            "code_generator_ids": code_generator_id.ids
        }
        code_generator_writer = env["code.generator.writer"].create(value)


def uninstall_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # Disable association with existing model
        model_id = env["ir.model"].search([('model', '=', 'helpdesk.ticket')])
        model_id.m2o_module = None
        model_id.nomenclator = False

        code_generator_id = env["code.generator.module"].search([('name', '=', MODULE_NAME)])
        if code_generator_id:
            code_generator_id.unlink()
