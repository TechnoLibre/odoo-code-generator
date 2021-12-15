from odoo import api, fields, models, modules, tools


class CodeGeneratorModuleDependency(models.Model):
    _inherit = "ir.module.module.dependency"
    _name = "code.generator.module.dependency"
    _description = "Code Generator Module Dependency"

    depend_id = fields.Many2one(
        comodel_name="ir.module.module",
        string="Dependency",
        compute=None,
    )

    module_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        ondelete="cascade",
    )
