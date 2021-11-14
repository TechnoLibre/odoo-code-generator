# -*- coding: utf-8 -*-

import base64

import logging
import lxml
import os
from docutils.core import publish_string
from odoo import models, fields, api, modules, tools
from odoo.addons.base.models.ir_module import MyWriter

_logger = logging.getLogger(__name__)


class Module(models.Model):
    _inherit = "ir.module.module"

    header_manifest = fields.Text(
        string="Header", help="Header comment in __manifest__.py file."
    )


class CodeGeneratorModule(models.Model):
    _inherit = "ir.module.module"
    _name = "code.generator.module"
    _description = "Code Generator Module"

    name = fields.Char(readonly=False)

    category_id = fields.Many2one(readonly=False)

    shortdesc = fields.Char(readonly=False, required=True)

    summary = fields.Char(readonly=False)

    description = fields.Text(readonly=False)

    author = fields.Char(readonly=False)

    maintainer = fields.Char(readonly=False)

    contributors = fields.Text(readonly=False)

    website = fields.Char(readonly=False)

    latest_version = fields.Char(readonly=False)

    published_version = fields.Char(readonly=False)

    url = fields.Char(readonly=False)

    dependencies_id = fields.One2many(
        "code.generator.module.dependency", "module_id", readonly=False
    )

    dependencies_template_id = fields.One2many(
        "code.generator.module.template.dependency",
        "module_id",
        readonly=False,
    )

    external_dependencies_id = fields.One2many(
        "code.generator.module.external.dependency",
        "module_id",
        readonly=False,
    )

    state = fields.Selection(readonly=False, default="uninstalled")

    demo = fields.Boolean(readonly=False)

    license = fields.Selection(readonly=False, default="AGPL-3")

    application = fields.Boolean(readonly=False)

    icon_image = fields.Binary(readonly=False)

    icon_child_image = fields.Binary(String="Generated icon")

    icon_real_image = fields.Binary(
        String="Replace icon", help="This will replace icon_image"
    )

    o2m_groups = fields.One2many("res.groups", "m2o_module")

    o2m_models = fields.One2many("ir.model", "m2o_module")

    o2m_codes = fields.One2many("code.generator.model.code", "m2o_module")

    o2m_nomenclator_whitelist_fields = fields.One2many(
        "code.generator.ir.model.fields",
        "m2o_module",
        domain=[("nomenclature_whitelist", "=", True)],
    )

    o2m_nomenclator_blacklist_fields = fields.One2many(
        "code.generator.ir.model.fields",
        "m2o_module",
        domain=[("nomenclature_blacklist", "=", True)],
    )

    o2m_model_access = fields.One2many(
        "ir.model.access", compute="_get_models_info"
    )

    o2m_model_rules = fields.One2many("ir.rule", compute="_get_models_info")

    # o2m_model_constraints = fields.One2many("ir.model.constraint", compute="_get_models_info")
    o2m_model_constraints = fields.One2many(
        "ir.model.constraint", inverse_name="code_generator_id"
    )

    o2m_model_views = fields.One2many("ir.ui.view", compute="_get_models_info")

    code_generator_menus_id = fields.One2many(
        "code.generator.menu", inverse_name="code_generator_id"
    )

    code_generator_act_window_id = fields.One2many(
        "code.generator.act_window", inverse_name="code_generator_id"
    )

    code_generator_views_id = fields.One2many(
        "code.generator.view", inverse_name="code_generator_id"
    )

    o2m_model_act_url = fields.One2many(
        comodel_name="ir.actions.act_url", inverse_name="m2o_code_generator"
    )

    o2m_model_act_todo = fields.One2many(
        comodel_name="ir.actions.todo", inverse_name="m2o_code_generator"
    )

    o2m_model_act_window = fields.One2many(
        "ir.actions.act_window", compute="_get_models_info"
    )

    o2m_model_act_server = fields.One2many(
        "ir.actions.server", compute="_get_models_info"
    )

    o2m_model_server_constrains = fields.One2many(
        "ir.model.server_constrain", compute="_get_models_info"
    )

    o2m_model_reports = fields.One2many(
        "ir.actions.report", compute="_get_models_info"
    )

    o2m_menus = fields.One2many(
        "ir.ui.menu", "m2o_module", context={"ir.ui.menu.full_list": True}
    )

    nomenclator_only = fields.Boolean(
        string="Only export data",
        default=False,
        help="Useful to export data with existing model.",
    )

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

    template_model_name = fields.Char(
        string="Functions models",
        help="Add model from list, separate by ';' and generate template.",
    )

    template_module_name = fields.Char(
        string="Generated module name",
        help=(
            "Can be empty in case of code_generator_demo, else it's the module"
            " name goal to generate."
        ),
    )

    template_module_id = fields.Many2one(
        comodel_name="ir.module.module",
        string="Template module id",
        help="Child module to generate.",
        compute="_fill_template_module_id",
    )

    @api.depends("template_module_name")
    @api.multi
    def _fill_template_module_id(self):
        for module_id in self:
            if module_id.template_module_name:
                module_id.template_module_id = self.env[
                    "ir.module.module"
                ].search([("name", "=", module_id.template_module_name)])

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

    # clean_before_sync_code = fields.Boolean(string="Clean before sync", help="Clean before sync, all will be lost.")

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


