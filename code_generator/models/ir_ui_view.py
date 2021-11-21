from odoo import models, fields, api, modules, tools


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    m2o_model = fields.Many2one(
        "ir.model",
        string="Code generator Model",
        help="Model",
        ondelete="cascade",
    )
