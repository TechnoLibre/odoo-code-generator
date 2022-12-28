import logging
import time
import uuid
from collections import defaultdict

import unidecode
from lxml import etree as ET
from lxml.builder import E

from odoo import _, api, fields, models
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]


class CodeGeneratorGenerateViewsWizard(models.TransientModel):
    _name = "code.generator.generate.views.wizard"
    _description = "Code Generator Generate Views Wizard"

    # @api.model
    # def default_get(self, fields):
    #     result = super(CodeGeneratorGenerateViewsWizard, self).default_get(fields)
    #     code_generator_id = self.env["code.generator.module"].browse(result.get("code_generator_id"))
    #     lst_model_id = [a.id for a in code_generator_id.o2m_models]
    # Don't need that solution
    #     result["selected_model_tree_view_ids"] = [(6, 0, lst_model_id)]
    #     result["selected_model_form_view_ids"] = [(6, 0, lst_model_id)]
    #     return result

    name = fields.Char()

    all_model = fields.Boolean(
        string="All models",
        default=True,
        help="Generate with all existing model, or select manually.",
    )

    clear_all_access = fields.Boolean(
        string="Clear access",
        default=True,
        help="Clear all access/permission before execute.",
    )

    clear_all_act_window = fields.Boolean(
        string="Clear actions windows",
        default=True,
        help="Clear all actions windows before execute.",
    )

    clear_all_menu = fields.Boolean(
        string="Clear menus",
        default=True,
        help="Clear all menus before execute.",
    )

    clear_all_view = fields.Boolean(
        string="Clear views",
        default=True,
        help="Clear all views before execute.",
    )

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    code_generator_view_ids = fields.Many2many(
        comodel_name="code.generator.view",
        string="Code Generator View",
    )

    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )

    disable_generate_access = fields.Boolean(
        help="Disable security access generation."
    )

    disable_generate_menu = fields.Boolean(help="Disable menu generation.")

    enable_generate_all = fields.Boolean(
        string="Enable all feature",
        default=True,
        help="Generate with all feature.",
    )

    selected_model_calendar_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_calendar_view_ids_ir_model",
        string="Selected Model Calendar View",
    )

    selected_model_diagram_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_diagram_view_ids_ir_model",
        string="Selected Model Diagram View",
    )

    selected_model_form_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_form_view_ids_ir_model",
        string="Selected Model Form View",
    )

    selected_model_graph_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_graph_view_ids_ir_model",
        string="Selected Model Graph View",
    )

    selected_model_kanban_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_kanban_view_ids_ir_model",
        string="Selected Model Kanban View",
    )

    selected_model_pivot_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_pivot_view_ids_ir_model",
        string="Selected Model Pivot View",
    )

    selected_model_search_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_search_view_ids_ir_model",
        string="Selected Model Search View",
    )

    selected_model_timeline_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_timeline_view_ids_ir_model",
        string="Selected Model Timeline View",
    )

    selected_model_tree_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_tree_view_ids_ir_model",
        string="Selected Model Tree View",
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda s: s.env.user.id,
    )

    generated_root_menu = None
    generated_parent_menu = None
    dct_group_generated_menu = {}
    dct_parent_generated_menu = {}
    lst_group_generated_menu_name = []
    lst_parent_generated_menu_name = []
    nb_sub_menu = 0

    def clear_all(self):
        # if self.clear_all_view and self.code_generator_id.o2m_model_views:
        #     self.code_generator_id.o2m_model_views.unlink()
        if self.clear_all_access and self.code_generator_id.o2m_model_access:
            self.code_generator_id.o2m_model_access.unlink()
        if self.clear_all_menu and self.code_generator_id.o2m_menus:
            self.code_generator_id.o2m_menus.unlink()
        if self.clear_all_act_window:
            if self.code_generator_id.o2m_model_act_window:
                self.code_generator_id.o2m_model_act_window.unlink()
            if self.code_generator_id.o2m_model_act_todo:
                self.code_generator_id.o2m_model_act_todo.unlink()
            if self.code_generator_id.o2m_model_act_url:
                self.code_generator_id.o2m_model_act_url.unlink()

    @api.multi
    def button_generate_views(self):
        self.ensure_one()

        # Add dependencies
        self._add_dependencies()

        self.clear_all()

        # TODO refactor this part to control generation
        dct_value_to_create = defaultdict(list)

        before_time = time.process_time()

        if not self.code_generator_view_ids:
            status = self.generic_generate_view(dct_value_to_create)
        else:
            model_id = None
            lst_view_generated = []
            lst_model_id = []
            for code_generator_view_id in self.code_generator_view_ids:
                view_id = self._generate_specific_form_views_models(
                    code_generator_view_id, dct_value_to_create
                )
                if not view_id:
                    _logger.error(
                        "Cannot create view_id or find existing. Skip for"
                        f" '{code_generator_view_id.id_name}'"
                    )
                else:
                    lst_view_generated.append(view_id.type)
                    lst_model_id.append(view_id.m2o_model)
            lst_model_id = list(set(lst_model_id))
            for model_id in lst_model_id:
                self._generate_model_access(model_id)
            if model_id:
                self._generate_menu(
                    model_id,
                    model_id.m2o_module,
                    lst_view_generated,
                    self.code_generator_id.o2m_models,
                )
            status = True
        # Accelerate creation in batch
        for model_name, lst_value in dct_value_to_create.items():
            self.env[model_name].create(lst_value)

        after_time = time.process_time()
        _logger.info(
            "DEBUG time execution button_generate_views"
            f" {after_time - before_time}"
        )
        return status

    @api.multi
    def generic_generate_view(self, dct_value_to_create):
        # before_time = time.process_time()
        o2m_models_view_tree = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_tree_view_ids
        )
        o2m_models_view_form = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_form_view_ids
        )
        o2m_models_view_kanban = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_kanban_view_ids
        )
        o2m_models_view_search = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_search_view_ids
        )
        o2m_models_view_pivot = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_pivot_view_ids
        )
        o2m_models_view_calendar = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_calendar_view_ids
        )
        o2m_models_view_graph = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_graph_view_ids
        )
        o2m_models_view_timeline = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_timeline_view_ids
        )
        o2m_models_view_diagram = (
            self.code_generator_id.o2m_models.filtered(
                lambda model: model.diagram_node_object
                and model.diagram_arrow_object
                and model.diagram_node_xpos_field
                and model.diagram_node_ypos_field
                and model.diagram_arrow_src_field
                and model.diagram_arrow_dst_field
            )
            if self.all_model
            else self.selected_model_diagram_view_ids
        )
        # Get unique list order by name of all model to generate
        lst_model = sorted(
            set(
                o2m_models_view_tree
                + o2m_models_view_form
                + o2m_models_view_kanban
                + o2m_models_view_search
                + o2m_models_view_pivot
                + o2m_models_view_calendar
                + o2m_models_view_graph
                + o2m_models_view_timeline
            ),
            key=lambda model: model.name,
        )
        lst_model_id = self.env["ir.model"].browse([a.id for a in lst_model])

        for model_id in lst_model_id:
            lst_view_generated = []

            # Support enable_activity
            if model_id.enable_activity:
                model_id.add_model_inherit(
                    ["mail.thread", "mail.activity.mixin"]
                )
                # inherit_model_ids
                lst_view_generated.append("activity")

            # Different view
            if model_id in o2m_models_view_tree:
                is_whitelist = any(
                    [a.is_show_whitelist_list_view for a in model_id.field_id]
                )
                # model_created_fields_tree = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_list_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_list_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_tree = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_list_view
                    and (
                        not is_whitelist
                        or (is_whitelist and field.is_show_whitelist_list_view)
                    )
                )
                model_created_fields_tree = self._update_model_field_tree_view(
                    model_created_fields_tree
                )
                self._generate_list_views_models(
                    model_id,
                    model_created_fields_tree,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("tree")

            if model_id in o2m_models_view_form:
                is_whitelist = any(
                    [
                        a.is_show_whitelist_form_view
                        for b in model_id
                        for a in b.field_id
                    ]
                )
                # model_created_fields_form = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_form_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_form_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_form = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_form_view
                    and (
                        not is_whitelist
                        or (is_whitelist and field.is_show_whitelist_form_view)
                    )
                )
                self._generate_form_views_models(
                    model_id,
                    model_created_fields_form,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("form")

            if model_id in o2m_models_view_kanban:
                is_whitelist = any(
                    [
                        a.is_show_whitelist_kanban_view
                        for b in model_id
                        for a in b.field_id
                    ]
                )
                # model_created_fields_kanban = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_kanban_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_kanban_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_kanban = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_kanban_view
                    and (
                        not is_whitelist
                        or (
                            is_whitelist
                            and field.is_show_whitelist_kanban_view
                        )
                    )
                )
                self._generate_kanban_views_models(
                    model_id,
                    model_created_fields_kanban,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("kanban")

            if model_id in o2m_models_view_search:
                is_whitelist = any(
                    [
                        a.is_show_whitelist_search_view
                        for b in model_id
                        for a in b.field_id
                    ]
                )
                # model_created_fields_search = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_search_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_search_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_search = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_search_view
                    and (
                        not is_whitelist
                        or (
                            is_whitelist
                            and field.is_show_whitelist_search_view
                        )
                    )
                )
                self._generate_search_views_models(
                    model_id,
                    model_created_fields_search,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("search")

            if model_id in o2m_models_view_pivot:
                is_whitelist = any(
                    [
                        a.is_show_whitelist_pivot_view
                        for b in model_id
                        for a in b.field_id
                    ]
                )
                # model_created_fields_pivot = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_pivot_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_pivot_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_pivot = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_pivot_view
                    and (
                        not is_whitelist
                        or (
                            is_whitelist and field.is_show_whitelist_pivot_view
                        )
                    )
                )
                self._generate_pivot_views_models(
                    model_id,
                    model_created_fields_pivot,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("pivot")

            if model_id in o2m_models_view_calendar:
                is_whitelist = any(
                    [
                        a.is_show_whitelist_calendar_view
                        for b in model_id
                        for a in b.field_id
                    ]
                )
                # model_created_fields_calendar = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_calendar_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_calendar_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_calendar = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_calendar_view
                    and (
                        not is_whitelist
                        or (
                            is_whitelist
                            and field.is_show_whitelist_calendar_view
                        )
                    )
                )
                has_start_date = any(
                    [
                        a.is_date_start_view
                        for a in model_created_fields_calendar
                    ]
                )
                if has_start_date:
                    self._generate_calendar_views_models(
                        model_id,
                        model_created_fields_calendar,
                        model_id.m2o_module,
                        dct_value_to_create,
                    )
                    lst_view_generated.append("calendar")

            if model_id in o2m_models_view_graph:
                is_whitelist = any(
                    [
                        a.is_show_whitelist_graph_view
                        for b in model_id
                        for a in b.field_id
                    ]
                )
                # model_created_fields_graph = list(
                #     filter(
                #         lambda x: x.name not in MAGIC_FIELDS
                #                   and not x.is_hide_blacklist_graph_view
                #                   and (
                #                           not is_whitelist
                #                           or (is_whitelist and x.is_show_whitelist_graph_view)
                #                   ),
                #         [a for a in model_id.field_id],
                #     )
                # )
                model_created_fields_graph = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_graph_view
                    and (
                        not is_whitelist
                        or (
                            is_whitelist and field.is_show_whitelist_graph_view
                        )
                    )
                )
                self._generate_graph_views_models(
                    model_id,
                    model_created_fields_graph,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("graph")

            if model_id in o2m_models_view_timeline:
                model_created_fields_timeline = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and field.ttype in ("date", "datetime")
                    and (field.is_date_start_view or field.is_date_end_view)
                )

                if model_created_fields_timeline:
                    self._generate_timeline_views_models(
                        model_id,
                        model_created_fields_timeline,
                        model_id.m2o_module,
                        dct_value_to_create,
                    )
                    lst_view_generated.append("timeline")

            if model_id in o2m_models_view_diagram:
                lst_view_generated.append("diagram")

            # Menu and action_windows
            self._generate_menu(
                model_id,
                model_id.m2o_module,
                lst_view_generated,
                lst_model_id,
            )

        # Need form to be created before create diagram
        for model_id in o2m_models_view_diagram:
            self._generate_diagram_views_models(
                model_id,
                model_id.m2o_module,
                dct_value_to_create,
            )

        # for model_id in o2m_models_view_form:
        #     print(model_id)
        # model_created_fields = model_id.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS).mapped(
        #     'name')
        #

        for model_id in self.code_generator_id.o2m_models:
            self._generate_model_access(model_id)

        # after_time = time.process_time()
        # _logger.info(
        #     "DEBUG time execution generic_generate_view"
        #     f" {after_time - before_time}"
        # )
        return True

    def _add_dependencies(self):
        # Check if need to add mail dependency
        for code_generator in self.code_generator_id:
            need_mail_depend = any(
                [a.enable_activity for a in code_generator.o2m_models]
            )
            if not need_mail_depend:
                continue

            code_generator.add_module_dependency("mail")

    def _update_model_field_tree_view(self, model_created_fields_tree):
        return model_created_fields_tree

    def _generate_list_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")

        lst_field_to_remove = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_tree_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_tree_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_tree_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_tree_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_tree_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )
            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            lst_field_sorted = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                )
            )
        else:
            # Use tree view sequence, or generic sequence
            lst_field_sorted = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
            ).sorted(lambda field: field.code_generator_tree_view_sequence)

        # lst_field = [E.field({"name": a.name}) for a in model_created_fields]
        lst_field = []
        for field_id in lst_field_sorted:
            if field_id.name in lst_field_to_remove:
                continue
            # TODO validate code_generator_tree_view_sequence is supported
            # if a.code_generator_tree_view_sequence >= 0
            dct_value = {"name": field_id.name}
            if field_id.force_widget:
                dct_value["widget"] = field_id.force_widget
            dct_value = dict(sorted(dct_value.items(), key=lambda kv: kv[0]))
            lst_field.append(E.field(dct_value))
        arch_xml = E.tree(
            {
                # TODO enable this when missing form
                # "editable": "top",
            },
            *lst_field,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_tree",
        #     "type": "tree",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_tree"),
                ("type", "=", "tree"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_tree",
                    "type": "tree",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_form_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        lst_item_sheet = []
        key = "geo_"

        lst_field_to_transform_button_box = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_form_simple_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_form_simple_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_form_simple_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_form_simple_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_form_simple_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )

            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            field_sorted_ids = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                )
            )
        else:
            field_sorted_ids = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
            ).sorted(
                lambda x: x.code_generator_form_simple_view_sequence,
            )

        lst_button_box = []
        for field_id in field_sorted_ids:
            if field_id.name in lst_field_to_transform_button_box:
                item_field = E.field(
                    {"name": field_id.name, "widget": "boolean_button"}
                )
                item_button = E.button(
                    {
                        "class": "oe_stat_button",
                        "icon": "fa-archive",
                        "name": "toggle_active",
                        "type": "object",
                    },
                    item_field,
                )
                lst_button_box.append(item_button)

        if lst_button_box:
            item = E.div(
                {"class": "oe_button_box", "name": "button_box"},
                *lst_button_box,
            )
            lst_item_sheet.append(item)

        for field_id in field_sorted_ids:
            if field_id.name in lst_field_to_transform_button_box:
                continue
            lst_value = []
            value = {"name": field_id.name}
            lst_value.append(value)

            if field_id.force_widget:
                if field_id.force_widget != "link_button":
                    # TODO add a configuration to force edible mode, if not editable, choose widget = link button
                    # special case, link button is readonly in form,
                    value["widget"] = field_id.force_widget
            elif key in field_id.ttype:
                value["widget"] = "geo_edit_map"
                # value["attrs"] = "{'invisible': [('type', '!=', '"f"{model[len(key):]}')]""}"
            # lst_field.append(value)
            lst_item_sheet.append(E.group({}, E.field(value)))

        lst_item_form = [E.sheet({}, *lst_item_sheet)]

        if model_created.enable_activity:
            xml_activity = E.div(
                {"class": "oe_chatter"},
                E.field(
                    {
                        # "groups": "base.group_user",
                        # "help": "",
                        "name": "message_follower_ids",
                        "widget": "mail_followers",
                    }
                ),
                E.field({"name": "activity_ids", "widget": "mail_activity"}),
                E.field(
                    {
                        "name": "message_ids",
                        "options": "{'post_refresh': 'recipients'}",
                        "widget": "mail_thread",
                    }
                ),
            )
            lst_item_form.append(xml_activity)

        arch_xml = E.form(
            {
                "string": "Titre",
            },
            *lst_item_form,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_form",
        #     "type": "form",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_form"),
                ("type", "=", "form"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_form",
                    "type": "form",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

            model_data_value = self.env["ir.model.data"].create(
                {
                    "name": f"{model_name_str}_view_form",
                    "model": "ir.ui.view",
                    "module": module.name,
                    "res_id": view_value.id,
                    "noupdate": True,  # If it's False, target record (res_id) will be removed while module update
                }
            )

        return view_value

    def _generate_kanban_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")

        lst_field_to_remove = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_kanban_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_kanban_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_kanban_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_kanban_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_kanban_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )
            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            lst_field_sorted = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                )
            )
        else:
            # Use kanban view sequence, or generic sequence
            lst_field_sorted = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
            ).sorted(lambda field: field.code_generator_kanban_view_sequence)

        # lst_field = [E.field({"name": a.name}) for a in model_created_fields]
        lst_field = []
        lst_field_template = []
        for field_id in lst_field_sorted:
            if field_id.name in lst_field_to_remove:
                continue
            # TODO validate code_generator_kanban_view_sequence is supported
            # if a.code_generator_kanban_view_sequence >= 0
            dct_value = {"name": field_id.name}
            if field_id.force_widget:
                dct_value["widget"] = field_id.force_widget
            dct_value = dict(sorted(dct_value.items(), key=lambda kv: kv[0]))
            lst_field.append(E.field(dct_value))

            if field_id.ttype == "boolean":
                # TODO detect type success/danger or another type of boolean
                dct_templates_value = E.li(
                    {
                        "class": "text-success float-right mb4",
                        "t-if": f"record.{field_id.name}.raw_value",
                    },
                    E.i(
                        {
                            "aria-label": "Ok",
                            "class": "fa fa-circle",
                            "role": "img",
                            "title": "Ok",
                        }
                    ),
                )
                lst_field_template.append(dct_templates_value)

                dct_templates_value = E.li(
                    {
                        "class": "text-danger float-right mb4",
                        "t-if": f"!record.{field_id.name}.raw_value",
                    },
                    E.i(
                        {
                            "aria-label": "Invalid",
                            "class": "fa fa-circle",
                            "role": "img",
                            "title": "Invalid",
                        }
                    ),
                )
                lst_field_template.append(dct_templates_value)
            else:
                dct_templates_value = E.li(
                    {"class": "mb4"},
                    E.strong(E.field({"name": field_id.name})),
                )
                lst_field_template.append(dct_templates_value)

        template_item = E.templates(
            {},
            E.t(
                {"t-name": "kanban-box"},
                E.div(
                    {"t-attf-class": "oe_kanban_global_click"},
                    E.div(
                        {"class": "oe_kanban_details"},
                        E.ul({}, *lst_field_template),
                    ),
                ),
            ),
        )
        lst_item_kanban = lst_field + [template_item]
        arch_xml = E.kanban(
            {
                "class": "o_kanban_mobile",
            },
            *lst_item_kanban,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_kanban",
        #     "type": "kanban",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_kanban"),
                ("type", "=", "kanban"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_kanban",
                    "type": "kanban",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_search_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        model_name_display_str = model_name_str.replace("_", " ").capitalize()

        lst_field_to_remove = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_search_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_search_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_search_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_search_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_search_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )
            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            lst_field_sorted = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                )
            )
        else:
            # Use search view sequence, or generic sequence
            lst_field_sorted = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
            ).sorted(lambda field: field.code_generator_search_view_sequence)

        # lst_field = [E.field({"name": a.name}) for a in model_created_fields]
        lst_field = []
        lst_field_filter = []
        lst_item_search = []
        for field_id in lst_field_sorted:
            if field_id.name in lst_field_to_remove:
                # Add inactive
                dct_templates_value = E.filter(
                    {
                        "domain": f"[('{field_id.name}','=',False)]",
                        "name": "Inactive",
                        "string": f"Inactive {model_name_display_str}",
                    }
                )
                lst_field_filter.append(dct_templates_value)
                continue
            # TODO validate code_generator_search_view_sequence is supported
            # if a.code_generator_search_view_sequence >= 0

            if field_id.ttype == "boolean":
                dct_templates_value = E.filter(
                    {
                        "domain": f"[('{field_id.name}','=',True)]",
                        "name": field_id.name,
                        "string": field_id.field_description,
                    }
                )
                lst_field_filter.append(dct_templates_value)
            else:
                dct_templates_value = E.filter(
                    {
                        "domain": f"[('{field_id.name}','!=',False)]",
                        "name": field_id.name,
                        "string": field_id.field_description,
                    }
                )
                lst_field_filter.append(dct_templates_value)

        lst_item_search = lst_field + lst_field_filter
        arch_xml = E.search(
            {
                "string": model_name_display_str,
            },
            *lst_item_search,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_search",
        #     "type": "search",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_search"),
                ("type", "=", "search"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_search",
                    "type": "search",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_pivot_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        model_name_display_str = model_name_str.replace("_", " ").capitalize()

        lst_field_to_remove = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_pivot_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_pivot_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_pivot_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_pivot_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_pivot_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )
            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            lst_field_sorted = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                    and field.ttype not in ("many2many", "one2many", "binary")
                )
            )
        else:
            # Use pivot view sequence, or generic sequence
            lst_field_sorted = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
                and field.ttype not in ("many2many", "one2many", "binary")
            ).sorted(lambda field: field.code_generator_pivot_view_sequence)

        # lst_field = [E.field({"name": a.name}) for a in model_created_fields]
        lst_field = []
        for field_id in lst_field_sorted:
            if field_id.name in lst_field_to_remove:
                continue
            # TODO validate code_generator_pivot_view_sequence is supported
            # if a.code_generator_pivot_view_sequence >= 0

            # TODO detect field_type col, when it's a date?
            if model_created.rec_name == field_id.name:
                field_type = "row"
            elif field_id.ttype in ("integer", "float"):
                field_type = "measure"
            else:
                field_type = "row"

            dct_templates_value = E.field(
                {
                    "name": field_id.name,
                    "type": field_type,
                }
            )
            lst_field.append(dct_templates_value)

        lst_item_pivot = lst_field
        arch_xml = E.pivot(
            {
                "string": model_name_display_str,
            },
            *lst_item_pivot,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_pivot",
        #     "type": "pivot",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_pivot"),
                ("type", "=", "pivot"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_pivot",
                    "type": "pivot",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_calendar_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        model_name_display_str = model_name_str.replace("_", " ").capitalize()

        lst_field_to_remove = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_calendar_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_calendar_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_calendar_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_calendar_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_calendar_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )
            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            lst_field_sorted = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                )
            )
        else:
            # Use calendar view sequence, or generic sequence
            lst_field_sorted = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
            ).sorted(lambda field: field.code_generator_calendar_view_sequence)

        # lst_field = [E.field({"name": a.name}) for a in model_created_fields]
        lst_field = []
        date_start = None
        for field_id in lst_field_sorted:
            if field_id.name in lst_field_to_remove:
                continue
            # TODO validate code_generator_calendar_view_sequence is supported
            # if a.code_generator_calendar_view_sequence >= 0

            dct_value = {"name": field_id.name}
            if field_id.force_widget:
                dct_value["widget"] = field_id.force_widget

            if field_id.is_date_start_view:
                if date_start:
                    _logger.warning(
                        f"Double date_start in model {model_name}."
                    )
                date_start = field_id

            dct_templates_value = E.field(dct_value)
            lst_field.append(dct_templates_value)

        if not date_start:
            _logger.error(
                f"Missing date_start in view calendar for model {model_name}."
            )
            return

        lst_item_calendar = lst_field
        arch_xml = E.calendar(
            {
                "color": model_created.rec_name,
                "date_start": date_start.name,
                "string": model_name_display_str,
            },
            *lst_item_calendar,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_calendar",
        #     "type": "calendar",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_calendar"),
                ("type", "=", "calendar"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_calendar",
                    "type": "calendar",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_graph_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        model_name_display_str = model_name_str.replace("_", " ").capitalize()

        lst_field_to_remove = ("active",)

        has_sequence = False
        for field_id in model_created_fields:
            if field_id.code_generator_graph_view_sequence >= 0:
                has_sequence = True
                break

        if not has_sequence:
            lst_order_field_id = [[], [], []]
            # code_generator_graph_view_sequence all -1, default value
            # Move rec_name in beginning
            # Move one2many at the end
            for field_id in model_created_fields:
                if field_id.name == model_created.rec_name:
                    # TODO write this value
                    lst_order_field_id[0].append(field_id.id)
                    # field_id.code_generator_graph_view_sequence = 0
                elif field_id.ttype == "one2many":
                    lst_order_field_id[2].append(field_id.id)
                    # field_id.code_generator_graph_view_sequence = 2
                else:
                    lst_order_field_id[1].append(field_id.id)
                    # field_id.code_generator_graph_view_sequence = 1
            new_lst_order_field_id = (
                lst_order_field_id[0]
                + lst_order_field_id[1]
                + lst_order_field_id[2]
            )
            # TODO this can slow, can we accumulate this data for the end?
            # field_sorted_sequence_0 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[0]
            # )
            # field_sorted_sequence_1 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[1]
            # )
            # field_sorted_sequence_2 = self.env["ir.model.fields"].browse(
            #     lst_order_field_id[2]
            # )
            # field_sorted_sequence_0.write(
            #     {"code_generator_form_simple_view_sequence": 0}
            # )
            # field_sorted_sequence_1.write(
            #     {"code_generator_form_simple_view_sequence": 1}
            # )
            # field_sorted_sequence_2.write(
            #     {"code_generator_form_simple_view_sequence": 2}
            # )
            # field_sorted_ids = (
            #     field_sorted_sequence_0
            #     + field_sorted_sequence_1
            #     + field_sorted_sequence_2
            # )
            lst_field_sorted = (
                self.env["ir.model.fields"]
                .browse(new_lst_order_field_id)
                .filtered(
                    lambda field: not field.ignore_on_code_generator_writer
                    and field.ttype not in ("many2many", "one2many")
                )
            )
        else:
            # Use graph view sequence, or generic sequence
            lst_field_sorted = model_created_fields.filtered(
                lambda field: not field.ignore_on_code_generator_writer
                and field.ttype not in ("many2many", "one2many")
            ).sorted(lambda field: field.code_generator_graph_view_sequence)

        # lst_field = [E.field({"name": a.name}) for a in model_created_fields]
        lst_field = []
        for field_id in lst_field_sorted:
            if field_id.name in lst_field_to_remove:
                continue
            # TODO validate code_generator_graph_view_sequence is supported
            # if a.code_generator_graph_view_sequence >= 0

            # TODO detect field_type col, when it's a date?
            if model_created.rec_name == field_id.name:
                field_type = "row"
            elif field_id.ttype in ("integer", "float"):
                field_type = "measure"
            else:
                field_type = "row"

            dct_templates_value = E.field(
                {
                    "name": field_id.name,
                    "type": field_type,
                }
            )
            lst_field.append(dct_templates_value)

        lst_item_graph = lst_field
        arch_xml = E.graph(
            {
                "string": model_name_display_str,
            },
            *lst_item_graph,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_graph",
        #     "type": "graph",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_graph"),
                ("type", "=", "graph"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_graph",
                    "type": "graph",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_timeline_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        model_name_display_str = model_name_str.replace("_", " ").capitalize()

        start_date = None
        end_date = None
        for field_id in model_created_fields:
            if field_id.is_date_start_view and not start_date:
                start_date = field_id
            if field_id.is_date_end_view and not end_date:
                end_date = field_id

        if not start_date:
            _logger.warning(
                "Missing start date field, need word start in name."
            )
        if not end_date:
            _logger.warning("Missing end date field, need word start in name.")
        if not start_date or not end_date:
            return

        # lst_item_timeline = lst_field
        arch_xml = E.timeline(
            {
                "date_start": start_date.name,
                "date_stop": end_date.name,
                "default_group_by": model_created.rec_name,
                "event_open_popup": "True",
                "string": model_name_display_str,
            }
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_timeline",
        #     "type": "timeline",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_timeline"),
                ("type", "=", "timeline"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_timeline",
                    "type": "timeline",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_diagram_views_models(
        self, model_created, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        model_name_display_str = model_name_str.replace("_", " ").capitalize()

        if (
            not model_created.diagram_node_object
            or not model_created.diagram_node_xpos_field
            or not model_created.diagram_node_ypos_field
            or not model_created.diagram_arrow_object
            or not model_created.diagram_arrow_src_field
            or not model_created.diagram_arrow_dst_field
        ):
            _logger.error(
                "Cannot create diagram view, missing field in model, check"
                " diagram_*"
            )
            return

        model_node = module.env["ir.model"].search(
            [("model", "=", model_created.diagram_node_object)], limit=1
        )
        if not model_node:
            _logger.error(
                f"Diagram model {model_created.diagram_node_object} doesn't"
                " exist."
            )
            return
        model_arrow = module.env["ir.model"].search(
            [("model", "=", model_created.diagram_arrow_object)], limit=1
        )
        if not model_arrow:
            _logger.error(
                f"Diagram model {model_created.diagram_arrow_object} doesn't"
                " exist."
            )
            return

        lst_field_node = [E.field({"name": model_node.rec_name})]
        lst_field_arrow = [
            E.field({"name": model_created.diagram_arrow_src_field}),
            E.field({"name": model_created.diagram_arrow_dst_field}),
            E.field({"name": model_arrow.rec_name}),
        ]

        # Take first
        node_form_view = module.env["ir.ui.view"].search(
            [
                ("model", "=", model_created.diagram_node_object),
                ("type", "=", "form"),
            ],
            limit=1,
        )
        node_xml_id = module.env["ir.model.data"].search(
            [("model", "=", "ir.ui.view"), ("res_id", "=", node_form_view.id)]
        )
        arrow_form_view = module.env["ir.ui.view"].search(
            [
                ("model", "=", model_created.diagram_arrow_object),
                ("type", "=", "form"),
            ],
            limit=1,
        )
        arrow_xml_id = module.env["ir.model.data"].search(
            [("model", "=", "ir.ui.view"), ("res_id", "=", arrow_form_view.id)]
        )

        arch_xml = E.diagram(
            {},
            E.node(
                {
                    # "bgcolor":"",
                    "form_view_ref": node_xml_id.name,
                    "object": model_created.diagram_node_object,
                    "shape": "rectangle:True",
                    "xpos": model_created.diagram_node_xpos_field,
                    "ypos": model_created.diagram_node_ypos_field,
                },
                *lst_field_node,
            ),
            E.arrow(
                {
                    "destination": model_created.diagram_arrow_dst_field,
                    "form_view_ref": arrow_xml_id.name,
                    "label": f"['{model_arrow.rec_name}']",
                    "object": model_created.diagram_arrow_object,
                    "source": model_created.diagram_arrow_src_field,
                },
                *lst_field_arrow,
            ),
            E.label(
                {
                    "for": "",
                    "string": (
                        "Caution, all modification is live. Diagram model:"
                        f" {model_created.model}, node model:"
                        f" {model_created.diagram_node_object} and arrow"
                        f" model: {model_created.diagram_arrow_object}"
                    ),
                }
            ),
        )

        str_arch = ET.tostring(arch_xml, pretty_print=True)
        str_arch = b'<?xml version="1.0"?>\n' + str_arch
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].search(
            [
                ("name", "=", f"{model_name_str}_diagram"),
                ("type", "=", "diagram"),
                ("model", "=", model_name),
                # ("arch", "=", str_arch),
                ("m2o_model", "=", model_created.id),
            ]
        )
        if not view_value:
            view_value = self.env["ir.ui.view"].create(
                {
                    "name": f"{model_name_str}_diagram",
                    "type": "diagram",
                    "model": model_name,
                    "arch": str_arch,
                    "m2o_model": model_created.id,
                }
            )

        return view_value

    def _generate_xml_button(self, item, model_id, lst_child_update=None):
        button_attributes = {
            "name": item.action_name,
            "type": "object",
        }
        if item.label:
            button_attributes["string"] = item.label
        if item.button_type:
            button_attributes["class"] = item.button_type
        if item.icon:
            button_attributes["icon"] = item.icon

        # Create method
        items = self.env["code.generator.model.code"].search(
            [
                ("name", "=", item.action_name),
                ("m2o_model", "=", model_id),
                ("m2o_module", "=", self.code_generator_id.id),
            ]
        )
        # TODO get this list from module base
        lst_ignore_code = ["toggle_active"]
        if not items and item.action_name not in lst_ignore_code:
            value = {
                "code": '''"""TODO what to run"""
pass''',
                "name": item.action_name,
                "decorator": "@api.multi",
                "param": "self",
                "m2o_module": self.code_generator_id.id,
                "m2o_model": model_id,
                "is_wip": True,
            }
            self.env["code.generator.model.code"].create(value)
        button_attributes = dict(
            sorted(button_attributes.items(), key=lambda kv: kv[0])
        )
        if lst_child_update:
            return E.button(button_attributes, *lst_child_update)

        return E.button(button_attributes)

    @staticmethod
    def _generate_xml_html_help(item, lst_child, dct_replace):
        """

        :param item:
        :param lst_child: list of item to add more in some context
        :param dct_replace: need it to replace html in xml without validation
        :return:
        """
        dct_item = {"string": "Help"}
        if item.colspan > 1:
            dct_item["colspan"] = str(item.colspan)
        dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
        item_xml = E.separator(dct_item)
        lst_child.append(item_xml)

        uid = str(uuid.uuid1())
        dct_replace[uid] = item.label
        item_xml = E.div({}, uid)
        return item_xml

    def _generate_xml_object(self, item, model_id, lst_child=None):
        lst_child_update = [] if not lst_child else lst_child
        item_xml = None
        dct_item = {}
        # TODO duplicate code here with function _generate_xml_title_field
        if not item.item_type == "html":
            if item.name:
                dct_item["name"] = item.name
            elif item.action_name:
                dct_item["name"] = item.action_name

            if item.t_name:
                dct_item["t-name"] = item.t_name
            if item.t_attf_class:
                dct_item["t-attf-class"] = item.t_attf_class
            if item.t_if:
                dct_item["t-if"] = item.t_if
            if item.title:
                dct_item["title"] = item.title
            if item.aria_label:
                dct_item["aria-label"] = item.aria_label
            if item.role:
                dct_item["role"] = item.role
            if item.type:
                dct_item["type"] = item.type
            if item.widget:
                dct_item["widget"] = item.widget
            if item.label:
                dct_item["string"] = item.label
            if item.domain:
                dct_item["domain"] = item.domain
            if item.context:
                dct_item["context"] = item.context
            if item.class_attr:
                dct_item["class"] = item.class_attr

        if item.item_type == "field":
            if item.placeholder:
                dct_item["placeholder"] = item.placeholder
            if item.password:
                dct_item["password"] = "True"
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.field(dct_item)
        elif item.item_type == "filter":
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.filter(dct_item)
        elif item.item_type == "button":
            return self._generate_xml_button(
                item, model_id, lst_child_update=lst_child_update
            )
        elif item.item_type == "html":
            lst_html_child = []
            if item.background_type:
                old_class = dct_item.get("class")
                if old_class and old_class != item.background_type:
                    _logger.error(
                        "Duplicate class, old class: {old_class},"
                        " background_type {item.background_type}"
                    )
                dct_item["class"] = item.background_type
                if item.background_type.startswith("bg-warning"):
                    lst_html_child.append(E.h3({}, "Warning:"))
                elif item.background_type.startswith("bg-success"):
                    lst_html_child.append(E.h3({}, "Success:"))
                elif item.background_type.startswith("bg-info"):
                    lst_html_child.append(E.h3({}, "Info:"))
                elif item.background_type.startswith("bg-danger"):
                    lst_html_child.append(E.h3({}, "Danger:"))
            lst_html_child.append(item.label)
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.div(dct_item, *lst_html_child)
        elif item.item_type == "group":
            if item.label:
                dct_item["string"] = item.label
            if item.attrs:
                dct_item["attrs"] = item.attrs
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.group(dct_item, *lst_child_update)
        elif item.item_type == "li":
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.li(dct_item, *lst_child_update)
        elif item.item_type == "ul":
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.ul(dct_item, *lst_child_update)
        elif item.item_type == "i":
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.i(dct_item, *lst_child_update)
        elif item.item_type == "t":
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.t(dct_item, *lst_child_update)
        elif item.item_type == "strong":
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.strong(dct_item, *lst_child_update)
        elif item.item_type == "xpath":
            if not item.expr:
                _logger.error(
                    f"Missing expr for item action_name {item.action_name}"
                )
            elif not item.position:
                _logger.error(
                    f"Missing position for item action_name {item.action_name}"
                )
            else:
                dct_item["expr"] = item.expr
                dct_item["position"] = item.position
                dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
                item_xml = E.xpath(dct_item, *lst_child_update)
        elif item.item_type == "div":
            if item.attrs:
                dct_item["attrs"] = item.attrs
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.div(dct_item, *lst_child_update)
        elif item.item_type == "templates":
            if item.attrs:
                dct_item["attrs"] = item.attrs
            dct_item = dict(sorted(dct_item.items(), key=lambda kv: kv[0]))
            item_xml = E.templates(dct_item, *lst_child_update)
        else:
            _logger.warning(f"View item '{item.item_type}' is not supported.")
        return item_xml

    def _generate_xml_group_div(self, item, lst_xml, dct_replace, model_id):
        """

        :param item:
        :param lst_xml: list of item to add more in some context
        :param dct_replace: need it to replace html in xml without validation
        :return:
        """
        lst_child = sorted(item.child_id, key=lambda a: a.sequence)
        lst_item_child = []
        if lst_child:
            for item_child_id in lst_child:
                item_child = self._generate_xml_group_div(
                    item_child_id, lst_xml, dct_replace, model_id
                )
                if item_child is not None:
                    lst_item_child.append(item_child)
                else:
                    _logger.warning(
                        "Missing item xml group div about view item"
                        f" '{item_child_id.item_type}'"
                    )
            item_xml = self._generate_xml_object(
                item, model_id, lst_child=lst_item_child
            )
        else:
            item_xml = self._generate_xml_object(item, model_id)

        if item_xml is None:
            _logger.error(f"Cannot generate view for item {item.action_name}")

        return item_xml

    @staticmethod
    def _generate_xml_title_field(item, lst_child, level=0):
        """

        :param item: type odoo.api.code.generator.view.item
        :param lst_child: list of item to add more in some context
        :param level: 0 is bigger level (H1), >=4 is H5
        :return:
        """
        if item.edit_only or item.has_label:
            dct_item_label = {"for": item.action_name}
            if item.edit_only:
                dct_item_label["class"] = "oe_edit_only"
            item_label = E.label(dct_item_label)
            lst_child.append(item_label)
        dct_item_field = {}
        if item.name:
            dct_item_field["name"] = item.name
        else:
            dct_item_field["name"] = item.action_name

        if item.type:
            dct_item_field["type"] = item.type

        if item.is_required:
            dct_item_field["required"] = "1"
        if item.is_readonly:
            dct_item_field["readonly"] = "1"
        dct_item_field = dict(
            sorted(dct_item_field.items(), key=lambda kv: kv[0])
        )
        item_field = E.field(dct_item_field)
        if level == 0:
            result = E.h1({}, item_field)
        elif level == 1:
            result = E.h2({}, item_field)
        elif level == 2:
            result = E.h3({}, item_field)
        elif level == 3:
            result = E.h4({}, item_field)
        else:
            result = E.h5({}, item_field)
        return result

    def _generate_specific_form_views_models(
        self, code_generator_view_id, dct_value_to_create
    ):
        view_type = code_generator_view_id.view_type
        model_name = code_generator_view_id.m2o_model.model
        model_id = code_generator_view_id.m2o_model.id
        dct_replace = {}
        lst_item_header = []
        lst_item_footer = []
        lst_item_body = []
        lst_item_title = []
        for view_item in code_generator_view_id.view_item_ids:
            if view_item.section_type == "body":
                lst_item_body.append(view_item)
            elif view_item.section_type == "header":
                lst_item_header.append(view_item)
            elif view_item.section_type == "footer":
                lst_item_footer.append(view_item)
            elif view_item.section_type == "title":
                lst_item_title.append(view_item)
            else:
                _logger.warning(
                    f"View item '{view_item.section_type}' is not supported."
                )

        lst_item_form = []
        lst_item_form_sheet = []

        if lst_item_header:
            lst_item_header = sorted(lst_item_header, key=lambda a: a.sequence)
            lst_child = []
            for item_header in lst_item_header:
                if item_header.item_type == "field":
                    item = E.field()
                    # TODO field in header
                elif item_header.item_type == "button":
                    item = self._generate_xml_button(item_header, model_id)
                else:
                    _logger.warning(
                        f"Item header type '{item_header.item_type}' is not"
                        " supported."
                    )
                    continue
                lst_child.append(item)
            header_xml = E.header({}, *lst_child)
            lst_item_form.append(header_xml)

        if lst_item_title:
            lst_item_title = sorted(lst_item_title, key=lambda a: a.sequence)
            lst_child = []
            i = 0
            for item_title in lst_item_title:
                if item_title.item_type == "field":
                    item = self._generate_xml_title_field(
                        item_title, lst_child, level=i
                    )
                elif item_title.item_type == "button":
                    _logger.warning(
                        f"Button is not supported in title section."
                    )
                    continue
                else:
                    _logger.warning(
                        f"Item title type '{item_title.item_type}' is not"
                        " supported."
                    )
                    continue
                i += 1
                lst_child.append(item)
            title_xml = E.div({"class": "oe_title"}, *lst_child)
            lst_item_form_sheet.append(title_xml)

        if lst_item_body:
            lst_item_root_body = [a for a in lst_item_body if not a.parent_id]
            lst_item_root_body = sorted(
                lst_item_root_body, key=lambda a: a.sequence
            )
            for item_body in lst_item_root_body:
                if item_body.is_help:
                    item_xml = self._generate_xml_html_help(
                        item_body, lst_item_form_sheet, dct_replace
                    )
                    lst_item_form_sheet.append(item_xml)
                elif item_body.item_type in ("div", "group", "templates"):
                    if not item_body.child_id:
                        _logger.warning(
                            f"Item type '{item_body.item_type}' missing child."
                        )
                        continue
                    item_xml = self._generate_xml_group_div(
                        item_body, lst_item_form_sheet, dct_replace, model_id
                    )
                    if item_xml is not None:
                        lst_item_form_sheet.append(item_xml)
                elif item_body.item_type in ("xpath",):
                    # TODO maybe move this in lst_item_xpath with view_item.section_type == 'xpath'
                    if not item_body.child_id:
                        _logger.warning(f"Item type xpath missing child.")
                        continue
                    item_xml = self._generate_xml_group_div(
                        item_body, lst_item_form_sheet, dct_replace, model_id
                    )
                    if item_xml is not None:
                        lst_item_form_sheet.append(item_xml)
                elif item_body.item_type in ("field", "filter"):
                    item_xml = self._generate_xml_object(item_body, model_id)
                    if item_xml is not None:
                        lst_item_form_sheet.append(item_xml)
                else:
                    _logger.warning(f"Unknown type xml {item_body.item_type}")

        if lst_item_footer:
            lst_item_footer = sorted(lst_item_footer, key=lambda a: a.sequence)
            lst_child = []
            for item_footer in lst_item_footer:
                if item_footer.item_type == "field":
                    item = E.field()
                    # TODO field in footer
                elif item_footer.item_type == "button":
                    item = self._generate_xml_button(item_footer, model_id)
                else:
                    _logger.warning(
                        f"Item footer type '{item_footer.item_type}' is not"
                        " supported."
                    )
                    continue
                if item:
                    lst_child.append(item)
            footer_xml = E.footer({}, *lst_child)
            lst_item_form.append(footer_xml)

        if lst_item_form_sheet:
            if code_generator_view_id.has_body_sheet:
                sheet_xml = E.sheet({}, *lst_item_form_sheet)
                lst_item_form.append(sheet_xml)
            else:
                lst_item_form += lst_item_form_sheet

        dct_attr_view = {}
        if code_generator_view_id.view_attr_string:
            dct_attr_view["string"] = code_generator_view_id.view_attr_string

        if code_generator_view_id.view_attr_class:
            dct_attr_view["class"] = code_generator_view_id.view_attr_class

        dct_attr_view = dict(
            sorted(dct_attr_view.items(), key=lambda kv: kv[0])
        )
        if code_generator_view_id.inherit_view_name:
            if len(lst_item_form) > 1:

                form_xml = E.data(dct_attr_view, *lst_item_form)
            else:
                form_xml = lst_item_form[0]
        elif view_type == "form":
            form_xml = E.form(dct_attr_view, *lst_item_form)
        elif view_type == "search":
            form_xml = E.search(dct_attr_view, *lst_item_form)
        elif view_type == "tree":
            form_xml = E.tree(dct_attr_view, *lst_item_form)
        elif view_type == "kanban":
            form_xml = E.kanban(dct_attr_view, *lst_item_form)
        elif view_type == "graph":
            form_xml = E.graph(dct_attr_view, *lst_item_form)
        elif view_type == "pivot":
            form_xml = E.pivot(dct_attr_view, *lst_item_form)
        else:
            _logger.warning(
                f"Unknown xml view_type {view_type}, attribute {dct_attr_view}"
            )
            return

        str_arch = ET.tostring(form_xml, pretty_print=True)
        str_content = str_arch.decode()

        for key, value in dct_replace.items():
            str_content = str_content.replace(key, value)

        view_name = (
            code_generator_view_id.view_name
            if code_generator_view_id.view_name
            else f"{model_name.replace('.', '_')}_{view_type}"
        )
        dct_view_value = {
            "name": view_name,
            "type": view_type,
            "model": model_name,
            "arch": str_content,
            "m2o_model": code_generator_view_id.m2o_model.id,
        }
        if code_generator_view_id.inherit_view_name:
            dct_view_value["inherit_id"] = self.env.ref(
                code_generator_view_id.inherit_view_name
            ).id
            dct_view_value["is_show_whitelist_write_view"] = True
        lst_search = [
            (a, "=", b)
            for a, b in dct_view_value.items()
            if a not in ("m2o_model", "arch")
        ]
        view_value = self.env["ir.ui.view"].search(lst_search)
        if not view_value:
            view_value = self.env["ir.ui.view"].create(dct_view_value)
        else:
            view_value.m2o_model = code_generator_view_id.m2o_model.id
            # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)

        if code_generator_view_id.id_name:
            ir_model_data_id = self.env["ir.model.data"].search(
                [
                    ("name", "=", code_generator_view_id.id_name),
                    ("model", "=", "ir.ui.view"),
                    (
                        "module",
                        "=",
                        code_generator_view_id.code_generator_id.name,
                    ),
                ]
            )
            if ir_model_data_id:
                ir_model_data_id.res_id = view_value.id
            else:
                self.env["ir.model.data"].create(
                    {
                        "name": code_generator_view_id.id_name,
                        "model": "ir.ui.view",
                        "module": code_generator_view_id.code_generator_id.name,
                        "res_id": view_value.id,
                        "noupdate": True,  # If it's False, target record (res_id) will be removed while module update
                    }
                )

        return view_value

    def _generate_model_access(self, model_created):
        if self.disable_generate_access:
            return
        # Unique access
        # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
        # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
        # TODO search system lang
        lang = "en_US"
        group_id = self.env.ref("base.group_user").with_context(lang=lang)
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        name = "%s Access %s" % (model_name_str, group_id.full_name)
        # TODO maybe search by permission and model, ignore the name
        existing_access = self.env["ir.model.access"].search(
            [
                ("model_id", "=", model_created.id),
                ("group_id", "=", group_id.id),
                ("name", "=", name),
            ]
        )
        if existing_access:
            return

        v = {
            "name": name,
            "model_id": model_created.id,
            "group_id": group_id.id,
            "perm_read": True,
            "perm_create": True,
            "perm_write": True,
            "perm_unlink": True,
        }

        access_value = self.env["ir.model.access"].create(v)

    def _generate_menu(
        self, model_created, module, lst_view_generated, model_ids
    ):
        if self.disable_generate_menu:
            return

        # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
        # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
        is_generic_menu = not model_created.m2o_module.code_generator_menus_id
        group_id = self.env.ref("base.group_user")
        model_name = model_created.model
        menu_group = model_created.menu_group
        menu_parent = model_created.menu_parent
        model_name_str = model_name.replace(".", "_")
        module_name = module.name
        menu_group_id = None
        menu_parent_id = None
        if module.application and is_generic_menu:
            # Create root if not exist
            if not self.generated_root_menu:
                v = {
                    "name": module_name.replace("_", " ").title(),
                    "sequence": 20,
                    "web_icon": f"code_generator,static/description/icon_new_application.png",
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                }
                self.generated_root_menu = self.env["ir.ui.menu"].create(v)
            if not self.generated_parent_menu:
                v = {
                    "name": _("Menu"),
                    "sequence": 1,
                    "parent_id": self.generated_root_menu.id,
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                }
                self.generated_parent_menu = self.env["ir.ui.menu"].create(v)

        # Create list of menu_parent
        if not self.lst_parent_generated_menu_name:
            self.lst_parent_generated_menu_name = sorted(
                list(set([a.menu_parent for a in model_ids if a.menu_parent]))
            )

        # Create list of menu_group
        if not self.lst_group_generated_menu_name:
            self.lst_group_generated_menu_name = sorted(
                list(set([a.menu_group for a in model_ids if a.menu_group]))
            )

        # Create menu_parent item
        if is_generic_menu and menu_parent:
            menu_parent_id = self.dct_parent_generated_menu.get(menu_parent)
            if menu_parent == "Configuration":
                sequence = 99
            else:
                sequence = (
                    self.lst_parent_generated_menu_name.index(menu_parent) + 1
                )

            if not menu_parent_id:
                v = {
                    "name": menu_parent,
                    "sequence": sequence,
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                    "parent_id": self.generated_root_menu.id,
                }

                menu_parent_id = self.env["ir.ui.menu"].create(v)
                self.dct_parent_generated_menu[menu_parent] = menu_parent_id

                # Create id name
                menu_parent_name = (
                    f"parent_{unidecode.unidecode(menu_parent).replace(' ','').lower()}"
                )
                self.env["ir.model.data"].create(
                    {
                        "name": menu_parent_name,
                        "model": "ir.ui.menu",
                        "module": module.name,
                        "res_id": menu_parent_id.id,
                        "noupdate": True,
                        # If it's False, target record (res_id) will be removed while module update
                    }
                )

        # Create menu_group item
        if is_generic_menu and menu_group:
            menu_group_id = self.dct_group_generated_menu.get(menu_group)
            sequence = self.lst_group_generated_menu_name.index(menu_group)
            if not menu_group_id:
                v = {
                    "name": menu_group,
                    "sequence": sequence,
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                }
                if menu_parent_id:
                    v["parent_id"] = menu_parent_id.id
                elif self.generated_parent_menu:
                    v["parent_id"] = self.generated_parent_menu.id
                else:
                    v["parent_id"] = self.generated_root_menu.id

                menu_group_id = self.env["ir.ui.menu"].create(v)
                self.dct_group_generated_menu[menu_group] = menu_group_id

                # Create id name
                menu_group_name = (
                    f"group_{unidecode.unidecode(menu_group).replace(' ','').lower()}"
                )
                self.env["ir.model.data"].create(
                    {
                        "name": menu_group_name,
                        "model": "ir.ui.menu",
                        "module": module.name,
                        "res_id": menu_group_id.id,
                        "noupdate": True,
                        # If it's False, target record (res_id) will be removed while module update
                    }
                )

        help_str = f"""<p class="o_view_nocontent_empty_folder">
        Add a new {model_name_str}
          </p>
          <p>
            Databases whose tables could be imported to Odoo and then be exported into code
          </p>
        """

        # TODO change sequence of view mode
        # Kanban first by default
        if "kanban" in lst_view_generated:
            lst_first_view_generated = ["kanban"]
            lst_second_view_generated = list(set(lst_view_generated[:]))
            lst_second_view_generated.remove("kanban")
        else:
            lst_first_view_generated = []
            lst_second_view_generated = list(set(lst_view_generated))

        # Special case, cannot support search view type in action_view
        try:
            lst_second_view_generated.remove("search")
        except:
            pass

        view_mode = ",".join(
            lst_first_view_generated
            + sorted(lst_second_view_generated, reverse=True)
        )
        view_type = (
            "form" if "form" in lst_view_generated else lst_view_generated[0]
        )

        # Create menu
        if module.application and is_generic_menu:
            # Compute menu name
            menu_name = model_name_str
            if "." in model_name:
                application_name, sub_model_name = model_name.split(
                    ".", maxsplit=1
                )
                if model_created.menu_label:
                    menu_name = model_created.menu_label
                elif (
                    not model_created.menu_name_keep_application
                    and sub_model_name
                    and menu_name.lower().startswith(application_name.lower())
                ):
                    menu_name = (
                        sub_model_name.capitalize()
                        .replace(".", " ")
                        .replace("_", " ")
                    )
                else:
                    menu_name = f"{application_name} {sub_model_name.replace('.', ' ')}".capitalize().replace(
                        "_", " "
                    )
            else:
                menu_name = model_name
            # Create action
            v = {
                "name": menu_name,
                "res_model": model_name,
                "type": "ir.actions.act_window",
                "view_mode": view_mode,
                "view_type": view_type,
                # 'help': help_str,
                # 'search_view_id': self.search_view_id.id,
                "context": {},
                "m2o_res_model": model_created.id,
            }
            action_id = self.env["ir.actions.act_window"].create(v)

            # TODO check function _get_action_data_name in code_generator_writer.py
            fix_action_id_name = (
                unidecode.unidecode(menu_name)
                .replace(" ", "_")
                .replace("'", "_")
                .replace("-", "_")
                .lower()
            )
            action_id_name = (
                f"{model_name_str}_{fix_action_id_name}_action_window"
            )

            v_ir_model_data = {
                "name": action_id_name,
                "model": "ir.actions.act_window",
                "module": module.name,
                "res_id": action_id.id,
                "noupdate": True,
            }
            self.env["ir.model.data"].create(v_ir_model_data)

            self.nb_sub_menu += 1

            v = {
                "name": menu_name,
                "sequence": self.nb_sub_menu,
                "action": "ir.actions.act_window,%s" % action_id.id,
                # 'group_id': group_id.id,
                "m2o_module": module.id,
            }

            if menu_group_id:
                v["parent_id"] = menu_group_id.id
            elif menu_parent_id:
                v["parent_id"] = menu_parent_id.id
            elif self.generated_parent_menu:
                v["parent_id"] = self.generated_parent_menu.id

            new_menu_id = self.env["ir.ui.menu"].create(v)

            menu_id_name = (
                unidecode.unidecode(menu_name)
                .replace(" ", "_")
                .replace("'", "_")
                .replace("-", "_")
                .lower()
            )

            v_ir_model_data = {
                "name": menu_id_name,
                "model": "ir.ui.menu",
                "module": module.name,
                "res_id": new_menu_id.id,
                "noupdate": True,
            }
            self.env["ir.model.data"].create(v_ir_model_data)
        elif not is_generic_menu:
            cg_menu_ids = model_created.m2o_module.code_generator_menus_id
            # TODO check different case, with act_window, without, multiple menu, single menu
            # Sort parent first

            lst_menu_to_sort = [a for a in cg_menu_ids]
            lst_menu = []
            lst_inserted_menu_name = []
            i = -1
            while lst_menu_to_sort:
                i += 1
                lst_added_menu = []
                if len(lst_menu_to_sort) <= i:
                    # Re loop
                    i = 0
                menu_id = lst_menu_to_sort[i]
                menu_name = menu_id.id_name
                if not menu_id.parent_id_name:
                    lst_inserted_menu_name.append(menu_name)
                    lst_added_menu.append(menu_id)
                else:
                    parent_module_name = None
                    if "." in menu_id.parent_id_name:
                        (
                            parent_module_name,
                            parent_menu_name,
                        ) = menu_id.parent_id_name.split(".")
                    else:
                        parent_menu_name = menu_id.parent_id_name
                    if (
                        parent_module_name != module.name
                        or parent_menu_name in lst_inserted_menu_name
                    ):
                        lst_inserted_menu_name.append(menu_name)
                        lst_added_menu.append(menu_id)
                for added_menu in lst_added_menu:
                    lst_menu.append(added_menu)
                    lst_menu_to_sort.remove(added_menu)
                    i = -1

            for menu_id in lst_menu:
                action_id = None
                if menu_id.m2o_act_window:
                    # Create action
                    v = {
                        "name": menu_id.m2o_act_window.name,
                        "type": "ir.actions.act_window",
                        "view_mode": view_mode,
                        "view_type": view_type,
                        # 'help': help_str,
                        # 'search_view_id': self.search_view_id.id,
                        "context": {},
                        "m2o_res_model": model_created.id,
                    }
                    if menu_id.m2o_act_window.model_name:
                        v["res_model"] = menu_id.m2o_act_window.model_name
                    else:
                        _logger.warning(
                            "Missing model_name into m2o_act_window"
                            f" '{menu_id.m2o_act_window.name}', force another"
                            f" model name '{model_name}'"
                        )
                        v["res_model"] = model_name

                    lst_action = [
                        (a, "=", b)
                        for a, b in v.items()
                        if a != "m2o_res_model"
                    ]
                    action_id = self.env["ir.actions.act_window"].search(
                        lst_action
                    )
                    if not action_id:
                        action_id = self.env["ir.actions.act_window"].create(v)
                    else:
                        action_id.m2o_res_model = model_created.id
                    if menu_id.m2o_act_window.id_name:
                        ir_model_data_id = self.env["ir.model.data"].search(
                            [
                                ("name", "=", menu_id.m2o_act_window.id_name),
                                ("model", "=", "ir.actions.act_window"),
                                (
                                    "module",
                                    "=",
                                    module.name,
                                ),
                            ]
                        )
                        if ir_model_data_id:
                            ir_model_data_id.res_id = action_id.id
                        else:
                            # Write id name
                            self.env["ir.model.data"].create(
                                {
                                    "name": menu_id.m2o_act_window.id_name,
                                    "model": "ir.actions.act_window",
                                    "module": module.name,
                                    "res_id": action_id.id,
                                    "noupdate": True,
                                    # If it's False, target record (res_id) will be removed while module update
                                }
                            )
                elif not menu_id.ignore_act_window:
                    # Create action
                    v = {
                        "name": f"{model_name_str}_action_view",
                        "res_model": model_name,
                        "type": "ir.actions.act_window",
                        "view_mode": view_mode,
                        "view_type": view_type,
                        # 'help': help_str,
                        # 'search_view_id': self.search_view_id.id,
                        "context": {},
                        "m2o_res_model": model_created.id,
                    }
                    action_id = self.env["ir.actions.act_window"].create(v)

                v = {
                    "name": menu_id.name,
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                }
                if menu_id.ignore_act_window:
                    v["ignore_act_window"] = True
                else:
                    v["action"] = "ir.actions.act_window,%s" % action_id.id

                v["sequence"] = menu_id.sequence

                if menu_id.web_icon:
                    v["web_icon"] = menu_id.web_icon

                if menu_id.parent_id_name:
                    # TODO crash when create empty module and template to read this empty module
                    try:
                        v["parent_id"] = self.env.ref(
                            menu_id.parent_id_name
                        ).id
                    except Exception:
                        _logger.error(
                            f"Cannot find ref {menu_id.parent_id_name} of menu"
                            f" {menu_id.id_name} to associate parent_id."
                        )

                new_menu_id = self.env["ir.ui.menu"].create(v)

                ir_model_data_id = self.env["ir.model.data"].search(
                    [
                        ("name", "=", menu_id.id_name),
                        ("model", "=", "ir.ui.menu"),
                        (
                            "module",
                            "=",
                            module.name,
                        ),
                    ]
                )
                if ir_model_data_id:
                    ir_model_data_id.res_id = new_menu_id.id
                else:
                    v_ir_model_data = {
                        "name": menu_id.id_name,
                        "model": "ir.ui.menu",
                        "module": module.name,
                        "res_id": new_menu_id.id,
                        "noupdate": True,
                    }
                    self.env["ir.model.data"].create(v_ir_model_data)