class CodeGeneratorModuleExternalDependency(models.Model):
    _name = "code.generator.module.external.dependency"
    _description = "Code Generator Module External Dependency"

    module_id = fields.Many2one(
        "code.generator.module", "Module", ondelete="cascade"
    )

    depend = fields.Char(string="Dependency name")

    application_type = fields.Selection(
        selection=[("python", "python"), ("bin", "bin")],
        string="Application Type",
        default="python",
    )

    # TODO this is wrong, an hack because ir_module_module != code_generator_module
    is_template = fields.Boolean(
        string="Is template", help="Will be affect template module."
    )


class CodeGeneratorModuleDependency(models.Model):
    _inherit = "ir.module.module.dependency"
    _name = "code.generator.module.dependency"
    _description = "Code Generator Module Dependency"

    module_id = fields.Many2one(
        "code.generator.module", "Module", ondelete="cascade"
    )

    depend_id = fields.Many2one("ir.module.module", "Dependency", compute=None)


class CodeGeneratorModuleTemplateDependency(models.Model):
    _inherit = "ir.module.module.dependency"
    _name = "code.generator.module.template.dependency"
    _description = (
        "Code Generator Module Template Dependency, set by"
        " code_generator_template"
    )

    module_id = fields.Many2one(
        "code.generator.module", "Module", ondelete="cascade"
    )

    depend_id = fields.Many2one("ir.module.module", "Dependency", compute=None)


class CodeGeneratorActWindow(models.Model):
    _name = "code.generator.act_window"
    _description = "Code Generator Act Window"

    name = fields.Char(string="name")

    # TODO use ir.model.data instead if id_name
    id_name = fields.Char(
        string="Action id", help="Specify id name of this action window."
    )

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )


class CodeGeneratorMenu(models.Model):
    _name = "code.generator.menu"
    _description = "Code Generator Menu"

    # TODO missing groups_id and active and web_icon or web_icon_data
    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    # TODO use ir.model.data instead if id_name
    id_name = fields.Char(
        string="Menu id", help="Specify id name of this menu."
    )

    # TODO use ir.model.data instead if parent_id_name
    parent_id_name = fields.Char(
        string="Menu parent id",
        help="Specify id name of parent menu, optional.",
    )

    sequence = fields.Integer(string="Sequence", default=10)

    m2o_act_window = fields.Many2one(
        comodel_name="code.generator.act_window",
        string="Action Windows",
        help="Act window to open when click on this menu.",
    )


class CodeGeneratorView(models.Model):
    _name = "code.generator.view"
    _description = "Code Generator View"

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    # TODO use ir.model.data instead if id_name
    id_name = fields.Char(
        string="View id", help="Specify id name of this view."
    )

    view_type = fields.Selection(
        [
            ("tree", "Tree"),
            ("form", "Form"),
            ("pivot", "Pivot"),
            ("graph", "Graph"),
            ("search", "Search"),  # Special
            ("kanban", "Kanban"),
            ("timeline", "Timeline"),
            ("activity", "Activity"),
            ("calendar", "Calendar"),
            ("diagram", "Diagram"),
        ],
        default="form",
        help="Choose view type to generate.",
    )

    view_name = fields.Char(string="View name")

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Code generator Model",
        help="Model related with this report",
    )

    view_item_ids = fields.Many2many(
        comodel_name="code.generator.view.item",
        string="View item",
        help="Item view to add in this view.",
    )

    has_body_sheet = fields.Boolean(
        string="Sheet format",
        help="Use sheet presentation for body of form view.",
    )


