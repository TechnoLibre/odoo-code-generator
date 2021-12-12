from odoo import models, fields, api, modules, tools


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )