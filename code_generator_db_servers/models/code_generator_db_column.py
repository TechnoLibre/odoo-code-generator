from odoo import _, models, fields, api

import logging

_logger = logging.getLogger(__name__)


class CodeGeneratorDbColumn(models.Model):
    _name = "code.generator.db.column"
    _description = "Code Generator Db Column"

    m2o_table = fields.Many2one(
        "code.generator.db.table", "Table", required=True, ondelete="cascade"
    )

    name = fields.Char(
        string="Name",
        help="Column name, be converted to field name.",
        required=True,
    )

    new_name = fields.Char(
        string="New name", help="Rename the field name to this value."
    )

    string = fields.Char(
        "String",
        help=(
            "The string representation of field name. By default, it's the"
            " title of the field name."
        ),
    )

    new_string = fields.Char(string="New string")

    new_type = fields.Char(string="New type")

    description = fields.Char(
        string="Description",
        help="Column description",
    )

    required = fields.Boolean(
        string="Required",
        help="Column required",
    )

    new_required = fields.Boolean(string="New required")

    new_change_required = fields.Boolean(
        string="New required update",
        help="Set at True if need to update required value.",
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

    force_widget = fields.Char(
        string="Force widget",
        help="Use this widget for this field when create views.",
    )

    add_one2many = fields.Boolean(
        string="Add one2many",
        help="Add field one2many to related model on this field.",
    )

    sql_select_modify = fields.Char(
        string="SQL selection modify",
        help="Change field name with this query",
    )

    compute_data_function = fields.Char(
        string="Function compute data",
        help=(
            "Will be execute when extract data, first argument is the origin"
            " data and return data to be overwrite. In string, will be execute"
            " with eval. Use variable name from field in the model."
        ),
    )

    path_binary = fields.Char(
        string="Path binary type",
        help=(
            "Attribut path to use with value of char to binary, import binary"
            " in database."
        ),
    )

    new_help = fields.Char(string="New help")

    delete = fields.Boolean(
        string="Delete", help="When enable, remove the field in generation."
    )

    ignore_field = fields.Boolean(
        string="Ignore field",
        help="When enable, ignore import field and never compute it.",
    )

    has_update = fields.Boolean(
        string="Has new data",
        compute="_compute_has_update",
        store=True,
    )

    temporary_name_field = fields.Boolean(
        string="Temporary name field",
        help=(
            "This field is temporary, at creation, if the __name__ of the"
            " module is name, this will create the field, else ignore it."
        ),
    )

    @api.depends(
        "new_name",
        "new_string",
        "new_type",
        "new_change_required",
        "force_widget",
        "add_one2many",
        "sql_select_modify",
        "compute_data_function",
        "path_binary",
        "new_help",
        "delete",
        "ignore_field",
    )
    def _compute_has_update(self):
        for obj in self:
            obj.has_update = bool(
                obj.new_name
                or obj.new_name
                or obj.new_string
                or obj.new_change_required
                or obj.force_widget
                or obj.add_one2many
                or obj.sql_select_modify
                or obj.compute_data_function
                or obj.compute_data_function
                or obj.path_binary
                or obj.new_help
                or obj.delete
                or obj.ignore_field
            )
