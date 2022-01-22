import logging

from odoo import _, api, fields, models, tools

_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    db_columns_ids = fields.Many2one(
        comodel_name="code.generator.db.column",
    )
