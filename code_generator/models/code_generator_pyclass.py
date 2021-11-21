from odoo import models, fields, api, modules, tools


class CodeGeneratorPyClass(models.Model):
    _name = "code.generator.pyclass"
    _description = "Code Generator Python Class"

    name = fields.Char(string="Class name", help="Class name", required=True)

    module = fields.Char(string="Class path", help="Class path")
