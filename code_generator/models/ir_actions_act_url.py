from odoo import models, fields, api, modules, tools


class IrActionsActUrl(models.Model):
    _inherit = "ir.actions.act_url"

    m2o_code_generator = fields.Many2one(
        "code.generator.module",
        string="Code Generator",
        help="Code Generator relation",
        ondelete="cascade",
    )
