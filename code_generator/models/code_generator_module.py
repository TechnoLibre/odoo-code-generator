import base64
import logging
import os

import lxml
from docutils.core import publish_string

from odoo import api, fields, models, modules, tools
from odoo.addons.base.models.ir_module import MyWriter

_logger = logging.getLogger(__name__)


class CodeGeneratorModule(models.Model):
    _name = "code.generator.module"
    _inherit = "ir.module.module"
    _description = "Code Generator Module"

    name = fields.Char(readonly=False)

    application = fields.Boolean(readonly=False)

    author = fields.Char(readonly=False)

    category_id = fields.Many2one(readonly=False)

    code_generator_act_window_id = fields.One2many(
        comodel_name="code.generator.act_window",
        inverse_name="code_generator_id",
        string="Code Generator Act Window",
    )

    code_generator_menus_id = fields.One2many(
        comodel_name="code.generator.menu",
        inverse_name="code_generator_id",
        string="Code Generator Menus",
    )

    code_generator_views_id = fields.One2many(
        comodel_name="code.generator.view",
        inverse_name="code_generator_id",
        string="Code Generator Views",
    )

    contributors = fields.Text(readonly=False)

    demo = fields.Boolean(readonly=False)

    dependencies_id = fields.One2many(
        comodel_name="code.generator.module.dependency",
        readonly=False,
        string="Dependencies module",
    )

    dependencies_template_id = fields.One2many(
        comodel_name="code.generator.module.template.dependency",
        inverse_name="module_id",
        string="Dependencies template module",
    )

    description = fields.Text(readonly=False)

    enable_pylint_check = fields.Boolean(
        string="Enable Pylint check",
        help="Show pylint result at the end of generation.",
    )

    # Dev binding code
    enable_sync_code = fields.Boolean(
        help="Will sync with code on drive when generate."
    )

    exclude_dependencies_str = fields.Char(
        help=(
            "Exclude from list dependencies_id about"
            " code.generator.module.dependency name separate by ;"
        )
    )

    export_website_optimize_binary_image = fields.Boolean(
        help=(
            "Associate with nomenclator export data. Search url /web/image/ in"
            " website page and remove ir.attachment who is not into view."
            " Remove duplicate same attachment, image or scss."
        )
    )

    external_dependencies_id = fields.One2many(
        comodel_name="code.generator.module.external.dependency",
        inverse_name="module_id",
        string="External Dependencies",
    )

    icon_child_image = fields.Binary(string="Generated icon")

    icon_image = fields.Binary(readonly=False)

    icon_real_image = fields.Binary(
        string="Replace icon",
        help="This will replace icon_image",
    )

    latest_version = fields.Char(readonly=False)

    license = fields.Selection(
        readonly=False,
        default="AGPL-3",
    )

    list_scss_process_hook = fields.Char(
        help=(
            "READONLY, use by computation. Value are separated by ;. List of"
            " xml_id to compute scss in hook when export website data with"
            " scss modification."
        )
    )

    maintainer = fields.Char(readonly=False)

    nomenclator_only = fields.Boolean(
        string="Only export data",
        help="Useful to export data with existing model.",
    )

    o2m_codes = fields.One2many(
        comodel_name="code.generator.model.code",
        inverse_name="m2o_module",
    )

    o2m_groups = fields.One2many(
        comodel_name="res.groups",
        inverse_name="m2o_module",
    )

    o2m_menus = fields.One2many(
        comodel_name="ir.ui.menu",
        inverse_name="m2o_module",
        context={"ir.ui.menu.full_list": True},
    )

    o2m_model_access = fields.One2many(
        comodel_name="ir.model.access",
        compute="_get_models_info",
    )

    o2m_model_act_server = fields.One2many(
        comodel_name="ir.actions.server",
        compute="_get_models_info",
    )

    o2m_model_act_todo = fields.One2many(
        comodel_name="ir.actions.todo",
        inverse_name="m2o_code_generator",
    )

    o2m_model_act_url = fields.One2many(
        comodel_name="ir.actions.act_url",
        inverse_name="m2o_code_generator",
    )

    o2m_model_act_window = fields.One2many(
        comodel_name="ir.actions.act_window",
        compute="_get_models_info",
    )

    # o2m_model_constraints = fields.One2many("ir.model.constraint", compute="_get_models_info")
    o2m_model_constraints = fields.One2many(
        comodel_name="ir.model.constraint",
        inverse_name="code_generator_id",
    )

    o2m_model_reports = fields.One2many(
        comodel_name="ir.actions.report",
        compute="_get_models_info",
    )

    o2m_model_rules = fields.One2many(
        comodel_name="ir.rule",
        compute="_get_models_info",
    )

    o2m_model_server_constrains = fields.One2many(
        comodel_name="ir.model.server_constrain",
        compute="_get_models_info",
    )

    o2m_model_views = fields.One2many(
        comodel_name="ir.ui.view",
        compute="_get_models_info",
    )

    o2m_models = fields.One2many(
        comodel_name="ir.model",
        inverse_name="m2o_module",
    )

    o2m_nomenclator_blacklist_fields = fields.One2many(
        comodel_name="code.generator.ir.model.fields",
        inverse_name="m2o_module",
        domain=[("nomenclature_blacklist", "=", True)],
    )

    o2m_nomenclator_whitelist_fields = fields.One2many(
        comodel_name="code.generator.ir.model.fields",
        inverse_name="m2o_module",
        domain=[("nomenclature_whitelist", "=", True)],
    )

    published_version = fields.Char(readonly=False)

    shortdesc = fields.Char(
        readonly=False,
        required=True,
    )

    state = fields.Selection(
        readonly=False,
        default="uninstalled",
    )

    summary = fields.Char(readonly=False)

    template_inherit_model_name = fields.Char(
        string="Functions models inherit",
        help="Add model from list, separate by ';' and generate template.",
    )

    template_model_name = fields.Char(
        string="Functions models",
        help="Add model from list, separate by ';' and generate template.",
    )

    template_module_id = fields.Many2one(
        comodel_name="ir.module.module",
        string="Template module id",
        compute="_fill_template_module_id",
        help="Child module to generate.",
    )

    template_module_name = fields.Char(
        string="Generated module name",
        help=(
            "Can be empty in case of code_generator_demo, else it's the module"
            " name goal to generate."
        ),
    )

    url = fields.Char(readonly=False)

    website = fields.Char(readonly=False)

    @api.model
    def _default_path_sync_code(self):
        # sibling directory odoo-code-generator-template
        sibling = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "TechnoLibre_odoo-code-generator-template",
            )
        )
        if os.path.isdir(sibling):
            return sibling
        # Cannot find sibling template, use this working repo directory instead
        return os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

    path_sync_code = fields.Char(
        string="Directory",
        default=_default_path_sync_code,
        help=(
            "Path directory where sync the code, will erase directory and"
            " generate new code."
        ),
    )

    @api.depends("template_module_name")
    @api.multi
    def _fill_template_module_id(self):
        for module_id in self:
            if module_id.template_module_name:
                module_id.template_module_id = self.env[
                    "ir.module.module"
                ].search([("name", "=", module_id.template_module_name)])

    @api.multi
    def add_module_dependency_template(self, module_name):
        self.add_module_dependency(
            module_name,
            model_dependency="code.generator.module.template.dependency",
        )

    @api.multi
    def add_module_dependency(
        self, module_name, model_dependency="code.generator.module.dependency"
    ):
        """

        :param module_name: list or string
        :param model_dependency: string model name to operate
        :return:
        """
        for cg in self:
            if type(module_name) is str:
                lst_model_name = [module_name]
            elif type(module_name) is list:
                lst_model_name = module_name
            else:
                _logger.error(
                    "Wrong type of model_name in method add_model_inherit:"
                    f" {type(module_name)}"
                )
                return

            dependency_ids = self.env["ir.module.module"].search(
                [("name", "in", lst_model_name)]
            )
            for dependency in dependency_ids:
                check_duplicate = self.env[model_dependency].search(
                    [
                        ("module_id", "=", cg.id),
                        ("depend_id", "=", dependency.id),
                    ]
                )
                if not check_duplicate:
                    value = {
                        "module_id": cg.id,
                        "depend_id": dependency.id,
                        "name": dependency.display_name,
                    }
                    self.env[model_dependency].create(value)

    @api.depends("o2m_models")
    def _get_models_info(self):
        # TODO not use anymore (soon), mapping has some problem with update
        for module in self:
            module.o2m_model_access = module.o2m_models.mapped("access_ids")
            module.o2m_model_rules = module.o2m_models.mapped("rule_ids")
            module.o2m_model_constraints = module.o2m_models.mapped(
                "o2m_constraints"
            )
            module.o2m_model_views = module.o2m_models.mapped("view_ids")
            module.o2m_model_act_window = module.o2m_models.mapped(
                "o2m_act_window"
            )
            module.o2m_model_act_server = module.o2m_models.mapped(
                "o2m_server_action"
            )
            module.o2m_model_server_constrains = module.o2m_models.mapped(
                "o2m_server_constrains"
            )
            module.o2m_model_reports = module.o2m_models.mapped("o2m_reports")

    @api.depends("name", "description")
    def _get_desc(self):
        for module in self:
            if module.name and module.description:
                path = modules.get_module_resource(
                    module.name, "static/description/index.html"
                )
                if path:
                    with tools.file_open(path, "rb") as desc_file:
                        doc = desc_file.read()
                        html = lxml.html.document_fromstring(doc)
                        for element, attribute, link, pos in html.iterlinks():
                            if (
                                element.get("src")
                                and "//" not in element.get("src")
                                and "static/" not in element.get("src")
                            ):
                                element.set(
                                    "src",
                                    "/%s/static/description/%s"
                                    % (module.name, element.get("src")),
                                )
                        module.description_html = tools.html_sanitize(
                            lxml.html.tostring(html)
                        )
                else:
                    overrides = {
                        "embed_stylesheet": False,
                        "doctitle_xform": False,
                        "output_encoding": "unicode",
                        "xml_declaration": False,
                        "file_insertion_enabled": False,
                    }
                    output = publish_string(
                        source=module.description
                        if not module.application and module.description
                        else "",
                        settings_overrides=overrides,
                        writer=MyWriter(),
                    )
                    module.description_html = tools.html_sanitize(output)

    @api.depends("icon")
    def _get_icon_image(self):
        for module in self:
            # module.icon_image = ""
            if module.icon:
                path_parts = module.icon.split("/")
                # TODO this is broken ??
                # path = modules.get_module_resource(
                #     path_parts[0], *path_parts[1:]
                # )
                path = modules.get_module_resource(
                    path_parts[1], *path_parts[2:]
                )
            else:
                path = modules.module.get_module_icon(module.name)
                path = path[1:]
            if path:
                with tools.file_open(path, "rb") as image_file:
                    module.icon_image = base64.b64encode(image_file.read())

    @api.model
    def add_update_model(
        self,
        model_model,
        model_name=None,
        dct_field=None,
        dct_model=None,
        lst_depend_model=None,
    ):
        # When this is called, all field is in whitelist
        if dct_field:
            for field_name, field_info in dct_field.items():
                if (
                    field_info.get("is_show_whitelist_model_inherit") is None
                    and field_info.get("is_hide_blacklist_model_inherit")
                    is None
                ):
                    field_info["is_show_whitelist_model_inherit"] = True
        model_id = self.env["ir.model"].search([("model", "=", model_model)])
        if model_name is None:
            model_name = model_model.replace(".", "_")
        # Check if exist or create it
        if model_id:
            model_id.m2o_module = self.id

            if dct_field:
                for field_name, field_info in dct_field.items():
                    if field_info.get("ttype") == "many2many":
                        self._check_relation_many2many(model_model, field_info)
                    field_id = self.env["ir.model.fields"].search(
                        [
                            ("model", "=", model_model),
                            ("name", "=", field_name),
                        ]
                    )
                    if not field_id:
                        value_ir_model_fields = {
                            "name": field_name,
                            "model": model_model,
                            "model_id": model_id.id,
                        }
                        for key in field_info.keys():
                            self._update_dict(
                                key,
                                field_info,
                                value_ir_model_fields,
                            )
                        self.env["ir.model.fields"].create(
                            value_ir_model_fields
                        )
                    else:
                        # Support model of code generator or model already existing (like inherit)
                        value_ir_model_fields = {
                            "m2o_fields": field_id.id,
                        }
                        # TODO update all field with getter
                        self._update_dict(
                            "filter_field_attribute",
                            field_info,
                            value_ir_model_fields,
                        )
                        self._update_dict(
                            "code_generator_compute",
                            field_info,
                            value_ir_model_fields,
                        )
                        self._update_dict(
                            "comment_before",
                            field_info,
                            value_ir_model_fields,
                        )
                        self._update_dict(
                            "comment_after",
                            field_info,
                            value_ir_model_fields,
                        )
                        self._update_dict(
                            "default_lambda",
                            field_info,
                            value_ir_model_fields,
                        )

                        self.env["code.generator.ir.model.fields"].create(
                            value_ir_model_fields
                        )

            if dct_model:
                model_id.write(dct_model)
        else:
            has_field_name = False
            # Update model values
            value = {
                "name": model_name,
                "model": model_model,
                "m2o_module": self.id,
            }
            if dct_model:
                for key in dct_model.keys():
                    self._update_dict(
                        key,
                        dct_model,
                        value,
                    )
            else:
                dct_model = {}
            rec_name = dct_model.get("rec_name")
            has_already_rec_name = False
            if not rec_name:
                rec_name = "name"
            else:
                has_already_rec_name = True

            # Update fields values
            lst_field_value = []
            if dct_field:
                for field_name, field_info in dct_field.items():
                    if field_info.get("ttype") == "many2many":
                        self._check_relation_many2many(model_model, field_info)

                    if field_name == rec_name:
                        has_field_name = True

                    field_id = self.env["ir.model.fields"].search(
                        [
                            ("model", "=", model_model),
                            ("name", "=", field_name),
                        ]
                    )
                    if not field_id:
                        value_field_id = {
                            "name": field_name,
                        }
                        for key in field_info.keys():
                            self._update_dict(
                                key,
                                field_info,
                                value_field_id,
                            )

                        lst_field_value.append((0, 0, value_field_id))
                    else:
                        _logger.error("What to do with existing field?")

            if lst_field_value:
                value["field_id"] = lst_field_value

            if not has_already_rec_name:
                if has_field_name:
                    value["rec_name"] = "name"
                elif not dct_field:
                    # TODO this will create x_name field
                    # value["rec_name"] = None
                    value["rec_name"] = "name"
                    # value["field_id"] = {"name": {"name": "name", "ttype": "char"}}
                    value["field_id"] = [
                        (
                            0,
                            0,
                            {
                                "name": "name",
                                "field_description": "Name",
                                "ttype": "char",
                            },
                        )
                    ]
                else:
                    _logger.error(
                        f"Cannot found rec_name for model {model_model}."
                    )

            model_id = self.env["ir.model"].create(value)

        # Model inherit
        if lst_depend_model:
            model_id.add_model_inherit(lst_depend_model)

        return model_id

    def _check_relation_many2many(self, model_model, field_value):
        relation_name = field_value.get("relation")
        comodel_name = relation_name.replace(".", "_")
        str_model_model = model_model.replace(".", "_")
        if not comodel_name:
            _logger.warning(f"Missing relation for field_value {field_value}")
        else:
            # Source, file odoo/odoo/addons/base/models/ir_model.py function _custom_many2many_names
            # relation = self.env["ir.model.fields"]._custom_many2many_names(model_name, comodel_name)
            # Execution error will come from file odoo/odoo/fields.py, function check_pg_name
            relation = f"x_{comodel_name}_{str_model_model}_rel"
            if len(relation) > 63:
                _logger.warning(
                    "The size is too high, please reduce size of model name"
                    f" of '{model_model}' ({len(model_model)}) or"
                    f" '{field_value.get('relation')}' ({len(relation_name)}),"
                    " automatic relation will be broke, max 63 chars. Result"
                    f" ({len(relation)}) '{relation}'"
                )

    @api.model
    def add_update_model_one2many(self, model_model, dct_field):
        # When this is called, all field is in whitelist
        for field_name, field_info in dct_field.items():
            if (
                field_info.get("is_show_whitelist_model_inherit") is None
                and field_info.get("is_hide_blacklist_model_inherit") is None
            ):
                field_info["is_show_whitelist_model_inherit"] = True
        model_id = self.env["ir.model"].search([("model", "=", model_model)])
        # Check if exist or create it
        if model_id:
            model_id.m2o_module = self.id
            for field_name, field_info in dct_field.items():
                field_id = self.env["ir.model.fields"].search(
                    [
                        ("model", "=", model_model),
                        ("name", "=", field_name),
                    ]
                )
                if not field_id:
                    value_field_one2many = {
                        "name": field_name,
                        "model": model_model,
                        "model_id": model_id.id,
                    }

                    for key in field_info.keys():
                        self._update_dict(
                            key,
                            field_info,
                            value_field_one2many,
                        )

                    self.env["ir.model.fields"].create(value_field_one2many)
                else:
                    # Support model of code generator or model already existing (like inherit)
                    if (
                        "field_context" in field_info.keys()
                        or "comment_before" in field_info.keys()
                        or "comment_after" in field_info.keys()
                    ):
                        value_ir_model_fields = {
                            "m2o_fields": field_id.id,
                        }
                        if "field_context" in field_info.keys():
                            # TODO find missing attribute
                            self._update_dict(
                                "field_context",
                                field_info,
                                value_ir_model_fields,
                            )
                        if "comment_before" in field_info.keys():
                            self._update_dict(
                                "comment_before",
                                field_info,
                                value_ir_model_fields,
                            )
                        if "comment_after" in field_info.keys():
                            self._update_dict(
                                "comment_after",
                                field_info,
                                value_ir_model_fields,
                            )
                        self.env["code.generator.ir.model.fields"].create(
                            value_ir_model_fields
                        )
                    # _logger.error("What to do to update a one2many?")
        else:
            _logger.error(
                f"The model '{model_model}' is not existing, need to be create"
                " before call add_update_model_one2many from"
                " CodeGeneratorModule."
            )

    @api.model
    def _update_dict(self, key_name, field_info, value_field_id):
        filter_field_attribute = field_info.get(key_name)
        if filter_field_attribute:
            value_field_id[key_name] = filter_field_attribute

    @api.model
    def create(self, vals):
        if "icon" in vals.keys():
            icon_path = vals["icon"]

            if icon_path and os.path.isfile(icon_path):
                with tools.file_open(icon_path, "rb") as image_file:
                    vals["icon_image"] = base64.b64encode(image_file.read())
        return super(models.Model, self).create(vals)

    @api.multi
    def unlink(self):
        o2m_models = self.mapped("o2m_models")
        if o2m_models:
            o2m_models.mapped("view_ids").unlink()
            o2m_models.unlink()  # I need to delete the created tables
        return super(CodeGeneratorModule, self).unlink()
