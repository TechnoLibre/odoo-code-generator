from odoo import api, fields, models, modules, tools


class CodeGeneratorModuleExternalDependency(models.Model):
    _name = "code.generator.module.external.dependency"
    _description = "Code Generator Module External Dependency"

    application_type = fields.Selection(
        selection=[("python", "python"), ("bin", "bin")],
        default="python",
    )

    depend = fields.Char(string="Dependency name")

    # TODO this is wrong, an hack because ir_module_module != code_generator_module
    is_template = fields.Boolean(
        string="Is template",
        help="Will be affect template module.",
    )

    module_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        ondelete="cascade",
    )
