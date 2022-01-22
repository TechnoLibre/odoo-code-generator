from odoo import api, fields, models, modules, tools


class IrActionsTodo(models.Model):
    _inherit = "ir.actions.todo"

    m2o_code_generator = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        help="Code Generator relation",
        ondelete="cascade",
    )
