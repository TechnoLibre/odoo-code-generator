from odoo import models, fields, api, modules, tools


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
