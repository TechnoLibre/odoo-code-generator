from odoo import fields, models


class ResGroups(models.Model):
    _inherit = "res.groups"

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )
