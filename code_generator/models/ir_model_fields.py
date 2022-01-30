import ast
import inspect
import logging
import types

import astor

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

FORCE_WIDGET_TYPES = [
    ("barcode_handler", "Barcode handler"),
    ("handle", "Handle"),
    ("float_with_uom", "Float with uom"),
    ("timesheet_uom", "Timesheet uom"),
    ("radio", "Radio"),
    ("priority", "Priority"),
    ("mail_thread", "Mail thread"),
    ("mail_activity", "Mail activity"),
    ("mail_followers", "Mail followers"),
    ("phone", "Phone"),
    ("statinfo", "Statinfo"),
    ("statusbar", "Statusbar"),
    ("many2many", "Many2many"),
    ("many2many_tags", "Many2many tags"),
    ("many2many_tags_email", "Many2many tags email"),
    ("many2many_checkboxes", "Many2many checkboxes"),
    ("many2many_binary", "Many2many binary"),
    ("monetary", "Monetary"),
    ("selection", "Selection"),
    ("url", "Url"),
    ("boolean_button", "Boolean button"),
    ("boolean_toggle", "Boolean toggle"),
    ("toggle_button", "Toggle button"),
    ("state_selection", "State selection"),
    ("kanban_state_selection", "Kanban state selection"),
    ("kanban_activity", "Kanban activity"),
    ("tier_validation", "Tier validation"),
    ("binary_size", "Binary size"),
    ("binary_preview", "Binary preview"),
    ("char_domain", "Char domain"),
    ("domain", "Domain"),
    ("file_actions", "File actions"),
    ("color", "Color"),
    ("copy_binary", "Copy binary"),
    ("share_char", "Share char"),
    ("share_text", "Share text"),
    ("share_binary", "Share binary"),
    ("selection_badge", "Selection badge"),
    ("link_button", "Link button"),
    ("image", "Image"),
    ("contact", "Contact"),
    ("float_time", "Float time"),
    ("image-url", "Image-url"),
    ("html", "Html"),
    ("email", "Email"),
    ("website_button", "Website button"),
    ("one2many", "One2many"),
    ("one2many_list", "One2many list"),
    ("gauge", "Gauge"),
    ("label_selection", "Label selection"),
    ("percentpie", "Percentpie"),
    ("progressbar", "Progressbar"),
    ("mrp_time_counter", "Mrp time counter"),
    ("qty_available", "Qty available"),
    ("ace", "Ace"),
    ("pdf_viewer", "Pdf viewer"),
    ("path_names", "Path names"),
    ("path_json", "Path json"),
    ("date", "Date"),
    ("color_index", "Color index"),
    ("google_partner_address", "Google partner address"),
    ("google_marker_picker", "Google marker picker"),
    ("spread_line_widget", "Spread line widget"),
    ("geo_edit_map", "Geo edit map"),
    ("dynamic_dropdown", "Dynamic dropdown"),
    ("section_and_note_one2many", "Section and note one2many"),
    ("section_and_note_text", "Section and note text"),
    ("reference", "Reference"),
    ("x2many_2d_matrix", "X2many 2d matrix"),
    ("numeric_step", "Numeric step"),
    ("BVEEditor", "Bveeditor"),
    ("er_diagram_image", "Er diagram image"),
    ("u2f_scan", "U2f scan"),
    ("password", "Password"),
    ("open_tab", "Open tab"),
    ("signature", "Signature"),
    ("upgrade_boolean", "Upgrade boolean"),
    ("many2manyattendee", "Many2manyattendee"),
    ("res_partner_many2one", "Res partner many2one"),
    ("hr_org_chart", "Hr org chart"),
    ("CopyClipboardText", "Copyclipboardtext"),
    ("CopyClipboardChar", "Copyclipboardchar"),
    ("bullet_state", "Bullet state"),
    ("pad", "Pad"),
    ("field_partner_autocomplete", "Field partner autocomplete"),
    ("html_frame", "Html frame"),
    ("task_workflow", "Task workflow"),
    ("document_page_reference", "Document page reference"),
    ("mis_report_widget", "Mis report widget"),
    ("kpi", "Kpi"),
    ("action_barcode_handler", "Action barcode handler"),
    ("mail_failed_message", "Mail failed message"),
    ("mermaid", "Mermaid"),
    ("payment", "Payment"),
    ("previous_order", "Previous order"),
]


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    code_generator_calendar_view_sequence = fields.Integer(
        string="calendar view sequence",
        default=-1,
        help=(
            "Sequence to write this field in calendar view from Code"
            " Generator."
        ),
    )

    code_generator_compute = fields.Char(
        string="Compute Code Generator",
        help="Compute method to code_generator_writer.",
    )

    code_generator_form_simple_view_sequence = fields.Integer(
        string="Form simple view sequence",
        default=-1,
        help=(
            "Sequence to write this field in form simple view from Code"
            " Generator."
        ),
    )

    code_generator_graph_view_sequence = fields.Integer(
        string="graph view sequence",
        default=-1,
        help="Sequence to write this field in graph view from Code Generator.",
    )

    code_generator_ir_model_fields_ids = fields.One2many(
        comodel_name="code.generator.ir.model.fields",
        inverse_name="m2o_fields",
        string="Code Generator Ir Model Fields",
        help=(
            "Link to update field when generate, because it cannot update"
            " ir.model.fields in runtime"
        ),
    )

    code_generator_kanban_view_sequence = fields.Integer(
        string="Kanban view sequence",
        default=-1,
        help=(
            "Sequence to write this field in kanban view from Code Generator."
        ),
    )

    code_generator_pivot_view_sequence = fields.Integer(
        string="pivot view sequence",
        default=-1,
        help="Sequence to write this field in pivot view from Code Generator.",
    )

    code_generator_search_sequence = fields.Integer(
        string="Search sequence",
        default=-1,
        help="Sequence to write this field in search from Code Generator.",
    )

    code_generator_search_view_sequence = fields.Integer(
        string="search view sequence",
        default=-1,
        help=(
            "Sequence to write this field in search view from Code Generator."
        ),
    )

    # This is used to choose order to show field in model
    code_generator_sequence = fields.Integer(
        string="Sequence Code Generator",
        help="Sequence to write this field from Code Generator.",
    )

    # TODO remove code_generator_tree_view_sequence and code_generator_search_sequence
    # TODO wrong architecture, separate view order from model
    # TODO This was a work around
    # TODO or maybe it's useful in first iteration of code generator, remove this later when A USE C GENERATE B
    code_generator_tree_view_sequence = fields.Integer(
        string="Tree view sequence",
        default=-1,
        help="Sequence to write this field in tree view from Code Generator.",
    )

    default = fields.Char(string="Default value")

    default_lambda = fields.Char(string="Default lambda value")

    field_context = fields.Char()

    force_widget = fields.Selection(
        FORCE_WIDGET_TYPES,
        string="Force widget",
        help="Use this widget for this field when create views.",
    )

    ignore_on_code_generator_writer = fields.Boolean(
        help="Enable this to ignore it when write code."
    )

    is_date_end_view = fields.Boolean(
        string="Show end date view",
        help="View timeline only, end field.",
    )

    is_date_start_view = fields.Boolean(
        string="Show start date view",
        help="View timeline only, start field.",
    )

    is_hide_blacklist_calendar_view = fields.Boolean(
        string="Hide in blacklist calendar view",
        help="Hide from view when field is blacklisted. View calendar only.",
    )

    is_hide_blacklist_form_view = fields.Boolean(
        string="Hide in blacklist form view",
        help="Hide from view when field is blacklisted. View form only.",
    )

    is_hide_blacklist_graph_view = fields.Boolean(
        string="Hide in blacklist graph view",
        help="Hide from view when field is blacklisted. View graph only.",
    )

    is_hide_blacklist_kanban_view = fields.Boolean(
        string="Hide in blacklist kanban view",
        help="Hide from view when field is blacklisted. View kanban only.",
    )

    is_hide_blacklist_list_view = fields.Boolean(
        string="Hide in blacklist list view",
        help="Hide from view when field is blacklisted. View list only.",
    )

    is_hide_blacklist_model_inherit = fields.Boolean(
        string="Hide in blacklist model inherit",
        help="Hide from model inherit when field is blacklisted.",
    )

    is_hide_blacklist_pivot_view = fields.Boolean(
        string="Hide in blacklist pivot view",
        help="Hide from view when field is blacklisted. View pivot only.",
    )

    is_hide_blacklist_search_view = fields.Boolean(
        string="Hide in blacklist search view",
        help="Hide from view when field is blacklisted. View search only.",
    )

    is_show_whitelist_calendar_view = fields.Boolean(
        string="Show in whitelist calendar view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View calendar only."
        ),
    )

    is_show_whitelist_form_view = fields.Boolean(
        string="Show in whitelist form view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View form only."
        ),
    )

    is_show_whitelist_graph_view = fields.Boolean(
        string="Show in whitelist graph view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View graph only."
        ),
    )

    is_show_whitelist_kanban_view = fields.Boolean(
        string="Show in whitelist kanban view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View kanban only."
        ),
    )

    is_show_whitelist_list_view = fields.Boolean(
        string="Show in whitelist list view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View list only."
        ),
    )

    is_show_whitelist_model_inherit = fields.Boolean(
        string="Show in whitelist model inherit",
        help=(
            "If a field in model is in whitelist, will be show in generated"
            " model."
        ),
    )

    is_show_whitelist_pivot_view = fields.Boolean(
        string="Show in whitelist pivot view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View pivot only."
        ),
    )

    is_show_whitelist_search_view = fields.Boolean(
        string="Show in whitelist search view",
        help=(
            "If a field in model is in whitelist, all is not will be hide."
            " View search only."
        ),
    )

    @api.constrains("name", "state")
    def _check_name(self):
        for field in self:
            if field.state == "manual":
                if (
                    not field.model_id.m2o_module
                    and not field.name.startswith("x_")
                ):
                    raise ValidationError(
                        _(
                            "Custom fields must have a name that starts with"
                            " 'x_' !"
                        )
                    )
            try:
                models.check_pg_name(field.name)
            except ValidationError:
                msg = _(
                    "Field names can only contain characters, digits and"
                    " underscores (up to 63)."
                )
                raise ValidationError(msg)

    @api.model
    def is_show_whitelist_model_inherit_call(self):
        if self.code_generator_ir_model_fields_ids:
            return (
                self.code_generator_ir_model_fields_ids.is_show_whitelist_model_inherit
            )
        return self.is_show_whitelist_model_inherit

    @api.model
    def get_default_lambda(self):
        if self.code_generator_ir_model_fields_ids:
            return self.code_generator_ir_model_fields_ids.default_lambda
        return self.default_lambda

    @api.model
    def get_field_context(self):
        if self.code_generator_ir_model_fields_ids:
            return self.code_generator_ir_model_fields_ids.field_context
        return self.field_context

    @api.model
    def get_code_generator_compute(self):
        if self.code_generator_ir_model_fields_ids:
            if len(self.code_generator_ir_model_fields_ids) > 1:
                # Check if multiple field before crash without message
                lst_model = set(
                    [
                        a.m2o_fields.model
                        for a in self.code_generator_ir_model_fields_ids
                    ]
                )
                lst_field = [
                    a.name for a in self.code_generator_ir_model_fields_ids
                ]
                raise Exception(
                    f"Cannot compute multiple field. In model {lst_model},"
                    f" List of field: {lst_field}"
                )
            else:
                return (
                    self.code_generator_ir_model_fields_ids.code_generator_compute
                )
        return self.code_generator_compute

    @api.model
    def get_selection(self):
        return_value = []

        if self.ttype not in ("reference", "selection"):
            return

        if self.selection and self.selection != "[]":
            try:
                # Transform string in list
                lst_selection = ast.literal_eval(self.selection)
                # lst_selection = [f"'{a}'" for a in lst_selection]
                return_value = lst_selection
            except Exception as e:
                _logger.error(
                    f"The selection of field {self.name} is not a"
                    f" list: '{self.selection}'."
                )
        elif (
            self.code_generator_ir_model_fields_ids
            and self.code_generator_ir_model_fields_ids.selection
            and self.code_generator_ir_model_fields_ids.selection != "[()]"
        ):
            try:
                # Transform string in list
                lst_selection = ast.literal_eval(
                    self.code_generator_ir_model_fields_ids.selection
                )
                return_value = lst_selection
            except Exception as e:
                _logger.error(
                    f"The selection of field {self.name} is not a"
                    f" list: '{self.selection}'."
                )
        if not return_value:
            return_value = self.env[self.model]._fields[self.name].selection
            if isinstance(return_value, types.FunctionType):
                source_code = (
                    inspect.getsource(return_value).strip().strip(",")
                )
                selection_equal_str = "selection="
                # Clean variable assignment if exist
                pos = source_code.find(" = fields.Selection(")
                if pos > 0:
                    source_code = source_code[pos + 3 :].strip()
                    return_value = self._extract_lambda_in_selection(
                        source_code
                    )
                elif selection_equal_str in source_code:
                    return_value = source_code[
                        source_code.find(selection_equal_str)
                        + len(selection_equal_str) :
                    ]
        return return_value

    def _extract_lambda_in_selection(self, source_code):
        # TODO move this function in code extractor
        # Extract lambda name
        tree = ast.parse(source_code)

        class LambdaVisitor(ast.NodeVisitor):
            def __init__(self):
                _new_source = None

            def visit_Lambda(self, node):
                self._new_source = astor.to_source(node).strip()
                if self._new_source[0] == "(" and self._new_source[-1] == ")":
                    self._new_source = self._new_source[1:-1]

            def get_result(self):
                return self._new_source

        visitor = LambdaVisitor()
        visitor.visit(tree)
        return visitor.get_result()

    @api.model
    def create(self, vals):
        model_data = None
        if "model_id" in vals:
            model_data = self.env["ir.model"].browse(vals["model_id"])
            vals["model"] = model_data.model
        if vals.get("ttype") == "selection":
            if not vals.get("selection"):
                raise UserError(
                    _(
                        "For selection fields, the Selection Options must be"
                        " given!"
                    )
                )
            self._check_selection(vals["selection"])

        res = super(models.Model, self).create(vals)

        if vals.get("state", "manual") == "manual":

            check_relation = True
            if vals.get("relation") and vals.get("model_id") and model_data:
                check_relation = not model_data.m2o_module

            if (
                vals.get("relation")
                and not self.env["ir.model"].search(
                    [("model", "=", vals["relation"])]
                )
                and check_relation
            ):
                raise UserError(
                    _("Model %s does not exist!") % vals["relation"]
                )

            if vals.get("ttype") == "one2many":
                # TODO check relation exist, but some times, it's created later to respect many2one order
                # if not self.env[""].search(
                #     [
                #         ("model_id", "=", vals["relation"]),
                #         ("name", "=", vals["relation_field"]),
                #         ("ttype", "=", "many2one"),
                #     ]
                # ):
                #     raise UserError(
                #         _("Many2one %s on model %s does not exist!")
                #         % (vals["relation_field"], vals["relation"])
                #     )
                pass

            self.clear_caches()  # for _existing_field_data()

            if vals["model"] in self.pool:
                # setup models; this re-initializes model in registry
                self.pool.setup_models(self._cr)
                # update database schema of model and its descendant models
                descendants = self.pool.descendants(
                    [vals["model"]], "_inherits"
                )
                self.pool.init_models(
                    self._cr,
                    descendants,
                    dict(self._context, update_custom_fields=True),
                )

        return res
