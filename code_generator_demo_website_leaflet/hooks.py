from odoo import _, api, models, fields, SUPERUSER_ID
import os

MODULE_NAME = "demo_website_leaflet"
MODEL_PREFIX = "demo.website_leaflet"


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # path_module_generate = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', MODULE_NAME))

        # Add code generator
        value = {
            "shortdesc": "Demo website leaflet",
            "name": MODULE_NAME,
            "license": "AGPL-3",
            "author": "TechnoLibre",
            "website": "https://technolibre.ca",
            "summary": "Leaflet integration in website",
            "application": True,
            "category_id": env.ref("base.module_category_website").id,

            "enable_sync_code": True,
            # "path_sync_code": path_module_generate,
        }
        code_generator_id = env["code.generator.module"].create(value)

        # Add dependency
        depend = "website"
        module_id = env["ir.module.module"].search([("name", "=", depend)])
        assert module_id
        value_dependency_website = {
            "module_id": code_generator_id.id,
            "name": depend,
            "depend_id": module_id.id
        }
        env["code.generator.module.dependency"].create(value_dependency_website)

        depend = "base_geoengine"
        module_id = env["ir.module.module"].search([("name", "=", depend)])
        assert module_id
        value_dependency_website = {
            "module_id": code_generator_id.id,
            "name": depend,
            "depend_id": module_id.id
        }
        env["code.generator.module.dependency"].create(value_dependency_website)

        # Add external dependency
        depend = "pyproj"
        value_dependency_website = {
            "module_id": code_generator_id.id,
            "depend": depend,
            "application_type": "python",
        }
        env["code.generator.module.external.dependency"].create(value_dependency_website)

        # Model Category
        model_category = f"{MODEL_PREFIX}.category"
        value = {
            "name": "Map Feature Category",
            "model": model_category,
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_category_id = env["ir.model"].create(value)

        # Field active
        value_field = {
            "name": "active",
            "model": model_category,
            "ttype": "boolean",
            "model_id": model_category_id.id,
            "default": True,
        }
        env["ir.model.fields"].create(value_field)

        # Field name
        value_field = {
            "name": "name",
            "model": model_category,
            "ttype": "char",
            "required": True,
            "model_id": model_category_id.id,
        }
        env["ir.model.fields"].create(value_field)

        # Field description
        value_field = {
            "name": "description",
            "model": model_category,
            "ttype": "char",
            "model_id": model_category_id.id,
        }
        env["ir.model.fields"].create(value_field)

        # Field company_id
        value_field = {
            "name": "company_id",
            "field_description": "Company",
            "comodel_name": "res.company",
            "relation": "res.company",
            "model": model_category,
            "ttype": "many2one",
            "model_id": model_category_id.id,
        }
        env["ir.model.fields"].create(value_field)

        # Field parent
        value_field = {
            "name": "parent",
            "field_description": "Parent",
            "comodel_name": model_category,
            "relation": model_category,
            "model": model_category,
            "ttype": "many2one",
            "model_id": model_category_id.id,
            "on_delete": "restrict",
        }
        env["ir.model.fields"].create(value_field)

        # Hack to solve field name when already has name
        # Ignore WARNING code_generator odoo.addons.base.models.ir_model: Two fields (name, x_name) of
        # demo.website_leaflet.category() have the same label: Name.
        field_x_name = env["ir.model.fields"].search([('model_id', '=', model_category_id.id), ('name', '=', 'x_name')])
        if field_x_name:
            field_x_name.unlink()

        # Model Map Feature
        model_map_feature = f"{MODEL_PREFIX}.map.feature"
        value = {
            "name": "Map Feature",
            "model": model_map_feature,
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_map_feature_id = env["ir.model"].create(value)

        # Field active
        value_field = {
            "name": "active",
            "model": model_map_feature,
            "ttype": "boolean",
            "model_id": model_map_feature_id.id,
            "default": True,
        }
        env["ir.model.fields"].create(value_field)

        # Field name
        value_field = {
            "name": "name",
            "model": model_map_feature,
            "ttype": "char",
            "required": True,
            "model_id": model_map_feature_id.id,
            # "is_show_whitelist_list_view": True,
        }
        env["ir.model.fields"].create(value_field)

        # Field html_text
        value_field = {
            "name": "html_text",
            "model": model_map_feature,
            "ttype": "html",
            "model_id": model_map_feature_id.id,
            "field_description": "Popup text"
        }
        env["ir.model.fields"].create(value_field)

        # Field open_popup
        value_field = {
            "name": "open_popup",
            "model": model_map_feature,
            "ttype": "boolean",
            "model_id": model_map_feature_id.id,
            "default": False,
            "field_description": "Popup opened on map",
        }
        env["ir.model.fields"].create(value_field)

        default_geo = "geo_point"
        dct_geo = {
            default_geo: "Geo Point",
            "geo_line": "Geo Line",
            "geo_polygon": "Geo Polygon",
        }
        for ttype, name in dct_geo.items():
            value_field = {
                "name": ttype,
                "model": model_map_feature,
                "model_id": model_map_feature_id.id,
                "ttype": ttype,
                "is_hide_blacklist_list_view": True,
            }
            env["ir.model.fields"].create(value_field)

        # Field type
        value_field = {
            "name": "type",
            "model": model_map_feature,
            "ttype": "selection",
            "model_id": model_map_feature_id.id,
            "selection": str(list(dct_geo.items())),
            "required": True,
            "default": "point",
            "translate": True,
        }
        a = env["ir.model.fields"].create(value_field)
        a.translate = True

        # Field category
        value_field = {
            "name": "category_id",
            "field_description": "Category",
            "comodel_name": model_category,
            "relation": model_category,
            "model": model_map_feature,
            "ttype": "many2one",
            "model_id": model_map_feature_id.id,
            "on_delete": "restrict",
        }
        env["ir.model.fields"].create(value_field)

        # Hack to solve field name when already has name
        # Ignore WARNING code_generator odoo.addons.base.models.ir_model: Two fields (name, x_name) of
        # demo.website_leaflet.category() have the same label: Name.
        field_x_name = env["ir.model.fields"].search(
            [('model_id', '=', model_map_feature_id.id), ('name', '=', 'x_name')])
        if field_x_name:
            field_x_name.unlink()

        # Model Map
        model_map = f"{MODEL_PREFIX}.map"
        value = {
            "name": "Map",
            "model": model_map,
            "m2o_module": code_generator_id.id,
            "rec_name": None,
            "nomenclator": True,
        }
        model_map_id = env["ir.model"].create(value)

        # Field active
        value_field = {
            "name": "active",
            "model": model_map,
            "ttype": "boolean",
            "model_id": model_map_id.id,
            "default": True,
        }
        env["ir.model.fields"].create(value_field)

        # Field name
        value_field = {
            "name": "name",
            "model": model_map,
            "ttype": "char",
            "required": True,
            "model_id": model_map_id.id,
        }
        env["ir.model.fields"].create(value_field)

        # Field description
        value_field = {
            "name": "description",
            "model": model_map,
            "ttype": "char",
            "model_id": model_map_id.id,
        }
        env["ir.model.fields"].create(value_field)

        # Field company_id
        value_field = {
            "name": "company_id",
            "field_description": "Company",
            "comodel_name": "res.company",
            "relation": "res.company",
            "model": model_map,
            "ttype": "many2one",
            "model_id": model_map_id.id,
        }
        env["ir.model.fields"].create(value_field)

        # Field category
        value_field = {
            "name": "category_id",
            "field_description": "Category",
            "comodel_name": model_category,
            "relation": model_category,
            "model": model_map,
            "ttype": "many2one",
            "model_id": model_map_id.id,
            "on_delete": "restrict",
        }
        env["ir.model.fields"].create(value_field)

        # Field features
        value_field = {
            "name": "feature_id",
            "field_description": "Features",
            "comodel_name": model_map_feature,
            "relation": model_map_feature,
            "model": model_map,
            "ttype": "many2many",
            "model_id": model_map_id.id
        }
        env["ir.model.fields"].create(value_field)

        # Hack to solve field name when already has name
        # Ignore WARNING code_generator odoo.addons.base.models.ir_model: Two fields (name, x_name) of
        # demo.website_leaflet.category() have the same label: Name.
        field_x_name = env["ir.model.fields"].search([('model_id', '=', model_map_id.id), ('name', '=', 'x_name')])
        if field_x_name:
            field_x_name.unlink()

        lst_view_list_model = [model_map_feature_id.id, model_category_id.id, model_map_id.id]
        lst_view_form_model = [model_map_feature_id.id, model_category_id.id, model_map_id.id]

        # Generate view
        wizard_view = env['code.generator.generate.views.wizard'].create({
            'code_generator_id': code_generator_id.id,
            'enable_generate_all': False,
            'all_model': False,
            'enable_generate_website_leaflet': True,
            'enable_generate_geoengine': True,
            'selected_model_list_view_ids': [(6, 0, lst_view_list_model)],
            'selected_model_form_view_ids': [(6, 0, lst_view_form_model)],
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
