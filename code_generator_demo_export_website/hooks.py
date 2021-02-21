from odoo import _, api, models, fields, SUPERUSER_ID

# import os

MODULE_NAME = "demo_website_data"
REPLACE_DEFAULT_WEBSITE = True  # This will only import default website
HIDE_OLD_WEBSITE = True


# TODO multi-site not correctly supported


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # path_module_generate = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

        # Add code generator
        value = {
            "shortdesc": "Demo website data",
            "name": MODULE_NAME,
            "license": "AGPL-3",
            "author": "TechnoLibre",
            "website": "https://technolibre.ca",
            "summary": "Exported Data from website",
            "application": False,
            "category_id": env.ref("base.module_category_website").id,
            "enable_sync_code": True,
            # "path_sync_code": path_module_generate,
            # "o2m_models": [(0, 0, models_id)],
            "nomenclator_only": True,
        }
        # Hook
        if HIDE_OLD_WEBSITE:
            value["pre_init_hook_show"] = True
            value["pre_init_hook_code"] = """with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Remove all website pages before installing data

    website_page_ids = env['website.page'].search([])
    website_menu_ids = env['website.menu'].search([])
    # TODO website doesn't support multi
    # website_page_ids.website_id = None
    # TODO replace by :
    for website_page in website_page_ids:
        website_page.website_id = None
    for website_menu in website_menu_ids:
        website_menu.website_id = None
"""

        code_generator_id = env["code.generator.module"].create(value)

        # Add dependency
        depend = "website"
        module_id = env["ir.module.module"].search([("name", "=", depend)])
        assert module_id
        value_dependency_website = {
            "module_id": code_generator_id.id,
            "name": depend,
            "depend_id": module_id[0].id
        }
        env["code.generator.module.dependency"].create(value_dependency_website)

        # Select models
        # lst_model_names = ['website.page', 'website.menu']
        # models_id = env["ir.model"].search([('model', 'in', lst_model_names)])

        # website
        if not REPLACE_DEFAULT_WEBSITE:
            website_model_id = env["ir.model"].search([("model", "=", "website")])

            lst_website_field_name = [
                "name",
                "domain",
                "company_id",
                "user_id",
                "favicon",
                # "homepage_id", # TODO this create a circular dependencies, ignore it and maybe fix that with post_init
            ]

            lst_website_field = env["ir.model.fields"].search(
                [("model_id", "=", website_model_id.id),
                 ("name", "in", lst_website_field_name)])

        # ir.ui.view
        ir_ui_view_model_id = env["ir.model"].search([("model", "=", "ir.ui.view")])

        lst_ir_ui_view_field_name = [
            "name",
            "key",
            "type",
            "arch",
        ]

        lst_ir_ui_view_field = env["ir.model.fields"].search(
            [("model_id", "=", ir_ui_view_model_id.id),
             ("name", "in", lst_ir_ui_view_field_name)])

        # website.page
        website_page_model_id = env["ir.model"].search([("model", "=", "website.page")])

        # apply whitelist
        lst_website_page_field_name = [
            "website_id",
            "website_published",
            "url",
            "view_id",
        ]

        lst_website_page_field = env["ir.model.fields"].search(
            [("model_id", "=", website_page_model_id.id),
             ("name", "in", lst_website_page_field_name)])

        # website.menu
        website_menu_model_id = env["ir.model"].search([("model", "=", "website.menu")])
        lst_ir_ui_view_field_name = [
            "name",
            "url",
            "parent_id",
            "page_id",
            "website_id",
            "sequence"
        ]
        lst_website_menu_field = env["ir.model.fields"].search(
            [("model_id", "=", website_menu_model_id.id),
             ("name", "in", lst_ir_ui_view_field_name)])

        # Generate view
        model_ids = ir_ui_view_model_id + website_page_model_id + website_menu_model_id
        if not REPLACE_DEFAULT_WEBSITE:
            model_ids += website_model_id

        lst_field = lst_ir_ui_view_field + lst_website_page_field + lst_website_menu_field
        if not REPLACE_DEFAULT_WEBSITE:
            lst_field += lst_website_field

        wizard_view = env['code.generator.add.model.wizard'].create({
            'code_generator_id': code_generator_id.id,
            'model_ids': [(6, 0, model_ids.ids)],
            'field_ids': [(6, 0, [a.id for a in lst_field])],
            'option_blacklist': 'whitelist',
        })

        wizard_view.button_generate_add_model()

        # Filter on exporting data
        # TODO bug duplicated id, need algorithm with unique key
        # TODO bug when exporting multiple website, the first is website.default_website and not the new website
        # TODO bug with long id, it cut and replace the end by ...
        # TODO missing import image
        if not REPLACE_DEFAULT_WEBSITE:
            lst_id_website = env["website"].search([]).ids
        else:
            lst_id_website = [env.ref("website.default_website").id]

        lst_id_view = [b for a in env["website.page"].search([('website_id', 'in', lst_id_website)]) for b in
                       a.view_id.ids]
        website_menu_model_id.expression_export_data = f"('website_id', 'in', {lst_id_website})"
        website_page_model_id.expression_export_data = f"('website_id', 'in', {lst_id_website})"
        ir_ui_view_model_id.expression_export_data = f"('id', 'in', {lst_id_view})"

        # Generate module
        value = {
            "code_generator_ids": code_generator_id.ids
        }
        code_generator_writer = env["code.generator.writer"].create(value)


def uninstall_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # Disable association with existing model
        lst_model_name = ['ir.ui.view', 'website.page', 'website.menu']
        model_ids = env["ir.model"].search([('model', 'in', lst_model_name)])
        for model_id in model_ids:
            model_id.m2o_module = None
            model_id.nomenclator = False

        code_generator_id = env["code.generator.module"].search([('name', '=', MODULE_NAME)])
        if code_generator_id:
            code_generator_id.unlink()
