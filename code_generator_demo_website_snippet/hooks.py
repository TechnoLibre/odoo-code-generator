from odoo import _, api, models, fields, SUPERUSER_ID

MODULE_NAME = "demo_website_snippet"


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
            "category_id": env.ref("base.module_category_website").id,
            "enable_sync_code": True,
            # "path_sync_code": path_module_generate,
        }

        # TODO HUMAN: enable your functionality to generate
        value["enable_generate_website_snippet"] = True
        value["enable_generate_website_snippet_javascript"] = True
        value["generate_website_snippet_type"] = "effect"  # content,effect,feature,structure
        value["enable_sync_template"] = False
        value["post_init_hook_show"] = False
        value["uninstall_hook_show"] = False
        value["post_init_hook_feature_code_generator"] = False
        value["uninstall_hook_feature_code_generator"] = False

        value["hook_constant_code"] = f'MODULE_NAME = "{MODULE_NAME}"'

        code_generator_id = env["code.generator.module"].create(value)

        # Add dependencies
        lst_depend = [
            "website",
        ]
        lst_dependencies = env["ir.module.module"].search([("name", "in", lst_depend)])
        for depend in lst_dependencies:
            value = {
                "module_id": code_generator_id.id,
                "depend_id": depend.id,
                "name": depend.display_name,
            }
            env["code.generator.module.dependency"].create(value)

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
