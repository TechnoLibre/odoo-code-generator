import logging

from odoo import models, fields, api, _, tools

_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    foreign_key_field_name = fields.Char(string="Foreign key field")

    origin_name = fields.Char(
        string="Origin name", help="Name before migration."
    )

    force_widget = fields.Char(
        string="Force widget",
        help="Use this widget for this field when create views.",
    )

    origin_string = fields.Char(
        string="Origin string", help="String before migration."
    )

    origin_help = fields.Char(
        string="Origin help", help="Help before migration."
    )

    origin_required = fields.Boolean(
        string="Origin required", help="Required before migration."
    )

    origin_type = fields.Char(
        string="Origin type", help="Type before migration."
    )

    path_binary = fields.Char(
        string="Path binary type",
        help=(
            "Attribut path to use with value of char to binary, import binary"
            " in database."
        ),
    )
