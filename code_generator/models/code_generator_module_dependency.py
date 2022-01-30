from odoo import api, fields, models, modules, tools


class CodeGeneratorModuleDependency(models.Model):
    _name = "code.generator.module.dependency"
    _inherit = "ir.module.module.dependency"
    _description = "Code Generator Module Dependency"

    depend_id = fields.Many2one(compute=None)

    module_id = fields.Many2one(comodel_name="code.generator.module")
