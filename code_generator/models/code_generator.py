# -*- coding: utf-8 -*-

import base64

import lxml
from docutils.core import publish_string
from odoo import models, fields, api, modules, tools
from odoo.addons.base.models.ir_module import MyWriter


class CodeGeneratorModule(models.Model):
    _inherit = 'ir.module.module'
    _name = 'code.generator.module'
    _description = 'Code Generator Module'

    name = fields.Char(
        readonly=False
    )

    category_id = fields.Many2one(
        readonly=False
    )

    shortdesc = fields.Char(
        readonly=False,
        required=True
    )

    summary = fields.Char(
        readonly=False
    )

    description = fields.Text(
        readonly=False
    )

    author = fields.Char(
        readonly=False
    )

    maintainer = fields.Char(
        readonly=False
    )

    contributors = fields.Text(
        readonly=False
    )

    website = fields.Char(
        readonly=False
    )

    latest_version = fields.Char(
        readonly=False
    )

    published_version = fields.Char(
        readonly=False
    )

    url = fields.Char(
        readonly=False
    )

    dependencies_id = fields.One2many(
        'code.generator.module.dependency',
        'module_id',
        readonly=False
    )

    state = fields.Selection(
        readonly=False,
        default='uninstalled'
    )

    demo = fields.Boolean(
        readonly=False
    )

    license = fields.Selection(
        readonly=False
    )

    application = fields.Boolean(
        readonly=False
    )

    icon_image = fields.Binary(
        readonly=False
    )

    o2m_groups = fields.One2many(
        'res.groups',
        'm2o_module'
    )

    o2m_models = fields.One2many(
        'ir.model',
        'm2o_module'
    )

    o2m_nomenclator_whitelist_fields = fields.One2many(
        'code.generator.ir.model.fields',
        'm2o_module',
        domain=[("nomenclature_whitelist", "=", True)]
    )

    o2m_nomenclator_blacklist_fields = fields.One2many(
        'code.generator.ir.model.fields',
        'm2o_module',
        domain=[("nomenclature_blacklist", "=", True)]
    )

    o2m_model_access = fields.One2many(
        'ir.model.access',
        compute='_get_models_info'
    )

    o2m_model_rules = fields.One2many(
        'ir.rule',
        compute='_get_models_info'
    )

    o2m_model_constraints = fields.One2many(
        'ir.model.constraint',
        compute='_get_models_info'
    )

    o2m_model_views = fields.One2many(
        'ir.ui.view',
        compute='_get_models_info'
    )

    o2m_model_act_url = fields.One2many(
        comodel_name='ir.actions.act_url',
        inverse_name='m2o_code_generator'
    )

    o2m_model_act_todo = fields.One2many(
        comodel_name='ir.actions.todo',
        inverse_name='m2o_code_generator'
    )

    o2m_model_act_window = fields.One2many(
        'ir.actions.act_window',
        compute='_get_models_info'
    )

    o2m_model_act_server = fields.One2many(
        'ir.actions.server',
        compute='_get_models_info'
    )

    o2m_model_server_constrains = fields.One2many(
        'ir.model.server_constrain',
        compute='_get_models_info'
    )

    o2m_model_reports = fields.One2many(
        'ir.actions.report',
        compute='_get_models_info'
    )

    o2m_menus = fields.One2many(
        'ir.ui.menu',
        'm2o_module',
        context={'ir.ui.menu.full_list': True}
    )

    nomenclator_only = fields.Boolean(string="Only export data", default=False,
                                      help="Useful to export data with existing model.")

    # Dev binding code
    enable_sync_code = fields.Boolean(string="Enable Sync Code", default=False,
                                      help="Will sync with code on drive when generate.")

    # TODO default path actual path of this file
    path_sync_code = fields.Char(string="Path", help="Path where sync the code.")

    # clean_before_sync_code = fields.Boolean(string="Clean before sync", help="Clean before sync, all will be lost.")

    @api.depends('o2m_models')
    def _get_models_info(self):
        for module in self:
            module.o2m_model_access = module.o2m_models.mapped('access_ids')
            module.o2m_model_rules = module.o2m_models.mapped('rule_ids')
            module.o2m_model_constraints = module.o2m_models.mapped('o2m_constraints')
            module.o2m_model_views = module.o2m_models.mapped('view_ids')
            module.o2m_model_act_window = module.o2m_models.mapped('o2m_act_window')
            module.o2m_model_act_server = module.o2m_models.mapped('o2m_server_action')
            module.o2m_model_server_constrains = module.o2m_models.mapped('o2m_server_constrains')
            module.o2m_model_reports = module.o2m_models.mapped('o2m_reports')

    @api.depends('name', 'description')
    def _get_desc(self):
        for module in self:
            if module.name and module.description:
                path = modules.get_module_resource(module.name, 'static/description/index.html')
                if path:
                    with tools.file_open(path, 'rb') as desc_file:
                        doc = desc_file.read()
                        html = lxml.html.document_fromstring(doc)
                        for element, attribute, link, pos in html.iterlinks():
                            if element.get('src') and '//' not in element.get('src') and \
                                    'static/' not in element.get('src'):
                                element.set('src', "/%s/static/description/%s" % (module.name, element.get('src')))
                        module.description_html = tools.html_sanitize(lxml.html.tostring(html))
                else:
                    overrides = {
                        'embed_stylesheet': False,
                        'doctitle_xform': False,
                        'output_encoding': 'unicode',
                        'xml_declaration': False,
                        'file_insertion_enabled': False,
                    }
                    output = publish_string(
                        source=module.description if not module.application and module.description else '',
                        settings_overrides=overrides, writer=MyWriter()
                    )
                    module.description_html = tools.html_sanitize(output)

    @api.depends('icon')
    def _get_icon_image(self):
        for module in self:
            module.icon_image = ''
            if module.icon:
                path_parts = module.icon.split('/')
                path = modules.get_module_resource(path_parts[1], *path_parts[2:])
            else:
                path = modules.module.get_module_icon(module.name)
                path = path[1:]
            if path:
                with tools.file_open(path, 'rb') as image_file:
                    module.icon_image = base64.b64encode(image_file.read())

    @api.model
    def create(self, vals):
        return super(models.Model, self).create(vals)

    @api.multi
    def unlink(self):
        o2m_models = self.mapped('o2m_models')
        if o2m_models:
            o2m_models.mapped('view_ids').unlink()
            o2m_models.unlink()  # I need to delete the created tables
        return super(CodeGeneratorModule, self).unlink()


class CodeGeneratorModuleDependency(models.Model):
    _inherit = 'ir.module.module.dependency'
    _name = 'code.generator.module.dependency'
    _description = 'Code Generator Module Dependency'

    module_id = fields.Many2one(
        'code.generator.module',
        'Module',
        ondelete='cascade'
    )

    depend_id = fields.Many2one(
        'ir.module.module',
        'Dependency',
        compute=None
    )


class CodeGeneratorPyClass(models.Model):
    _name = 'code.generator.pyclass'
    _description = 'Code Generator Python Class'

    name = fields.Char(
        string='Class name',
        help='Class name',
        required=True
    )

    module = fields.Char(
        string='Class path',
        help='Class path'
    )
