import logging

from odoo import models, fields, api, _, tools

_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    db_columns_ids = fields.Many2one(
        comodel_name="code.generator.db.column",
    )
