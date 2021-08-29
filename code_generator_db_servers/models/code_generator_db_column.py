from odoo import _, models, fields, api

import logging

_logger = logging.getLogger(__name__)


class CodeGeneratorDbColumn(models.Model):
    _name = "code.generator.db.column"
    _description = "Code Generator Db Column"

    m2o_table = fields.Many2one(
        "code.generator.db.table", "Table", required=True, ondelete="cascade"
    )

    name = fields.Char(string="Name", help="Column name", required=True)

    description = fields.Char(
        string="Description",
        help="Column description",
    )

    required = fields.Boolean(
        string="Required",
        help="Column required",
    )

    column_type = fields.Selection(
        string="Column type",
        help="Column type",
        required=True,
        selection=[
            ("char", "Char"),
            ("text", "Text"),
            ("integer", "Integer"),
            ("monetary", "Monetary"),
            ("float", "Float"),
            ("datetime", "Datetime"),
            ("date", "Date"),
            ("boolean", "Boolean"),
            ("html", "Html"),
            ("binary", "Binary"),
            ("selection", "Selection"),
            ("many2one", "Many2one"),
            # TODO support many2many
            # ("many2many", "Many2many"),
            # Cannot detect one2many in database relation
            # ("one2many", "One2many"),
        ],
    )
