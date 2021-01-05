# -*- coding: utf-8 -*-

from odoo import _, api, models, fields, SUPERUSER_ID
import os

MODULE_NAME = "demo_portal"


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        path_module_generate = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'demo_portal'))

        # Add code generator
        value = {
            "shortdesc": "Demo portal",
            "name": MODULE_NAME,
            "license": "AGPL-3",
            "author": "TechnoLibre",
            "website": "https://technolibre.ca",
            "application": True,

            "enable_sync_code": True,
            "path_sync_code": path_module_generate,
        }
        code_generator_id = env["code.generator.module"].create(value)

        # Add model demo portal
        value = {
            "name": "demo_model_portal",
            "model": "demo.model.portal",
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_demo_1 = env["ir.model"].create(value)

        value_field_banana = {
            "name": "banana",
            "model": "demo.model.portal",
            "field_description": "Banana demo",
            "ttype": "boolean",
            "model_id": model_demo_1.id,
        }
        model_demo_1_field_banana = env["ir.model.fields"].create(value_field_banana)

        # Hack to solve field name
        field_x_name = env["ir.model.fields"].search([('model_id', '=', model_demo_1.id), ('name', '=', 'x_name')])
        field_x_name.name = "name"
        model_demo_1.rec_name = "name"

        # Add data
        value = {
            "banana": True,
            "name": "fds",
        }
        data_1 = env["demo.model.portal"].create(value)

        # Add model demo_2 portal
        value = {
            "name": "demo_model_2_portal",
            "model": "demo.model_2.portal",
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_demo_2 = env["ir.model"].create(value)

        # Add model demo portal FIELDS
        value_field_name = {
            "name": "model_1",
            "model": "demo.model_2.portal",
            "field_description": "Model 1",
            "ttype": "many2one",
            "comodel_name": "demo.model.portal",
            "relation": "demo.model.portal",
            "model_id": model_demo_2.id,
        }
        model_demo_1_field_name = env["ir.model.fields"].create(value_field_name)

        # Hack to solve field name
        field_x_name = env["ir.model.fields"].search([('model_id', '=', model_demo_2.id), ('name', '=', 'x_name')])
        field_x_name.name = "name"
        model_demo_2.rec_name = "name"

        # Add data
        value = {
            "model_1": data_1.id,
            "name": "fds",
        }
        data_2 = env["demo.model_2.portal"].create(value)

        # Generate view
        wizard_view = env['code.generator.generate.views.wizard'].create({
            'code_generator_id': code_generator_id.id,
            'enable_generate_all': False,
            'enable_generate_portal': True,
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
