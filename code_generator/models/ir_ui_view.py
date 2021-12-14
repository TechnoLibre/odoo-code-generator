from odoo import models, fields, api, modules, tools


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    is_hide_blacklist_write_view = fields.Boolean(
        string="Hide in blacklist when writing code view",
        help="Hide from view when field is blacklisted.",
    )

    is_show_whitelist_write_view = fields.Boolean(
        string="Show in whitelist when writing code view",
        help="If a field in model is in whitelist, all is not will be hide. ",
    )

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Code generator Model",
        help="Model",
        ondelete="cascade",
    )
