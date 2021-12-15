import base64
import logging
import os

import lxml
from docutils.core import publish_string

from odoo import api, fields, models, modules, tools
from odoo.addons.base.models.ir_module import MyWriter

_logger = logging.getLogger(__name__)


class CodeGeneratorModule(models.Model):
    _inherit = "ir.module.module"
    _name = "code.generator.module"
    _description = "Code Generator Module"

    name = fields.Char(readonly=False)

    application = fields.Boolean(readonly=False)

    author = fields.Char(readonly=False)

    category_id = fields.Many2one(
        string="Category",
        readonly=False,
    )

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
        inverse_name="module_id",
        string="Dependencies module",
        readonly=False,
    )

    dependencies_template_id = fields.One2many(
        comodel_name="code.generator.module.template.dependency",
        inverse_name="module_id",
        string="Dependencies template module",
        readonly=False,
    )

    description = fields.Text(readonly=False)

    # Dev binding code
    enable_sync_code = fields.Boolean(
        string="Enable Sync Code",
        default=False,
        help="Will sync with code on drive when generate.",
    )

    enable_pylint_check = fields.Boolean(
        string="Enable Pylint check",
        default=False,
        help="Show pylint result at the end of generation.",
    )

    external_dependencies_id = fields.One2many(
        comodel_name="code.generator.module.external.dependency",
        inverse_name="module_id",
        string="External Dependencies",
        readonly=False,
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

    maintainer = fields.Char(readonly=False)

    nomenclator_only = fields.Boolean(
        string="Only export data",
        default=False,
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

    shortdesc = fields.Char(readonly=False, required=True)

    state = fields.Selection(readonly=False, default="uninstalled")

    summary = fields.Char(readonly=False)

    template_model_name = fields.Char(
        string="Functions models",
        help="Add model from list, separate by ';' and generate template.",
    )

    template_module_id = fields.Many2one(
        comodel_name="ir.module.module",
        string="Template module id",
        help="Child module to generate.",
        compute="_fill_template_module_id",
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
