from odoo import api, fields, models, modules, tools


class CodeGeneratorModelCodeImport(models.Model):
    _name = "code.generator.model.code.import"
    _description = "Header code to display in model"

    name = fields.Char(
        string="Import name",
        help="import name",
    )

    code = fields.Text(help="Code of import header of python file")

    is_templated = fields.Boolean(
        string="Templated",
        help="Code for code generator from template.",
    )

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        help="Model",
        ondelete="cascade",
    )

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    sequence = fields.Integer(help="Order of sequence code.")
