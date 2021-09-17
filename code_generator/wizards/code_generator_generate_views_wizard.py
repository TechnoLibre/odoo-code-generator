import time

from collections import defaultdict
from odoo import _, models, fields, api
from odoo.models import MAGIC_COLUMNS
from lxml.builder import E
from lxml import etree as ET
import uuid
import logging

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
    #     result["selected_model_list_view_ids"] = [(6, 0, lst_model_id)]
    #     result["selected_model_form_view_ids"] = [(6, 0, lst_model_id)]
    #     return result

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    enable_generate_all = fields.Boolean(
        string="Enable all feature",
        default=True,
        help="Generate with all feature.",
    )

    disable_generate_access = fields.Boolean(
        help="Disable security access generation.",
    )

    code_generator_view_ids = fields.Many2many(
        comodel_name="code.generator.view",
        string="Code Generator View",
        ondelete="cascade",
    )

    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda s: s.env.user.id,
    )

    name = fields.Char(
        string="Name",
    )

    clear_all_view = fields.Boolean(
        string="Clear views",
        default=True,
        help="Clear all views before execute.",
    )

    clear_all_access = fields.Boolean(
        string="Clear access",
        default=True,
        help="Clear all access/permission before execute.",
    )

    clear_all_menu = fields.Boolean(
        string="Clear menus",
        default=True,
        help="Clear all menus before execute.",
    )

    clear_all_act_window = fields.Boolean(
        string="Clear actions windows",
        default=True,
        help="Clear all actions windows before execute.",
    )

    all_model = fields.Boolean(
        string="All models",
        default=True,
        help="Generate with all existing model, or select manually.",
    )

    selected_model_list_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_list_view_ids_ir_model",
    )

    selected_model_form_view_ids = fields.Many2many(
        comodel_name="ir.model",
        relation="selected_model_form_view_ids_ir_model",
    )

    generated_root_menu = None
    generated_parent_menu = None
    nb_sub_menu = 0

    def clear_all(self):
        if self.clear_all_view and self.code_generator_id.o2m_model_views:
            self.code_generator_id.o2m_model_views.unlink()
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
            lst_view_generated = []
            for code_generator_view_id in self.code_generator_view_ids:
                view_id = self._generate_specific_form_views_models(
                    code_generator_view_id, dct_value_to_create
                )
                lst_view_generated.append(view_id.type)
                # TODO bug attach view to model (o2m_model) when not generate access
                for model_id in self.code_generator_id.o2m_models:
                    self._generate_model_access(model_id)
            self._generate_menu(
                model_id, model_id.m2o_module, lst_view_generated
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
        o2m_models_view_list = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_list_view_ids
        )
        o2m_models_view_form = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_form_view_ids
        )
        lst_model = sorted(
            set(o2m_models_view_list + o2m_models_view_form),
            key=lambda model: model.name,
        )

        for model_id in lst_model:
            lst_view_generated = []

            # Different view
            if model_id in o2m_models_view_list:
                is_whitelist = all(
                    [a.is_show_whitelist_list_view for a in model_id.field_id]
                )
                # model_created_fields_list = list(
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
                model_created_fields_list = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_list_view
                    and (
                        not is_whitelist
                        or (is_whitelist and field.is_show_whitelist_list_view)
                    )
                )
                model_created_fields_list = self._update_model_field_tree_view(
                    model_created_fields_list
                )
                self._generate_list_views_models(
                    model_id,
                    model_created_fields_list,
                    model_id.m2o_module,
                    dct_value_to_create,
                )
                lst_view_generated.append("list")

            if model_id in o2m_models_view_form:
                is_whitelist = all(
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

            # Menu and action_windows
            self._generate_menu(
                model_id, model_id.m2o_module, lst_view_generated
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
        pass

    def _update_model_field_tree_view(self, model_created_fields_list):
        return model_created_fields_list

    def _generate_list_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")

        lst_field_to_remove = ("active", "actif")

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
            lst_field_sorted = self.env["ir.model.fields"].browse(
                new_lst_order_field_id
            )
        else:
            # Use tree view sequence, or generic sequence
            lst_field_sorted = model_created_fields.sorted(
                lambda field: field.code_generator_tree_view_sequence
            )

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
            lst_field.append(E.field(dct_value))
        arch_xml = E.tree(
            {
                # TODO enable this when missing form
                # "editable": "top",
            },
            *lst_field,
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_tree",
        #     "type": "tree",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
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

        lst_field_to_transform_button_box = ("active", "actif")

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
            field_sorted_ids = self.env["ir.model.fields"].browse(
                new_lst_order_field_id
            )
        else:
            field_sorted_ids = sorted(
                model_created_fields,
                key=lambda x: x.code_generator_form_simple_view_sequence,
            )

        lst_button_box = []
        for field_id in field_sorted_ids:
            if field_id.name in lst_field_to_transform_button_box:
                item_field = E.field(
                    {"name": field_id.name, "widget": "boolean_button"}
                )
                item_button = E.button(
                    {
                        "name": "toggle_active",
                        "type": "object",
                        "class": "oe_stat_button",
                        "icon": "fa-archive",
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
                value["widget"] = field_id.force_widget
            elif key in field_id.ttype:
                value["widget"] = "geo_edit_map"
                # value["attrs"] = "{'invisible': [('type', '!=', '"f"{model[len(key):]}')]""}"
            # lst_field.append(value)
            lst_item_sheet.append(E.group({}, E.field(value)))

        arch_xml = E.form(
            {
                "string": "Titre",
            },
            E.sheet({}, *lst_item_sheet),
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_form",
        #     "type": "form",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)
        view_value = self.env["ir.ui.view"].create(
            {
                "name": f"{model_name_str}_form",
                "type": "form",
                "model": model_name,
                "arch": str_arch,
                "m2o_model": model_created.id,
            }
        )

        return view_value

    def _generate_xml_button(self, item, model_id):
        button_attributes = {
            "name": item.action_name,
            "string": item.label,
            "type": "object",
        }
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
        if not items:
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
        item_xml = E.separator(dct_item)
        lst_child.append(item_xml)

        uid = str(uuid.uuid1())
        dct_replace[uid] = item.label
        item_xml = E.div({}, uid)
        return item_xml

    def _generate_xml_object(self, item, model_id, lst_child=[]):
        if item.item_type == "field":
            dct_item = {"name": item.action_name}
            if item.placeholder:
                dct_item["placeholder"] = item.placeholder
            if item.password:
                dct_item["password"] = "True"
            item_xml = E.field(dct_item)
            return item_xml
        elif item.item_type == "button":
            return self._generate_xml_button(item, model_id)
        elif item.item_type == "html":
            lst_html_child = []
            dct_item = {}
            if item.background_type:
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
            item_xml = E.div(dct_item, *lst_html_child)
            return item_xml
        elif item.item_type == "group":
            dct_item = {}
            if item.label:
                dct_item["string"] = item.label
            if item.attrs:
                dct_item["attrs"] = item.attrs
            item_xml = E.group(dct_item, *lst_child)
            return item_xml
        elif item.item_type == "div":
            dct_item = {}
            if item.attrs:
                dct_item["attrs"] = item.attrs
            item_xml = E.div(dct_item, *lst_child)
            return item_xml
        else:
            _logger.warning(f"View item '{item.item_type}' is not supported.")

    def _generate_xml_group_div(self, item, lst_xml, dct_replace, model_id):
        """

        :param item:
        :param lst_xml: list of item to add more in some context
        :param dct_replace: need it to replace html in xml without validation
        :return:
        """
        lst_child = sorted(item.child_id, key=lambda item: item.sequence)
        lst_item_child = []
        if lst_child:
            for item_child_id in lst_child:
                item_child = self._generate_xml_group_div(
                    item_child_id, lst_xml, dct_replace, model_id
                )
                lst_item_child.append(item_child)
            item_xml = self._generate_xml_object(
                item, model_id, lst_child=lst_item_child
            )
        else:
            item_xml = self._generate_xml_object(item, model_id)

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
        dct_item_field = {"name": item.action_name}

        if item.is_required:
            dct_item_field["required"] = "1"
        if item.is_readonly:
            dct_item_field["readonly"] = "1"
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
        lst_item_body = []
        lst_item_title = []
        for view_item in code_generator_view_id.view_item_ids:
            if view_item.section_type == "body":
                lst_item_body.append(view_item)
            elif view_item.section_type == "header":
                lst_item_header.append(view_item)
            elif view_item.section_type == "title":
                lst_item_title.append(view_item)
            else:
                _logger.warning(
                    f"View item '{view_item.section_type}' is not supported."
                )

        lst_item_form = []
        lst_item_form_sheet = []

        if lst_item_header:
            lst_item_header = sorted(
                lst_item_header, key=lambda item: item.sequence
            )
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
            lst_item_title = sorted(
                lst_item_title, key=lambda item: item.sequence
            )
            lst_child = []
            i = 0
            for item_header in lst_item_title:
                if item_header.item_type == "field":
                    item = self._generate_xml_title_field(
                        item_header, lst_child, level=i
                    )
                elif item_header.item_type == "button":
                    _logger.warning(
                        f"Button is not supported in title section."
                    )
                    continue
                else:
                    _logger.warning(
                        f"Item header type '{item_header.item_type}' is not"
                        " supported."
                    )
                    continue
                i += 1
                lst_child.append(item)
            header_xml = E.div({"class": "oe_title"}, *lst_child)
            lst_item_form_sheet.append(header_xml)

        if lst_item_body:
            lst_item_root_body = [a for a in lst_item_body if not a.parent_id]
            lst_item_root_body = sorted(
                lst_item_root_body, key=lambda item: item.sequence
            )
            for item_header in lst_item_root_body:
                if item_header.is_help:
                    item_xml = self._generate_xml_html_help(
                        item_header, lst_item_form_sheet, dct_replace
                    )
                    lst_item_form_sheet.append(item_xml)
                elif item_header.item_type in ("div", "group"):
                    if not item_header.child_id:
                        _logger.warning(
                            f"Item type div or group missing child."
                        )
                        continue
                    item_xml = self._generate_xml_group_div(
                        item_header, lst_item_form_sheet, dct_replace, model_id
                    )
                    lst_item_form_sheet.append(item_xml)
                elif item_header.item_type in ("field",):
                    item_xml = self._generate_xml_object(item_header, model_id)
                    lst_item_form_sheet.append(item_xml)
                else:
                    _logger.warning(
                        f"Unknown type xml {item_header.item_type}"
                    )

        if lst_item_form_sheet:
            if code_generator_view_id.has_body_sheet:
                sheet_xml = E.sheet({}, *lst_item_form_sheet)
                lst_item_form.append(sheet_xml)
            else:
                lst_item_form += lst_item_form_sheet

        if view_type == "form":
            form_xml = E.form({}, *lst_item_form)
        elif view_type == "search":
            form_xml = E.search({}, *lst_item_form)
        elif view_type == "tree":
            form_xml = E.tree({}, *lst_item_form)
        elif view_type == "kanban":
            form_xml = E.kanban({}, *lst_item_form)
        elif view_type == "graph":
            form_xml = E.graph({}, *lst_item_form)
        elif view_type == "pivot":
            form_xml = E.pivot({}, *lst_item_form)
        else:
            _logger.warning(f"Unknown xml view_type {view_type}")
            return

        str_arch = ET.tostring(form_xml, pretty_print=True)
        str_content = str_arch.decode()

        for key, value in dct_replace.items():
            str_content = str_content.replace(key, value)

        view_value = self.env["ir.ui.view"].create(
            {
                "name": code_generator_view_id.view_name,
                "type": view_type,
                "model": model_name,
                "arch": str_content,
                "m2o_model": code_generator_view_id.m2o_model.id,
            }
        )
        # ir_ui_view_value = {
        #     "name": f"{model_name_str}_tree",
        #     "type": "tree",
        #     "model": model_name,
        #     "arch": str_arch,
        #     "m2o_model": model_created.id,
        # }
        # dct_value_to_create["ir.ui.view"].append(ir_ui_view_value)

        if code_generator_view_id.id_name:
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

    def _generate_menu(self, model_created, module, lst_view_generated):
        # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
        # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
        is_generic_menu = not model_created.m2o_module.code_generator_menus_id
        group_id = self.env.ref("base.group_user")
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        module_name = module.name
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
                    "name": _("Models"),
                    "sequence": 1,
                    "parent_id": self.generated_root_menu.id,
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                }
                self.generated_parent_menu = self.env["ir.ui.menu"].create(v)

        help_str = f"""<p class="o_view_nocontent_empty_folder">
        Add a new {model_name_str}
          </p>
          <p>
            Databases whose tables could be imported to Odoo and then be exported into code
          </p>
        """

        # Special case, cannot support search view type in action_view
        try:
            lst_view_generated.remove("search")
        except:
            pass

        view_mode = ",".join(sorted(set(lst_view_generated), reverse=True))
        view_type = (
            "form" if "form" in lst_view_generated else lst_view_generated[0]
        )

        # Create menu
        if module.application and is_generic_menu:
            # Create action
            v = {
                "name": model_name_str.replace("_", " ").title(),
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

            self.nb_sub_menu += 1

            # Compute menu name
            menu_name = model_name_str
            application_name, sub_model_name = model_name.split(
                ".", maxsplit=1
            )
            if sub_model_name and menu_name.lower().startswith(
                application_name.lower()
            ):
                menu_name = sub_model_name.title().replace(".", " ")

            v = {
                "name": menu_name,
                "sequence": self.nb_sub_menu,
                "action": "ir.actions.act_window,%s" % action_id.id,
                # 'group_id': group_id.id,
                "m2o_module": module.id,
            }

            if self.generated_parent_menu:
                v["parent_id"] = self.generated_parent_menu.id

            access_value = self.env["ir.ui.menu"].create(v)
        elif not is_generic_menu:
            cg_menu_ids = model_created.m2o_module.code_generator_menus_id
            # TODO check different case, with act_window, without, multiple menu, single menu
            for menu_id in cg_menu_ids:
                if menu_id.m2o_act_window:
                    # Create action
                    v = {
                        "name": menu_id.m2o_act_window.name,
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
                    if menu_id.m2o_act_window.id_name:
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
                else:
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
                    "name": menu_id.id_name,
                    "action": "ir.actions.act_window,%s" % action_id.id,
                    # 'group_id': group_id.id,
                    "m2o_module": module.id,
                }
                if menu_id.sequence != 10:
                    v["sequence"] = menu_id.sequence

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

                access_value = self.env["ir.ui.menu"].create(v)
