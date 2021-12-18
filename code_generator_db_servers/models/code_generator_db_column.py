import logging

from odoo import _, api, fields, models

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

    new_default_value = fields.Char(
        help=""""True" -> True
    "False" -> False
    After, will be converted dependent of type."""
    )

    selection_migration_start_at = fields.Integer(
        default=0, help="For migrating data, start indexing from this number."
    )

    new_selection = fields.Char(help=""""Use value like [('value','text'),]""")

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

    is_show_whitelist_list_view = fields.Boolean(
        string="Show in whitelist list view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View list only."
        ),
    )
    is_hide_blacklist_list_view = fields.Boolean(
        string="Hide in blacklist list view",
        help="Hide from view when field is blacklisted. View list only.",
    )
    is_show_whitelist_form_view = fields.Boolean(
        string="Show in whitelist form view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View form only."
        ),
    )
    is_hide_blacklist_form_view = fields.Boolean(
        string="Hide in blacklist form view",
        help="Hide from view when field is blacklisted. View form only.",
    )
    is_show_whitelist_kanban_view = fields.Boolean(
        string="Show in whitelist kanban view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View kanban only."
        ),
    )
    is_hide_blacklist_kanban_view = fields.Boolean(
        string="Hide in blacklist kanban view",
        help="Hide from view when field is blacklisted. View kanban only.",
    )
    is_show_whitelist_search_view = fields.Boolean(
        string="Show in whitelist search view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View search only."
        ),
    )
    is_hide_blacklist_search_view = fields.Boolean(
        string="Hide in blacklist search view",
        help="Hide from view when field is blacklisted. View search only.",
    )
    is_show_whitelist_pivot_view = fields.Boolean(
        string="Show in whitelist pivot view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View pivot only."
        ),
    )
    is_hide_blacklist_pivot_view = fields.Boolean(
        string="Hide in blacklist pivot view",
        help="Hide from view when field is blacklisted. View pivot only.",
    )
    is_show_whitelist_graph_view = fields.Boolean(
        string="Show in whitelist graph view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View graph only."
        ),
    )
    is_hide_blacklist_graph_view = fields.Boolean(
        string="Hide in blacklist graph view",
        help="Hide from view when field is blacklisted. View graph only.",
    )
    is_date_start_view = fields.Boolean(
        string="Is date start timeline view",
        help="View timeline only.",
    )
    is_date_end_view = fields.Boolean(
        string="Is date end timeline view",
        help="View timeline only.",
    )
    is_show_whitelist_calendar_view = fields.Boolean(
        string="Show in whitelist calendar view",
        help=(
            "If a field in model is in whitelist, all is not will be hide. "
            "View calendar only."
        ),
    )
    is_hide_blacklist_calendar_view = fields.Boolean(
        string="Hide in blacklist calendar view",
        help="Hide from view when field is blacklisted. View calendar only.",
    )

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

    def update_column(
        self,
        table_name,
        column_name,
        new_field_name=None,
        new_description=None,
        new_type=None,
        new_help=None,
        new_required=None,
        new_compute=None,
        new_default_value=None,
        new_selection=None,
        selection_migration_start_at=0,
        sql_select_modify=None,
        delete=False,
        ignore_field=False,
        path_binary=None,
        force_widget=None,
        is_show_whitelist_list_view=None,
        is_hide_blacklist_list_view=None,
        is_show_whitelist_form_view=None,
        is_hide_blacklist_form_view=None,
        is_show_whitelist_kanban_view=None,
        is_hide_blacklist_kanban_view=None,
        is_show_whitelist_search_view=None,
        is_hide_blacklist_search_view=None,
        is_show_whitelist_pivot_view=None,
        is_hide_blacklist_pivot_view=None,
        is_show_whitelist_graph_view=None,
        is_hide_blacklist_graph_view=None,
        is_show_whitelist_calendar_view=None,
        is_hide_blacklist_calendar_view=None,
        is_date_start_view=None,
        is_date_end_view=None,
        compute_data_function=None,
        add_one2many=False,
    ):
        """

        :param table_name:
        :param column_name:
        :param new_field_name:
        :param new_description:
        :param new_type:
        :param new_help:
        :param new_required:
        :param new_compute:
        :param new_default_value:
        :param selection_migration_start_at:
        :param new_selection:
        :param sql_select_modify: update select command with this string
        :param delete: import data, use to compute information but delete the field at the end with his data
        :param ignore_field: never compute it and ignore data from it
        :param path_binary: path for type binary when the past was char
        :param force_widget:
        :param is_show_whitelist_list_view:
        :param is_hide_blacklist_list_view:
        :param is_show_whitelist_form_view:
        :param is_hide_blacklist_form_view:
        :param is_show_whitelist_kanban_view:
        :param is_hide_blacklist_kanban_view:
        :param is_show_whitelist_search_view:
        :param is_hide_blacklist_search_view:
        :param is_show_whitelist_pivot_view:
        :param is_hide_blacklist_pivot_view:
        :param is_show_whitelist_graph_view:
        :param is_hide_blacklist_graph_view:
        :param is_date_start_view:
        :param is_date_end_view:
        :param is_show_whitelist_calendar_view:
        :param is_hide_blacklist_calendar_view:
        :param compute_data_function: function, in string, to run with data in argument and overwrite data
        :param add_one2many:
        :return:
        """
        table_id = self.env["code.generator.db.table"].search(
            [("name", "=", table_name)]
        )
        if not table_id:
            _logger.error(
                f"Cannot update table {table_name} with column {column_name}."
            )
            return

        column_id = self.env["code.generator.db.column"].search(
            [("m2o_table", "=", table_id.id), ("name", "=", column_name)]
        )
        if len(column_id) > 1:
            _logger.error(
                f"Find too much column {column_name} from table {table_name}."
            )
            return
        elif not column_id:
            _logger.error(
                f"Cannot column {column_name} from table {table_name}."
            )
            return
        if new_field_name:
            column_id.new_name = new_field_name
        if new_description:
            column_id.new_description = new_description
        if new_type:
            column_id.new_type = new_type
        if new_default_value:
            column_id.new_default_value = new_default_value
        if selection_migration_start_at:
            column_id.selection_migration_start_at = (
                selection_migration_start_at
            )
        if new_selection:
            column_id.new_selection = new_selection.replace("\n", "")
        if new_help:
            column_id.new_help = new_help
        if new_required is not None:
            column_id.new_change_required = True
            column_id.new_required = new_required
        if new_compute is not None:
            column_id.new_compute = new_compute
        if path_binary:
            column_id.path_binary = path_binary
        if force_widget:
            column_id.force_widget = force_widget
        if is_show_whitelist_list_view:
            column_id.is_show_whitelist_list_view = is_show_whitelist_list_view
        if is_hide_blacklist_list_view:
            column_id.is_hide_blacklist_list_view = is_hide_blacklist_list_view
        if is_show_whitelist_form_view:
            column_id.is_show_whitelist_form_view = is_show_whitelist_form_view
        if is_hide_blacklist_form_view:
            column_id.is_hide_blacklist_form_view = is_hide_blacklist_form_view
        if is_show_whitelist_kanban_view:
            column_id.is_show_whitelist_kanban_view = (
                is_show_whitelist_kanban_view
            )
        if is_hide_blacklist_kanban_view:
            column_id.is_hide_blacklist_kanban_view = (
                is_hide_blacklist_kanban_view
            )
        if is_show_whitelist_search_view:
            column_id.is_show_whitelist_search_view = (
                is_show_whitelist_search_view
            )
        if is_hide_blacklist_search_view:
            column_id.is_hide_blacklist_search_view = (
                is_hide_blacklist_search_view
            )
        if is_show_whitelist_pivot_view:
            column_id.is_show_whitelist_pivot_view = (
                is_show_whitelist_pivot_view
            )
        if is_hide_blacklist_pivot_view:
            column_id.is_hide_blacklist_pivot_view = (
                is_hide_blacklist_pivot_view
            )
        if is_show_whitelist_graph_view:
            column_id.is_show_whitelist_graph_view = (
                is_show_whitelist_graph_view
            )
        if is_hide_blacklist_graph_view:
            column_id.is_hide_blacklist_graph_view = (
                is_hide_blacklist_graph_view
            )
        if is_show_whitelist_calendar_view:
            column_id.is_show_whitelist_calendar_view = (
                is_show_whitelist_calendar_view
            )
        if is_hide_blacklist_calendar_view:
            column_id.is_hide_blacklist_calendar_view = (
                is_hide_blacklist_calendar_view
            )
        if is_date_start_view:
            column_id.is_date_start_view = is_date_start_view
        if is_date_end_view:
            column_id.is_date_end_view = is_date_end_view
        if add_one2many:
            column_id.add_one2many = add_one2many
        if compute_data_function:
            column_id.compute_data_function = compute_data_function
        if sql_select_modify:
            column_id.sql_select_modify = sql_select_modify
        if delete:
            column_id.delete = True
        if ignore_field:
            column_id.ignore_field = True
