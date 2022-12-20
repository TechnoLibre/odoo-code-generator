import importlib
import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]


class IrModel(models.Model):
    _inherit = "ir.model"

    description = fields.Char()

    diagram_arrow_dst_field = fields.Char(
        help="Diagram arrow field name for destination."
    )

    diagram_arrow_form_view_ref = fields.Char(
        help=(
            "Diagram arrow field, reference view xml id. If empty, will take"
            " default form."
        )
    )

    diagram_arrow_label = fields.Char(
        default="['name']",
        help="Diagram label, data to show when draw a line.",
    )

    diagram_arrow_object = fields.Char(
        help="Diagram arrow model name for arrow."
    )

    diagram_arrow_src_field = fields.Char(
        help="Diagram arrow field name for source."
    )

    diagram_label_string = fields.Char(
        help="Sentence to show at top of diagram."
    )

    diagram_node_form_view_ref = fields.Char(
        help=(
            "Diagram node field, reference view xml id. If empty, will take"
            " default form."
        )
    )

    diagram_node_object = fields.Char(help="Diagram model name for node.")

    diagram_node_shape_field = fields.Char(
        default="rectangle:True",
        help="Diagram node field shape.",
    )

    diagram_node_xpos_field = fields.Char(
        help="Diagram node field name for xpos."
    )

    diagram_node_ypos_field = fields.Char(
        help="Diagram node field name for ypos."
    )

    enable_activity = fields.Boolean(
        help="Will add chatter and activity to this model in form view."
    )

    expression_export_data = fields.Char(
        help=(
            "Set an expression to apply filter when exporting data. example"
            ' ("website_id", "in", [1,2]). Keep it empty to export all data.'
        )
    )

    ignore_name_export_data = fields.Char(
        help="List of ignore file_name separate by ;"
    )

    inherit_model_ids = fields.Many2many(
        comodel_name="code.generator.ir.model.dependency",
        string="Inherit ir Model",
        help="Inherit Model",
    )

    m2o_inherit_py_class = fields.Many2one(
        comodel_name="code.generator.pyclass",
        string="Python Class",
        help="Python Class",
        ondelete="cascade",
    )

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    menu_group = fields.Char(
        help=(
            "If not empty, will create a group of element in menu when"
            " auto-generate."
        )
    )

    menu_label = fields.Char(help="Force label menu to use this value.")

    menu_name_keep_application = fields.Boolean(
        help=(
            "When generate menu name, do we keep application name in item"
            " name?"
        )
    )

    menu_parent = fields.Char(
        help=(
            "If not empty, will create a new root menu of element in menu when"
            " auto-generate."
        )
    )

    nomenclator = fields.Boolean(
        string="Nomenclator?",
        help="Set this if you want this model as a nomenclator",
    )

    o2m_act_window = fields.One2many(
        comodel_name="ir.actions.act_window",
        inverse_name="m2o_res_model",
        string="Act window",
    )

    o2m_code_import = fields.One2many(
        comodel_name="code.generator.model.code.import",
        inverse_name="m2o_model",
        string="Codes import",
    )

    o2m_codes = fields.One2many(
        comodel_name="code.generator.model.code",
        inverse_name="m2o_model",
        string="Codes",
    )

    o2m_constraints = fields.One2many(
        comodel_name="ir.model.constraint",
        inverse_name="model",
        domain=[("type", "=", "u"), ("message", "!=", None)],
        string="Constraints",
    )

    o2m_reports = fields.One2many(
        comodel_name="ir.actions.report",
        inverse_name="m2o_model",
        string="Reports",
        help="Reports associated with this model",
    )

    o2m_server_action = fields.One2many(
        comodel_name="ir.actions.server",
        inverse_name="model_id",
        domain=[
            ("binding_type", "=", "action"),
            "|",
            ("state", "=", "code"),
            ("state", "=", "multi"),
            ("usage", "=", "ir_actions_server"),
        ],
        string="Server action",
    )

    o2m_server_constrains = fields.One2many(
        comodel_name="ir.model.server_constrain",
        inverse_name="m2o_ir_model",
        string="Server Constrains",
        help="Server Constrains attach to this model",
    )

    rec_name = fields.Char(
        default="name",
        help="Will be the field name to use when show the generic name.",
    )

    @api.onchange("m2o_module")
    def _onchange_m2o_module(self):
        if self.m2o_module:

            name4filter = "x_name"
            name4newfield = "name"

        else:

            name4filter = "xname"
            name4newfield = "x_name"

        remain = self.field_id.filtered(
            lambda field: field.name != name4filter
        )

        return dict(
            value=dict(
                field_id=[
                    (6, False, remain.ids),
                    (
                        0,
                        False,
                        dict(
                            name=name4newfield,
                            field_description="Name",
                            ttype="char",
                        ),
                    ),
                ]
            )
        )

    @api.constrains("model")
    def _check_model_name(self):
        for model in self:
            if model.state == "manual":
                if not model.m2o_module and not model.model.startswith("x_"):
                    raise ValidationError(
                        _("The model name must start with 'x_'.")
                    )
            if not models.check_object_name(model.model):
                raise ValidationError(
                    _(
                        "The model name %s can only contain lowercase"
                        " characters, digits, underscores and dots."
                    )
                    % model.model
                )

    def get_rec_name(self):
        return self.rec_name if self.rec_name else self._rec_name

    @api.multi
    def add_model_inherit(self, model_name):
        """

        :param model_name: list or string
        :return:
        """
        lst_model_id = []
        if type(model_name) is str:
            lst_model_name = [model_name]
        elif type(model_name) is list:
            lst_model_name = model_name
        elif isinstance(model_name, models.Model):
            lst_model_name = []
            lst_model_id = model_name
        else:
            _logger.error(
                "Wrong type of model_name in method add_model_inherit:"
                f" {type(model_name)}"
            )
            return
        for ir_model in self:
            inherit_model = None
            if lst_model_id:
                for check_inherit_model in lst_model_id:
                    if check_inherit_model.id not in [
                        a.depend_id.id for a in ir_model.inherit_model_ids
                    ]:
                        if not inherit_model:
                            inherit_model = check_inherit_model
                        else:
                            inherit_model += check_inherit_model
            else:
                for model_name in lst_model_name:
                    check_inherit_model = self.env["ir.model"].search(
                        [("model", "=", model_name)]
                    )
                    if check_inherit_model.id not in [
                        a.depend_id.id for a in ir_model.inherit_model_ids
                    ]:
                        if not inherit_model:
                            inherit_model = check_inherit_model
                        else:
                            inherit_model += check_inherit_model

            if not inherit_model:
                return

            lst_create = [{"depend_id": a.id} for a in inherit_model]
            depend_ids = self.env["code.generator.ir.model.dependency"].create(
                lst_create
            )
            ir_model.inherit_model_ids = depend_ids.ids

            # Add missing field
            actual_field_list = set(ir_model.field_id.mapped("name"))
            lst_dct_field = []
            for ir_model_id in inherit_model:
                diff_list = list(
                    set(ir_model_id.field_id.mapped("name")).difference(
                        actual_field_list
                    )
                )
                lst_new_field = [
                    a for a in ir_model_id.field_id if a.name in diff_list
                ]
                for new_field_id in lst_new_field:
                    # TODO support ttype selection, who extract this information?
                    if new_field_id.ttype == "selection":
                        continue
                    value_field_backup_format = {
                        "name": new_field_id.name,
                        "model": ir_model.model,
                        "field_description": new_field_id.field_description,
                        "ttype": new_field_id.ttype,
                        "model_id": ir_model.id,
                        "ignore_on_code_generator_writer": True,
                    }
                    tpl_relation = ("many2one", "many2many", "one2many")
                    tpl_relation_field = ("many2many", "one2many")
                    if new_field_id.ttype in tpl_relation:
                        value_field_backup_format[
                            "relation"
                        ] = new_field_id.relation

                    if (
                        new_field_id.ttype in tpl_relation_field
                        and new_field_id.relation_field
                    ):
                        value_field_backup_format[
                            "relation_field"
                        ] = new_field_id.relation_field

                    lst_dct_field.append(value_field_backup_format)
            if lst_dct_field:
                self.env["ir.model.fields"].create(lst_dct_field)

    @api.model
    def has_same_model_in_inherit_model(self):
        for inherit_model_id in self.inherit_model_ids:
            # if inherit_model_id.ir_model_ids.ids == self.ids:
            #     return True
            if inherit_model_id.depend_id.id in self.ids:
                return True
        return False

    @api.model
    def _instanciate(self, model_data):
        custommodelclass = super(IrModel, self)._instanciate(model_data)

        try:
            if "rec_name" in model_data and model_data["rec_name"]:
                # TODO this was commented because it caused stack overflow when running with pydev
                # model_fields = self.field_id.search([('model_id', '=', model_data['id'])]). \
                #     filtered(lambda f: f.name not in MAGIC_FIELDS)
                #
                # if model_fields and not model_fields.filtered(lambda f: f.name == model_data['rec_name']):
                #     raise ValidationError(_('The Record Label value must exist within the model fields name.'))

                custommodelclass._rec_name = model_data["rec_name"]

            if (
                "inherit_model_ids" in model_data
                and model_data["inherit_model_ids"]
            ):
                lst_inherit = [
                    a.depend_id.model for a in model_data["inherit_model_ids"]
                ]
                if lst_inherit:
                    if len(lst_inherit) == 1:
                        custommodelclass._inherit = lst_inherit[0]
                    else:
                        custommodelclass._inherit = lst_inherit

            if (
                "m2o_inherit_py_class" in model_data
                and model_data["m2o_inherit_py_class"]
            ):

                try:
                    py_class = self.env["code.generator.pyclass"].browse(
                        model_data["m2o_inherit_py_class"]
                    )
                    m2o_inherit_py_class_module = importlib.import_module(
                        py_class.module
                    )
                    m2o_inherit_py_class = getattr(
                        m2o_inherit_py_class_module, py_class.name
                    )

                    class CustomModelInheritedPyClass(
                        custommodelclass, m2o_inherit_py_class
                    ):
                        pass

                    return CustomModelInheritedPyClass

                except AttributeError:
                    pass

        except RecursionError:
            pass

        return custommodelclass


# class CodeGeneratorBase(models.AbstractModel):
#     _inherit = "base"
#
#     def _run_safe_eval(self, created=None):
#         """
#
#         :param created:
#         :return:
#         """
#
#         records = created or self
#         for r in records:
#             target_model = self.env["ir.model"].search([("model", "=", r._name)])
#             if (
#                 target_model
#                 and hasattr(self.env, target_model[0]._name)
#                 and hasattr(target_model[0], "o2m_server_constrains")
#             ):
#                 codes = target_model.mapped("o2m_server_constrains").mapped("txt_code")
#                 for code in codes:
#                     safe_eval(code, SAFE_EVAL_BASE, {"self": r}, mode="exec")
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         result = super(CodeGeneratorBase, self).create(vals_list)
#
#         self._run_safe_eval(result)
#
#         return result
#
#     @api.multi
#     def write(self, vals):
#         result = super(CodeGeneratorBase, self).write(vals)
#
#         self._run_safe_eval()
#
#         return result
