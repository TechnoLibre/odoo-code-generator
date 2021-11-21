from odoo import models, fields, api, modules, tools


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
