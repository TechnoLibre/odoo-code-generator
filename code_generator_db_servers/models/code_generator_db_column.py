from odoo import _, models, fields, api

import logging

_logger = logging.getLogger(__name__)

SELECTION_TYPE = [
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
]


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

    new_name = fields.Char(help="Rename the field name to this value.")

    field_name = fields.Char(
        help="Field name, use name, or new_name", compute="_compute_field_name"
    )

    description = fields.Char(
        help="Column description, be converted to field description.",
    )

    new_description = fields.Char(
        help="Rename the field description this value."
    )

    field_description = fields.Char(
        help="Field description, use new_description or description.",
        compute="_compute_field_description",
    )

    new_help = fields.Char(string="New help")

    column_type = fields.Selection(
        required=True,
        selection=SELECTION_TYPE,
    )

    new_type = fields.Selection(
        selection=SELECTION_TYPE,
    )

    field_type = fields.Char(
        selection=SELECTION_TYPE, compute="_compute_field_type"
    )

    required = fields.Boolean(
        string="Required",
        help="Column required",
    )

    new_required = fields.Boolean()

    new_change_required = fields.Boolean(
        string="New required update",
        help=(
            "Set at True if need to update required with field new_required"
            " instead of field required."
        ),
    )

    field_required = fields.Boolean(compute="_compute_field_required")

    relation_table_id = fields.Many2one(
        string="Depend table",
        comodel_name="code.generator.db.table",
        ondelete="restrict",
    )

    relation_column_id = fields.Many2one(
        string="Depend column",
        comodel_name="code.generator.db.column",
        ondelete="restrict",
    )

    # is_looping_relation = fields.Boolean(help="Set True when this field is a looping dependency.")

    relation = fields.Char(
        string="Relation many2one",
        help="The field related with foreign key, contain the new model name.",
    )

    relation_column = fields.Char(
        string="Relation many2one column",
        help="The column foreign key from relation.",
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

    temporary_name_field = fields.Boolean(
        string="Temporary name field",
        help=(
            "This field is temporary, at creation, if the __name__ of the"
            " module is name, this will create the field, else ignore it."
        ),
    )

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

    ir_model_field_id = fields.One2many(
        comodel_name="ir.model.fields", inverse_name="db_columns_ids"
    )

    @api.depends(
        "new_name",
        "new_description",
        "new_type",
        "new_help",
        "field_required",
        "force_widget",
        "add_one2many",
        "sql_select_modify",
        "compute_data_function",
        "path_binary",
        "delete",
        "ignore_field",
    )
    def _compute_has_update(self):
        for obj in self:
            has_update = bool(
                obj.new_name
                or obj.new_description
                or obj.new_type
                or obj.new_help
                or obj.force_widget
                or obj.add_one2many
                or obj.sql_select_modify
                or obj.compute_data_function
                or obj.path_binary
                or obj.delete
                or obj.ignore_field
            )
            obj.has_update = has_update or obj.field_required != obj.required

    @api.depends("name", "new_name")
    def _compute_field_name(self):
        for obj in self:
            obj.field_name = obj.new_name if obj.new_name else obj.name

    @api.depends("description", "new_description")
    def _compute_field_description(self):
        for obj in self:
            obj.field_description = (
                obj.new_description if obj.new_description else obj.description
            )

    @api.depends("column_type", "new_type")
    def _compute_field_type(self):
        for obj in self:
            obj.field_type = obj.new_type if obj.new_type else obj.column_type

    @api.depends("required", "new_required", "new_change_required")
    def _compute_field_required(self):
        for obj in self:
            obj.field_required = (
                obj.new_required if obj.new_change_required else obj.required
            )
