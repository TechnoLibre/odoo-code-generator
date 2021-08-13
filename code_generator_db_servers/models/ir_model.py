import logging

from odoo import models, fields, api, _, tools

_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    foreign_key_field_name = fields.Char(string="Foreign key field")