class CodeGeneratorViewItem(models.Model):
    _name = "code.generator.view.item"
    _description = "Code Generator View Item"

    action_name = fields.Char(string="Action name")

    sequence = fields.Integer(string="Sequence", default=1)

    # TODO create HTML for specific label
    label = fields.Char(string="Label")

    item_type = fields.Selection(
        [
            ("field", "Field"),
            ("button", "Button"),
            ("html", "HTML"),
            ("filter", "Filter"),
            ("div", "Division"),
            ("group", "Group"),
            ("templates", "Templates"),
            ("t", "T"),
            ("ul", "UL"),
            ("li", "LI"),
            ("i", "I"),
            ("strong", "Strong"),
        ],
        default="field",
        help="Choose item type to generate.",
    )

    button_type = fields.Selection(
        [
            ("", ""),  # Default
            ("btn-default", "Default"),  # Default
            ("btn-primary", "Primary"),
            ("btn-secondary", "Secondary"),  # Default
            ("btn-link", "Link"),  # URL
            ("btn-success", "Success"),  # Green
            ("btn-warning", "Warning"),  # Yellow
            ("btn-danger", "Danger"),  # Red
            ("oe_highlight", "Highlight"),  # Primary
            ("oe_stat_button", "Statistic"),  # Default
        ],
        default="",
        help="Choose item type to generate.",
    )

    background_type = fields.Selection(
        [
            ("", ""),  # Default
            ("bg-success", "Success"),  # Default
            # ("bg-success-light", "Success light"),
            ("bg-success-full", "Success full"),
            ("bg-warning", "Warning"),
            # ("bg-warning-light", "Warning light"),
            ("bg-warning-full", "Warning full"),
            ("bg-info", "Info"),
            # ("bg-info-light", "Info light"),
            ("bg-info-full", "Info full"),
            ("bg-danger", "Danger"),
            # ("bg-danger-light", "Danger light"),
            ("bg-danger-full", "Danger full"),
            ("bg-light", "Light"),
            ("bg-dark", "Dark"),
        ],
        default="",
        help="Choose background color of HTML.",
    )

    section_type = fields.Selection(
        [
            ("header", "Header"),
            ("title", "Title"),
            ("body", "Body"),
            ("footer", "Footer"),
        ],
        default="body",
        help="Choose item type to generate.",
    )

    colspan = fields.Integer(
        string="Colspan",
        default=1,
        help="Use this to fill more column, check HTML table.",
    )

    placeholder = fields.Char(string="Placeholder")

    password = fields.Boolean(string="Password", help="Hide character.")

    icon = fields.Char(
        string="Icon",
        help="Example fa-television. Only supported with button.",
    )

    attrs = fields.Char(
        string="Attributes",
        help="Specific condition, search attrs for more information.",
    )

    is_required = fields.Boolean(string="Required")

    is_invisible = fields.Boolean(string="Invisible")

    is_readonly = fields.Boolean(string="Readonly")

    is_help = fields.Boolean(string="Help")

    has_label = fields.Boolean(string="Labeled", help="Label for title.")

    parent_id = fields.Many2one(comodel_name="code.generator.view.item")

    child_id = fields.One2many(
        comodel_name="code.generator.view.item",
        inverse_name="parent_id",
    )

    edit_only = fields.Boolean(string="Edit only")


class CodeGeneratorPyClass(models.Model):
    _name = "code.generator.pyclass"
    _description = "Code Generator Python Class"

    name = fields.Char(string="Class name", help="Class name", required=True)

    module = fields.Char(string="Class path", help="Class path")


class CodeGeneratorCodeImport(models.Model):
    _name = "code.generator.model.code.import"
    _description = "Header code to display in model"

    name = fields.Char(string="Import name", help="import name")

    sequence = fields.Integer(
        string="Sequence", help="Order of sequence code."
    )

    code = fields.Text(
        string="code", help="Code of import header of python file"
    )

    m2o_module = fields.Many2one(
        "code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    m2o_model = fields.Many2one(
        "ir.model", string="Model", help="Model", ondelete="cascade"
    )

    is_templated = fields.Boolean(
        string="Templated", help="Code for code generator from template."
    )


class CodeGeneratorCode(models.Model):
    _name = "code.generator.model.code"
    _description = "Code to display in model"

    name = fields.Char(string="Method name", help="Method name", required=True)

    sequence = fields.Integer(
        string="Sequence", help="Order of sequence code."
    )

    code = fields.Text(
        string="Code of pre_init_hook",
        default="""
return""",
    )

    decorator = fields.Char(
        string="Decorator",
        help="Like @api.model. Use ; for multiple decorator.",
    )

    param = fields.Char(string="Param", help="Like : name,color")

    returns = fields.Char(
        string="Return type", help="Annotation to return type value."
    )

    m2o_module = fields.Many2one(
        "code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    m2o_model = fields.Many2one(
        "ir.model", string="Model", help="Model", ondelete="cascade"
    )

    is_wip = fields.Boolean(
        string="Work in progress", help="Temporary function to be fill later."
    )

    is_templated = fields.Boolean(
        string="Templated", help="Code for code generator from template."
    )
