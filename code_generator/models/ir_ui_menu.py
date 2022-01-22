from odoo import api, fields, models, modules, tools


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    ignore_act_window = fields.Boolean(
        help="Set True to force no act_window, like a parent menu."
    )
