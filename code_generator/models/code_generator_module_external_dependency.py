from odoo import models, fields, api, modules, tools


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
