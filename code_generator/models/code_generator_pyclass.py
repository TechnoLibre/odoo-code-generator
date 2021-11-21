from odoo import models, fields, api, modules, tools


class CodeGeneratorPyclass(models.Model):
    _name = "code.generator.pyclass"
    _description = "Code Generator Python Class"

    name = fields.Char(
        string="Class name",
        required=True,
        help="Class name",
    )

    module = fields.Char(
        string="Class path",
        help="Class path",
    )
