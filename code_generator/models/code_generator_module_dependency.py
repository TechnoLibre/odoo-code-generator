from odoo import models, fields, api, modules, tools


class CodeGeneratorModuleDependency(models.Model):
    _inherit = "ir.module.module.dependency"
    _name = "code.generator.module.dependency"
    _description = "Code Generator Module Dependency"

    module_id = fields.Many2one(
        "code.generator.module", "Module", ondelete="cascade"
    )

    depend_id = fields.Many2one("ir.module.module", "Dependency", compute=None)
