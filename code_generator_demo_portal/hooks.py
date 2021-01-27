from odoo import _, api, models, fields, SUPERUSER_ID

MODULE_NAME = "demo_portal"


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # The path of the actual file
        # path_module_generate = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

        short_name = MODULE_NAME.replace("_", " ").title()

        # Add code generator
        value = {
            "shortdesc": short_name,
            "name": MODULE_NAME,
            "license": "AGPL-3",
            "author": "TechnoLibre",
            "website": "https://technolibre.ca",
            "application": True,
            "enable_sync_code": True,
            # "path_sync_code": path_module_generate,
        }

        # TODO HUMAN: enable your functionality to generate
        value["enable_sync_template"] = True
        value["post_init_hook_show"] = False
        value["uninstall_hook_show"] = False
        value["post_init_hook_feature_code_generator"] = False
        value["uninstall_hook_feature_code_generator"] = False

        value["hook_constant_code"] = f'MODULE_NAME = "{MODULE_NAME}"'

        code_generator_id = env["code.generator.module"].create(value)

        # Add dependencies
        # TODO HUMAN: update your dependencies
        lst_depend = [
            "portal",
        ]
        lst_dependencies = env["ir.module.module"].search([("name", "in", lst_depend)])
        for depend in lst_dependencies:
            value = {
                "module_id": code_generator_id.id,
                "depend_id": depend.id,
                "name": depend.display_name,
            }
            env["code.generator.module.dependency"].create(value)

        # Add Demo Model Portal
        value = {
            "name": "demo_model_portal",
            "model": "demo.model.portal",
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_demo_model_portal = env["ir.model"].create(value)

        ##### Begin Field
        value_field_demo_binary = {
            "name": "demo_binary",
            "model": "demo.model.portal",
            "field_description": "Binary demo",
            "ttype": "binary",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_binary)

        value_field_demo_boolean = {
            "name": "demo_boolean",
            "model": "demo.model.portal",
            "field_description": "Boolean demo",
            "ttype": "boolean",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_boolean)

        value_field_demo_char = {
            "name": "demo_char",
            "model": "demo.model.portal",
            "field_description": "Char demo",
            "ttype": "char",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_char)

        value_field_demo_date = {
            "name": "demo_date",
            "model": "demo.model.portal",
            "field_description": "Date demo",
            "ttype": "date",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_date)

        value_field_demo_date_time = {
            "name": "demo_date_time",
            "model": "demo.model.portal",
            "field_description": "Datetime demo",
            "ttype": "datetime",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_date_time)

        value_field_demo_float = {
            "name": "demo_float",
            "model": "demo.model.portal",
            "field_description": "Float demo",
            "ttype": "float",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_float)

        value_field_demo_html = {
            "name": "demo_html",
            "model": "demo.model.portal",
            "field_description": "HTML demo",
            "ttype": "html",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_html)

        value_field_demo_integer = {
            "name": "demo_integer",
            "model": "demo.model.portal",
            "field_description": "Integer demo",
            "ttype": "integer",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_integer)

        value_field_demo_many2many = {
            "name": "demo_many2many",
            "model": "demo.model.portal",
            "field_description": "Many2many demo",
            "ttype": "many2many",
            "comodel_name": "demo.model_2.portal",
            "relation": "demo.model_2.portal",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_many2many)

        value_field_demo_selection = {
            "name": "demo_selection",
            "model": "demo.model.portal",
            "field_description": "Selection demo",
            "ttype": "selection",
            "selection": str(list()),
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_selection)

        # Hack to solve field name
        field_x_name = env["ir.model.fields"].search([("model_id", "=", model_demo_model_portal.id), ("name", "=", "x_name")])
        field_x_name.name = "name"
        model_demo_model_portal.rec_name = "name"
        ##### End Field

        # Add Demo Model 2 Portal
        value = {
            "name": "demo_model_2_portal",
            "model": "demo.model_2.portal",
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_demo_model_2_portal = env["ir.model"].create(value)

        ##### Begin Field
        value_field_demo_many2one = {
            "name": "demo_many2one",
            "model": "demo.model_2.portal",
            "field_description": "Many2one",
            "ttype": "many2one",
            "comodel_name": "demo.model.portal",
            "relation": "demo.model.portal",
            "model_id": model_demo_model_2_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_many2one)

        # Hack to solve field name
        field_x_name = env["ir.model.fields"].search([("model_id", "=", model_demo_model_2_portal.id), ("name", "=", "x_name")])
        field_x_name.name = "name"
        model_demo_model_2_portal.rec_name = "name"

        # Added one2many field, many2many need to be creat before add one2many
        value_field_demo_one2many = {
            "name": "demo_one2many",
            "model": "demo.model.portal",
            "field_description": "One2Many demo",
            "ttype": "one2many",
            "comodel_name": "demo.model_2.portal",
            "relation": "demo.model_2.portal",
            "relation_field": "demo_many2one",
            "model_id": model_demo_model_portal.id,
        }
        env["ir.model.fields"].create(value_field_demo_one2many)

        ##### End Field

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
        code_generator_id = env["code.generator.module"].search([("name", "=", MODULE_NAME)])
        if code_generator_id:
            code_generator_id.unlink()
