from odoo import models, fields, api

import ast
import os
import shutil
import tempfile
import logging
import uuid
import base64
import glob
from lxml.builder import E
from lxml import etree as ET
from collections import defaultdict
from odoo.tools.misc import mute_logger
import subprocess
import html5print
import xmlformatter
from PIL import Image
import io

import xml.dom.minicompat
from xml.dom import minidom, Node

from code_writer import CodeWriter
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

UNDEFINEDMESSAGE = "Restriction message not yet define."
MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]
MODULE_NAME = "code_generator"
BLANK_LINE = [""]
BREAK_LINE_OFF = "\n"
BREAK_LINE = ["\n"]
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF
XML_VERSION = ['<?xml version="1.0" encoding="utf-8"?>']
XML_ODOO_OPENING_TAG = ["<odoo>"]
XML_HEAD = XML_VERSION + XML_ODOO_OPENING_TAG
XML_ODOO_CLOSING_TAG = ["</odoo>"]
FROM_ODOO_IMPORTS = ["from odoo import _, api, models, fields"]
MODEL_HEAD = FROM_ODOO_IMPORTS + BREAK_LINE
FROM_ODOO_IMPORTS_SUPERUSER = [
    "from odoo import _, api, models, fields, SUPERUSER_ID"
]
MODEL_SUPERUSER_HEAD = FROM_ODOO_IMPORTS_SUPERUSER + BREAK_LINE


class CodeGeneratorWriter(models.Model):
    _name = "code.generator.writer"
    _description = "Code Generator Writer"

    code_generator_ids = fields.Many2many(comodel_name="code.generator.module")

    list_path_file = fields.Char(
        string="List path file", help="Value are separated by ;"
    )

    rootdir = fields.Char(string="Root dir")

    basename = fields.Char(string="Base name")

    class ExtractorView:
        def __init__(self, module, model_model):
            self._module = module
            self.view_ids = module.env["ir.ui.view"].search(
                [("model", "=", model_model)]
            )
            self.code_generator_id = None
            self.model_id = module.env["ir.model"].search(
                [("model", "=", model_model)]
            )
            self.dct_model = defaultdict(dict)
            self.dct_field = defaultdict(dict)
            self.module_attr = defaultdict(dict)
            model_name = model_model.replace(".", "_")
            self.var_model_name = f"model_{model_name}"
            self.var_model = model_model
            if self.view_ids:
                # create temporary module
                name = f"TEMP_{model_name}"
                i = 1
                while module.env["code.generator.module"].search(
                    [("name", "=", name)]
                ):
                    name = f"TEMP_{i}_{model_name}"
                    i += 1
                value = {
                    "name": name,
                    "shortdesc": "None",
                }
                self.code_generator_id = module.env[
                    "code.generator.module"
                ].create(value)
                self._parse_view_ids()
                self._parse_menu()
                self._parse_action_server()

        def _parse_action_server(self):
            # Search comment node associated to action_server
            module = self._module
            if not module.template_module_path_generated_extension:
                return
            relative_path_generated_module = (
                module.template_module_path_generated_extension.replace(
                    "'", ""
                ).replace(", ", "/")
            )
            path_generated_module = os.path.normpath(
                os.path.join(
                    module.path_sync_code,
                    relative_path_generated_module,
                    module.template_module_name,
                    "**",
                    "*.xml",
                )
            )
            lst_xml_file = glob.glob(path_generated_module)
            for xml_file in lst_xml_file:
                my_xml = minidom.parse(xml_file)
                lst_record = my_xml.getElementsByTagName("record")
                for record in lst_record:
                    # detect action_server_backup
                    searched_record = "model", "ir.actions.server"

                    if searched_record in record.attributes.items():
                        last_record = record.previousSibling.previousSibling
                        if last_record.nodeType is Node.COMMENT_NODE:
                            record_id = dict(record.attributes.items()).get(
                                "id"
                            )
                            if not record_id:
                                _logger.warning(
                                    "Missing id when searching"
                                    " ir.actions.server."
                                )
                                continue
                            xml_id = (
                                f"{module.template_module_name}.{record_id}"
                            )
                            result = self._module.env.ref(
                                xml_id, raise_if_not_found=False
                            )
                            if result:
                                result.comment = last_record.data.strip()

        def _parse_menu(self):
            ir_model_data_ids = self._module.env["ir.model.data"].search(
                [
                    ("model", "=", "ir.ui.menu"),
                    ("module", "=", self._module.template_module_name),
                ]
            )
            if not ir_model_data_ids:
                return
            lst_id_menu = [a.res_id for a in ir_model_data_ids]
            menu_ids = self._module.env["ir.ui.menu"].browse(lst_id_menu)
            for menu_id in menu_ids:

                # TODO optimise request ir.model.data, this is duplicated
                menu_action = None
                if menu_id.action:
                    # Create act_window
                    menu_data_id = self._module.env["ir.model.data"].search(
                        [
                            ("model", "=", "ir.actions.act_window"),
                            ("res_id", "=", menu_id.action.id),
                        ]
                    )
                    dct_act_value = {
                        "id_name": menu_data_id.name,
                        "name": menu_id.action.name,
                        "code_generator_id": self.code_generator_id.id,
                    }
                    menu_action = self._module.env[
                        "code.generator.act_window"
                    ].create(dct_act_value)
                # Create menu
                menu_data_id = self._module.env["ir.model.data"].search(
                    [("model", "=", "ir.ui.menu"), ("res_id", "=", menu_id.id)]
                )
                dct_menu_value = {
                    "code_generator_id": self.code_generator_id.id,
                    "id_name": menu_data_id.name,
                }
                if menu_id.sequence != 10:
                    dct_menu_value["sequence"] = menu_id.sequence
                if menu_id.parent_id:
                    menu_data_parent_id = self._module.env[
                        "ir.model.data"
                    ].search(
                        [
                            ("model", "=", "ir.ui.menu"),
                            ("res_id", "=", menu_id.parent_id.id),
                        ]
                    )
                    dct_menu_value[
                        "parent_id_name"
                    ] = menu_data_parent_id.complete_name

                if menu_action:
                    dct_menu_value["m2o_act_window"] = menu_action.id

                self._module.env["code.generator.menu"].create(dct_menu_value)
                # If need to associated
                # menu_id.m2o_module = self._module.id

        def _parse_view_ids(self):
            for view_id in self.view_ids:
                mydoc = minidom.parseString(view_id.arch_base.encode())

                lst_view_item_id = []

                # Search form
                lst_form_xml = mydoc.getElementsByTagName("form")
                if lst_form_xml:
                    sequence_form = 10
                    lst_form_field_xml = mydoc.getElementsByTagName("field")
                    for field_xml in lst_form_field_xml:
                        field_name = dict(field_xml.attributes.items()).get(
                            "name"
                        )
                        if field_name in self.dct_model[view_id.model]:
                            self.dct_model[view_id.model][field_name][
                                "code_generator_form_simple_view_sequence"
                            ] = sequence_form
                        else:
                            self.dct_model[view_id.model][field_name] = {
                                "code_generator_form_simple_view_sequence": sequence_form
                            }
                        sequence_form += 1

                # Search tree
                lst_tree_xml = mydoc.getElementsByTagName("tree")
                if lst_tree_xml:
                    sequence_tree = 10
                    lst_tree_field_xml = mydoc.getElementsByTagName("field")
                    for field_xml in lst_tree_field_xml:
                        field_name = dict(field_xml.attributes.items()).get(
                            "name"
                        )
                        if field_name in self.dct_model[view_id.model]:
                            self.dct_model[view_id.model][field_name][
                                "code_generator_tree_view_sequence"
                            ] = sequence_tree
                        else:
                            self.dct_model[view_id.model][field_name] = {
                                "code_generator_tree_view_sequence": sequence_tree
                            }
                        sequence_tree += 1

                # Search timeline
                lst_timeline_xml = mydoc.getElementsByTagName("timeline")
                if lst_timeline_xml:
                    for timeline_xml in lst_timeline_xml:
                        if "date_start" in timeline_xml.attributes.keys():
                            field_name = (
                                timeline_xml.attributes["date_start"]
                                .childNodes[0]
                                .data
                            )
                            for field_id in self.model_id.field_id:
                                if field_id.name == field_name:
                                    self.dct_field[field_name][
                                        "is_date_start_view"
                                    ] = True
                        if "date_stop" in timeline_xml.attributes.keys():
                            field_name = (
                                timeline_xml.attributes["date_stop"]
                                .childNodes[0]
                                .data
                            )
                            for field_id in self.model_id.field_id:
                                if field_id.name == field_name:
                                    self.dct_field[field_name][
                                        "is_date_end_view"
                                    ] = True

                # Search diagram
                lst_diagram_xml = mydoc.getElementsByTagName("diagram")
                if lst_diagram_xml:
                    nb_iter = 0
                    for diagram_xml in lst_diagram_xml:
                        nb_iter += 1
                        if nb_iter > 1:
                            _logger.warning(
                                "Cannot support multiple diagram in the same"
                                " file."
                            )
                            continue
                        # Search 1 node, 1 arrow and maybe 1 label
                        find_node = False
                        find_arrow = False
                        find_label = False
                        for child_div in diagram_xml.childNodes:
                            if child_div.nodeType is Node.ELEMENT_NODE:
                                dct_att = dict(child_div.attributes.items())
                                if child_div.nodeName == "node":
                                    find_node = True
                                    node_object = dct_att.get("object")
                                    node_xpos = dct_att.get("xpos")
                                    node_ypos = dct_att.get("ypos")
                                    node_shape = dct_att.get("shape")
                                    node_form_view_ref = dct_att.get(
                                        "form_view_ref"
                                    )
                                    if not node_object:
                                        _logger.warning(
                                            "Missing diagram node object for"
                                            f" model {self.var_model}"
                                        )
                                        find_node = False
                                    if not node_xpos:
                                        _logger.warning(
                                            "Missing diagram node xpos for"
                                            f" model {self.var_model}"
                                        )
                                        find_node = False
                                    if not node_ypos:
                                        _logger.warning(
                                            "Missing diagram node ypos for"
                                            f" model {self.var_model}"
                                        )
                                        find_node = False
                                    if not node_shape:
                                        _logger.warning(
                                            "Missing diagram node shape for"
                                            f" model {self.var_model}"
                                        )
                                        find_node = False
                                    if not node_form_view_ref:
                                        _logger.warning(
                                            "Missing diagram node"
                                            " form_view_ref for model"
                                            f" {self.var_model}"
                                        )
                                        find_node = False
                                if child_div.nodeName == "arrow":
                                    find_arrow = True
                                    arrow_object = dct_att.get("object")
                                    arrow_source = dct_att.get("source")
                                    arrow_destination = dct_att.get(
                                        "destination"
                                    )
                                    arrow_label = dct_att.get("label")
                                    arrow_form_view_ref = dct_att.get(
                                        "form_view_ref"
                                    )
                                    if not arrow_object:
                                        _logger.warning(
                                            "Missing diagram arrow object for"
                                            f" model {self.var_model}"
                                        )
                                        find_arrow = False
                                    if not arrow_source:
                                        _logger.warning(
                                            "Missing diagram arrow source for"
                                            f" model {self.var_model}"
                                        )
                                        find_arrow = False
                                    if not arrow_destination:
                                        _logger.warning(
                                            "Missing diagram arrow"
                                            " destination for model"
                                            f" {self.var_model}"
                                        )
                                        find_arrow = False
                                    if not arrow_label:
                                        _logger.warning(
                                            "Missing diagram arrow label for"
                                            f" model {self.var_model}"
                                        )
                                        find_arrow = False
                                    if not arrow_form_view_ref:
                                        _logger.warning(
                                            "Missing diagram arrow"
                                            " form_view_ref for model"
                                            f" {self.var_model}"
                                        )
                                        find_arrow = False
                                if child_div.nodeName == "label":
                                    find_label = True
                                    diagram_label_string = dct_att.get(
                                        "string"
                                    )
                                    if not diagram_label_string:
                                        _logger.warning(
                                            "Missing diagram label string"
                                            f" for model {self.var_model}"
                                        )
                                        find_label = False
                        if find_node and find_arrow:
                            self.model_id.diagram_node_object = node_object
                            self.model_id.diagram_node_xpos_field = node_xpos
                            self.model_id.diagram_node_ypos_field = node_ypos
                            self.model_id.diagram_node_shape_field = node_shape
                            self.model_id.diagram_node_form_view_ref = (
                                node_form_view_ref
                            )
                            self.model_id.diagram_arrow_object = arrow_object
                            self.model_id.diagram_arrow_src_field = (
                                arrow_source
                            )
                            self.model_id.diagram_arrow_dst_field = (
                                arrow_destination
                            )
                            if find_label:
                                self.model_id.diagram_label_string = (
                                    diagram_label_string
                                )

                # Search oe_chatter activity message_ids or message_follower_ids
                lst_div_xml = mydoc.getElementsByTagName("div")
                if lst_div_xml:
                    for div_xml in lst_div_xml:
                        if (
                            "class",
                            "oe_chatter",
                        ) in div_xml.attributes.items():
                            for child_div in div_xml.childNodes:
                                if child_div.nodeType is Node.ELEMENT_NODE:
                                    lst_value = dict(
                                        child_div.attributes.items()
                                    ).values()
                                    if (
                                        "activity_ids" in lst_value
                                        or "message_ids" in lst_value
                                        or "message_follower_ids" in lst_value
                                    ):
                                        # self.model_id.write(
                                        #     {"enable_activity": True}
                                        # )
                                        self.model_id.enable_activity = True

                # Sheet
                lst_sheet_xml = mydoc.getElementsByTagName("sheet")
                has_body_sheet = bool(lst_sheet_xml)
                sheet_xml = lst_sheet_xml[0] if lst_sheet_xml else None
                if len(lst_sheet_xml) > 1:
                    _logger.warning("Cannot support multiple <sheet>.")

                # Search header
                header_xml = None
                no_sequence = 1
                lst_header_xml = mydoc.getElementsByTagName("header")
                if len(lst_header_xml) > 1:
                    _logger.warning("Cannot support multiple header.")
                for header_xml in lst_header_xml:
                    # TODO get inside attributes for header
                    for child_header in header_xml.childNodes:
                        if child_header.nodeType is Node.TEXT_NODE:
                            data = child_header.data.strip()
                            if data:
                                _logger.warning("Not supported.")
                        elif child_header.nodeType is Node.ELEMENT_NODE:
                            self._extract_child_xml(
                                child_header,
                                lst_view_item_id,
                                "header",
                                sequence=no_sequence,
                            )

                # Search title
                no_sequence = 1
                nb_oe_title = 0
                div_title = None
                for div_xml in mydoc.getElementsByTagName("div"):
                    # Find oe_title class
                    # TODO what todo when multiple class? split by ,
                    for key, value in div_xml.attributes.items():
                        if key == "class" and value == "oe_title":
                            div_title = div_xml
                            nb_oe_title += 1
                            if nb_oe_title > 1:
                                _logger.warning(
                                    "Cannot support multiple class oe_title."
                                )
                                continue
                            # TODO support multiple element in title
                            lst_field = div_xml.getElementsByTagName("field")
                            if not lst_field:
                                _logger.warning(
                                    "Not supported title without field, TODO."
                                )
                            elif len(lst_field) > 1:
                                _logger.warning(
                                    "Not supported title without multiple"
                                    " field, TODO."
                                )
                            else:
                                dct_field_attrs = dict(
                                    div_xml.getElementsByTagName("field")[
                                        0
                                    ].attributes.items()
                                )
                                name = dct_field_attrs.get("name")
                                if not name:
                                    _logger.warning(
                                        "Cannot identify field type in title."
                                    )
                                else:
                                    dct_attributes = {
                                        "action_name": name,
                                        "section_type": "title",
                                        "item_type": "field",
                                        "sequence": no_sequence,
                                    }
                                    view_item_id = self._module.env[
                                        "code.generator.view.item"
                                    ].create(dct_attributes)
                                    lst_view_item_id.append(view_item_id.id)
                                    no_sequence += 1

                lst_body_xml = []
                lst_tag_support = list(
                    dict(
                        self._module.env["code.generator.view"]
                        ._fields["view_type"]
                        .selection
                    ).keys()
                )
                lst_content = [
                    b
                    for a in lst_tag_support
                    for b in mydoc.getElementsByTagName(a)
                ]
                if not lst_content:
                    _logger.warning(
                        f"Cannot find a xml type from list: {lst_tag_support}."
                    )
                elif len(lst_content) > 1:
                    _logger.warning(
                        f"Cannot support multiple {lst_tag_support}."
                    )
                else:
                    form_xml = lst_content[0]
                    for child_form in form_xml.childNodes:
                        if child_form.nodeType is Node.TEXT_NODE:
                            data = child_form.data.strip()
                            if data:
                                _logger.warning("Not supported.")
                        elif child_form.nodeType is Node.ELEMENT_NODE:
                            if (
                                child_form == div_title
                                or child_form == header_xml
                                or child_form == sheet_xml
                            ):
                                continue
                            # if has_body_sheet:
                            #     _logger.warning(
                            #         "How can find body xml outside of his"
                            #         " sheet?"
                            #     )
                            # else:
                            #     lst_body_xml.append(child_form)
                            # TODO everything can be in body? check when add oe_chatter
                            lst_body_xml.append(child_form)

                if lst_sheet_xml:
                    # TODO validate this, test with and without <sheet>
                    if type(lst_sheet_xml) is xml.dom.minicompat.NodeList:
                        lst_body_xml = [a for a in lst_sheet_xml[0].childNodes]
                    else:
                        lst_body_xml = [a for a in lst_sheet_xml.childNodes]
                sequence = 1
                lst_node = []
                for body_xml in lst_body_xml:
                    if body_xml.nodeType is Node.TEXT_NODE:
                        data = body_xml.data.strip()
                        if data:
                            _logger.warning(f"Not supported : {data}.")
                    elif body_xml.nodeType is Node.ELEMENT_NODE:
                        status = self._extract_child_xml(
                            body_xml,
                            lst_view_item_id,
                            "body",
                            lst_node=lst_node,
                            sequence=sequence,
                        )
                        if status:
                            lst_node.append(body_xml)
                        else:
                            lst_node = []
                        sequence += 1
                if lst_node:
                    _logger.warning("Missing node in buffer.")

                value = {
                    "code_generator_id": self.code_generator_id.id,
                    "view_type": view_id.type,
                    # "view_name": "view_backup_conf_form",
                    # "m2o_model": model_db_backup.id,
                    "view_item_ids": [(6, 0, lst_view_item_id)],
                    "has_body_sheet": has_body_sheet,
                }

                # ID
                ir_model_data = self._module.env["ir.model.data"].search(
                    [
                        ("model", "=", "ir.ui.view"),
                        ("res_id", "=", view_id.id),
                    ]
                )
                if ir_model_data:
                    first_name = ir_model_data[0].name
                    if len(ir_model_data) > 1:
                        _logger.warning(
                            f"Duplicated view model id {first_name}"
                        )
                    value["id_name"] = first_name
                view_code_generator = self._module.env[
                    "code.generator.view"
                ].create(value)

        def _extract_child_xml(
            self,
            node,
            lst_view_item_id,
            section_type,
            lst_node=[],
            parent=None,
            sequence=1,
        ):
            """

            :param node:
            :param lst_view_item_id:
            :param section_type:
            :param parent:
            :param sequence:
            :return: when True, cumulate the node in lst_node for next run, else None
            """
            # From background_type
            lst_key_html_class = (
                "bg-success",
                "bg-success-full",
                "bg-warning",
                "bg-warning-full",
                "bg-info",
                "bg-info-full",
                "bg-danger",
                "bg-danger-full",
                "bg-light",
                "bg-dark",
            )
            dct_key_keep = {
                "name": "action_name",
                "string": "label",
                "attrs": "attrs",
            }
            dct_attributes = {
                "section_type": section_type,
                "item_type": node.nodeName,
                "sequence": sequence,
            }

            if parent:
                dct_attributes["parent_id"] = parent.id

            if node.nodeName in (
                "group",
                "div",
                "templates",
                "t",
                "ul",
                "li",
                "strong",
                "i",
            ):
                if lst_node:
                    # Check cached of nodes
                    # maybe help node
                    for cached_node in lst_node:
                        # TODO need to check nodeName == "separator" ?
                        for key, value in cached_node.attributes.items():
                            if key == "string" and value == "Help":
                                dct_attributes["is_help"] = True
                            elif key == "colspan" and value != 1:
                                dct_attributes["colspan"] = value
                    dct_attributes["label"] = "\n".join(
                        [a.strip() for a in node.toxml().split("\n")[1:-1]]
                    )
                    dct_attributes["item_type"] = "html"
                else:
                    for key, value in node.attributes.items():
                        if key == "class" and value in lst_key_html_class:
                            # not a real div, it's an html part
                            dct_attributes["item_type"] = "html"
                            dct_attributes["background_type"] = value
                            text_html = ""
                            for child in node.childNodes:
                                # ignore element, only get text
                                if child.nodeType is Node.TEXT_NODE:
                                    data = child.data.strip()
                                    if data:
                                        text_html += data
                                elif child.nodeType is Node.ELEMENT_NODE:
                                    continue
                            dct_attributes["label"] = text_html

            elif node.nodeName == "button":
                dct_key_keep["class"] = "button_type"
                for key, value in node.attributes.items():
                    if key == "icon":
                        dct_attributes["icon"] = value
            elif node.nodeName in ("field", "filter"):
                for key, value in node.attributes.items():
                    if key == "password":
                        dct_attributes["password"] = value
                    if key == "widget":
                        field_name = dict(node.attributes.items()).get("name")
                        # TODO update dict instead of overwrite it
                        self.module_attr[self.var_model][field_name] = {
                            "force_widget": value
                        }
                    if key == "placeholder":
                        dct_attributes["placeholder"] = value
            elif node.nodeName == "separator":
                # Accumulate nodes
                return True
            elif node.nodeName == "templates":
                _logger.warning(f"Node template is not supported, ignore it.")
                return
            else:
                _logger.warning(f"Unknown this case '{node.nodeName}'.")
                return

            # TODO use external function to get attributes items to remove duplicate code, search "node.attributes.items()"
            for key, value in node.attributes.items():
                attributes_name = dct_key_keep.get(key)
                if attributes_name:
                    dct_attributes[attributes_name] = value
            # TODO validate dct_attributes has all needed key with dct_key_keep (except button_type)
            view_item_id = self._module.env["code.generator.view.item"].create(
                dct_attributes
            )
            lst_view_item_id.append(view_item_id.id)
            sequence += 1

            # Child, except HTML
            if dct_attributes["item_type"] != "html":
                child_sequence = 1
                for child in node.childNodes:
                    if child.nodeType is Node.TEXT_NODE:
                        data = child.data.strip()
                        if data:
                            _logger.warning(f"Not supported : {data}.")
                    elif child.nodeType is Node.ELEMENT_NODE:
                        self._extract_child_xml(
                            child,
                            lst_view_item_id,
                            section_type,
                            parent=view_item_id,
                            sequence=child_sequence,
                        )
                        child_sequence += 1

    class ExtractorModule:
        def __init__(self, module, model_model, view_file_sync_model):
            self.is_enabled = False
            self.working_directory = module.path_sync_code
            self.view_file_sync_model = view_file_sync_model
            self.module = module
            self.model = model_model
            self.model_id = module.env["ir.model"].search(
                [("model", "=", model_model)], limit=1
            )
            self.dct_model = view_file_sync_model.dct_model
            self.py_filename = ""
            if not module.template_module_path_generated_extension:
                _logger.warning(
                    f"The variable template_module_path_generated_extension is"
                    f" empty."
                )
                return
            if not self.model_id:
                _logger.warning(f"Cannot found module {model_model}.")
                return

            relative_path_generated_module = (
                module.template_module_path_generated_extension.replace(
                    "'", ""
                ).replace(", ", "/")
            )
            template_directory = os.path.normpath(
                os.path.join(
                    module.path_sync_code,
                    relative_path_generated_module,
                    module.template_module_name,
                )
            )
            manifest_file_path = os.path.normpath(
                os.path.join(
                    template_directory,
                    "__manifest__.py",
                )
            )

            if module.template_module_id and os.path.isfile(
                manifest_file_path
            ):
                with open(manifest_file_path, "r") as source:
                    lst_line = source.readlines()
                    i = 0
                    for line in lst_line:
                        if line.startswith("{"):
                            break
                        i += 1
                str_line = "".join(lst_line[:i]).strip()
                module.template_module_id.header_manifest = str_line
                dct_data = ast.literal_eval("".join(lst_line[i:]).strip())
                external_dep = dct_data.get("external_dependencies")
                if external_dep:
                    if type(external_dep) is dict:
                        for key, lst_value in external_dep.items():
                            if type(lst_value) is list:
                                for value in lst_value:
                                    v = {
                                        "module_id": module.id,
                                        "depend": value,
                                        "application_type": key,
                                        "is_template": True,
                                    }
                                    self.module.env[
                                        "code.generator.module.external.dependency"
                                    ].create(v)
                            else:
                                _logger.warning(
                                    "Unknown value type external_dependencies"
                                    f" in __manifest__ key {key}, value"
                                    f" {value}."
                                )
                    else:
                        _logger.warning(
                            "Unknown external_dependencies in __manifest__"
                            f" {external_dep}"
                        )

            elif not module.template_module_id:
                _logger.warning(
                    "Missing template_module_id in module to extract"
                    " information."
                )
            elif not os.path.isfile(manifest_file_path):
                _logger.warning(
                    "Missing __manifest__.py file in directory"
                    f" '{template_directory}' to extract information."
                )

            path_generated_module = os.path.normpath(
                os.path.join(
                    module.path_sync_code,
                    relative_path_generated_module,
                    module.template_module_name,
                    "**",
                    "*.py",
                )
            )
            lst_py_file = glob.glob(path_generated_module)
            if not lst_py_file:
                return
            for py_file in lst_py_file:
                filename = py_file.split("/")[-1]
                if filename == "__init__.py":
                    continue
                with open(py_file, "r") as source:
                    f_lines = source.read()
                    lst_lines = f_lines.split("\n")
                    f_ast = ast.parse(f_lines)
                    class_model_ast = self.search_class_model(f_ast)
                    if class_model_ast:
                        self.py_filename = filename
                        self.search_field(class_model_ast)
                        # Fill method
                        self.search_import(lst_lines)
                        self.search_method(class_model_ast, lst_lines, module)
            self.is_enabled = True

        def search_class_model(self, f_ast):
            for children in f_ast.body:
                # TODO check bases of class if equal models.Model for better performance
                if type(children) == ast.ClassDef:
                    # Detect good _name
                    for node in children.body:
                        if (
                            type(node) is ast.Assign
                            and node.targets
                            and node.targets[0].id == "_name"
                            and node.value.s == self.model
                        ):
                            return children

        def extract_lambda(self, node):
            args = ", ".join([a.arg for a in node.args.args])
            value = ""
            if type(node.body) is ast.Call:
                # Support -> lambda self: self._default_folder()
                body = node.body.func
                value = f"{body.value.id}.{body.attr}()"
            else:
                _logger.error("Lambda not supported.")
            return f"lambda {args}: {value}"

        def _fill_search_field(self, ast_obj, var_name=""):
            ast_obj_type = type(ast_obj)
            if ast_obj_type is ast.Str:
                result = ast_obj.s
            elif ast_obj_type is ast.Lambda:
                result = self.extract_lambda(ast_obj)
            elif ast_obj_type is ast.NameConstant:
                result = ast_obj.value
            elif ast_obj_type is ast.Num:
                result = ast_obj.n
            elif ast_obj_type is ast.List:
                lst_value = [
                    self._fill_search_field(a, var_name) for a in ast_obj.elts
                ]
                result = lst_value
            elif ast_obj_type is ast.Tuple:
                lst_value = [
                    self._fill_search_field(a, var_name) for a in ast_obj.elts
                ]
                result = tuple(lst_value)
            else:
                # TODO missing ast.Dict?
                result = None
                _logger.error(
                    f"Cannot support keyword of variable {var_name} type"
                    f" {ast_obj_type} in filename {self.py_filename}."
                )
            return result

        def search_field(self, class_model_ast):
            if self.dct_model[self.model]:
                dct_field = self.dct_model[self.model]
            else:
                dct_field = {}
                self.dct_model[self.model] = dct_field
            lst_var_name_check = []

            sequence = -1
            for node in class_model_ast.body:
                sequence += 1
                if (
                    type(node) is ast.Assign
                    and type(node.value) is ast.Call
                    and node.value.func.value.id == "fields"
                ):
                    var_name = node.targets[0].id
                    d = {
                        "type": node.value.func.attr,
                        "code_generator_sequence": sequence,
                    }
                    for keyword in node.value.keywords:
                        value = self._fill_search_field(
                            keyword.value, var_name
                        )
                        # Waste to stock None value
                        if value is not None:
                            d[keyword.arg] = value
                    if (
                        self.view_file_sync_model
                        and self.view_file_sync_model.module_attr
                    ):
                        dct_module_attr = (
                            self.view_file_sync_model.module_attr.get(
                                self.model
                            )
                        )
                        if dct_module_attr:
                            dct_field_module_attr = dct_module_attr.get(
                                var_name
                            )
                            if dct_field_module_attr:
                                for (
                                    attr_key,
                                    attr_value,
                                ) in dct_field_module_attr.items():
                                    d[attr_key] = attr_value

                    if var_name in dct_field:
                        dct_field[var_name].update(d)
                    else:
                        dct_field[var_name] = d
                    lst_var_name_check.append(var_name)
            # Remove item not from this list
            lst_var_name_to_delete = list(
                set(dct_field.keys()).difference(set(lst_var_name_check))
            )
            for var_name_to_delete in lst_var_name_to_delete:
                del dct_field[var_name_to_delete]

        def _extract_decorator(self, decorator_list):
            str_decorator = ""
            for dec in decorator_list:
                if type(dec) is ast.Attribute:
                    v = f"@{dec.value.id}.{dec.attr}"
                elif type(dec) is ast.Call:
                    args = [
                        f'\\"{self._fill_search_field(a)}\\"' for a in dec.args
                    ]
                    str_arg = ", ".join(args)
                    v = f"@{dec.func.value.id}.{dec.func.attr}({str_arg})"
                elif type(dec) is ast.Name:
                    v = f"@{dec.id}"
                else:
                    _logger.warning(
                        f"Decorator type {type(dec)} not supported."
                    )
                    v = None

                if v:
                    if str_decorator:
                        str_decorator += f";{v}"
                    else:
                        str_decorator = v
            return str_decorator

        def _write_exact_argument(self, value):
            str_args = ""
            if type(value) is ast.arg:
                if hasattr(value, "is_vararg") and value.is_vararg:
                    str_args += "*"
                if hasattr(value, "is_kwarg") and value.is_kwarg:
                    str_args += "**"
                str_args += value.arg
                if value.annotation:
                    str_args += f": {value.annotation.id}"
            else:
                v = self._fill_search_field(value)
                if type(v) is str:
                    str_args += f"='{v}'"
                else:
                    str_args += f"={v}"
            return str_args

        def _extract_argument(self, ast_argument):
            dct_args = {}
            # Need to regroup different element in order
            # Create dict with all element
            if ast_argument.args:
                for arg in ast_argument.args:
                    dct_args[f"{arg.lineno}-{arg.col_offset}"] = arg
            if ast_argument.defaults:
                for arg in ast_argument.defaults:
                    dct_args[f"{arg.lineno}-{arg.col_offset}"] = arg
            if ast_argument.kwonlyargs:
                for arg in ast_argument.kwonlyargs:
                    dct_args[f"{arg.lineno}-{arg.col_offset}"] = arg
            if ast_argument.kw_defaults:
                for arg in ast_argument.kw_defaults:
                    dct_args[f"{arg.lineno}-{arg.col_offset}"] = arg
            if ast_argument.vararg:
                arg = ast_argument.vararg
                arg.is_vararg = True
                dct_args[f"{arg.lineno}-{arg.col_offset}"] = arg
            if ast_argument.kwarg:
                arg = ast_argument.kwarg
                arg.is_kwarg = True
                dct_args[f"{arg.lineno}-{arg.col_offset}"] = arg

            # Regroup all extra associated with arg
            str_args = ""
            lst_key_sorted = sorted(dct_args.keys())
            lst_group_arg = []
            last_lst_item = []
            for key in lst_key_sorted:
                value = dct_args[key]
                if type(value) is ast.arg:
                    # new item
                    last_lst_item = [value]
                    lst_group_arg.append(last_lst_item)
                else:
                    last_lst_item.append(value)

            # Recreate string of argument
            for lst_value in lst_group_arg[:-1]:
                for value in lst_value:
                    str_args += self._write_exact_argument(value)
                str_args += ", "
            last_value = lst_group_arg[-1]
            if last_value:
                for value in last_value:
                    str_args += self._write_exact_argument(value)
            return str_args

        def _get_nb_line_multiple_string(
            self, item, lst_line, i_lineno, extra_size=2
        ):
            str_size = len(item.s)
            line_size = len(lst_line[i_lineno - 1].strip())
            if line_size != str_size + extra_size:
                # Try detect multiline string with pending technique like
                # """test1"""
                # """test2"""
                # This will be """test1test2"""
                # or
                # "test1"
                # "test2"
                # This will be "test1test2"
                # So if next line is bigger size then full string, it's the end of multiple string line
                i = 0
                line_size += len(lst_line[i_lineno + i].strip())
                while line_size < str_size + extra_size:
                    i += 1
                i_lineno += i + 1
            return i_lineno

        def _get_recursive_lineno(self, item, set_lineno, lst_line):
            if hasattr(item, "lineno"):
                lineno = getattr(item, "lineno")
                if lineno:
                    i_lineno = item.lineno
                    if type(item) is ast.Str:
                        if "\n" in item.s:
                            # -1 to ignore last \n
                            i_lineno = item.lineno - item.s.count("\n")
                        elif lst_line[i_lineno - 1][-3:] == '"""':
                            i_lineno = self._get_nb_line_multiple_string(
                                item, lst_line, i_lineno, extra_size=6
                            )
                        elif lst_line[i_lineno - 1][-1] == '"':
                            i_lineno = self._get_nb_line_multiple_string(
                                item, lst_line, i_lineno
                            )
                    set_lineno.add(i_lineno)

            # Do recursive search, search last line of code
            lst_attr = [
                "body",
                "finalbody",
                "orelse",
                "handlers",
                "test",
                "right",
                "left",
                "value",
                "exc",
                "ctx",
                "func",
                "args",
                "elts",
            ]
            for attr in lst_attr:
                if not hasattr(item, attr):
                    continue
                lst_attr_item = getattr(item, attr)
                if not lst_attr_item:
                    continue
                if type(lst_attr_item) is list:
                    for attr_item in lst_attr_item:
                        if attr_item:
                            self._get_recursive_lineno(
                                attr_item, set_lineno, lst_line
                            )
                elif type(lst_attr_item) in (
                    ast.Compare,
                    ast.Call,
                    ast.Str,
                    ast.Attribute,
                    ast.JoinedStr,
                    ast.BinOp,
                    ast.NameConstant,
                    ast.Name,
                    ast.arguments,
                    ast.Load,
                    ast.List,
                    ast.IfExp,
                    ast.Subscript,
                    ast.UnaryOp,
                    ast.BoolOp,
                    ast.Dict,
                    ast.Tuple,
                    bool,
                ):
                    # Check type, but in fact, can accept all type.
                    # This check is only to understand what style of code we read
                    self._get_recursive_lineno(
                        lst_attr_item, set_lineno, lst_line
                    )
                else:
                    _logger.warning(
                        f"From get recursive {attr} unknown type"
                        f" {type(lst_attr_item)}."
                    )

        def _get_min_max_no_line(self, node, lst_line):
            # hint node.name == ""
            set_lineno = set()
            lst_body = []
            if len(node.body) > 1:
                lst_body.append(node.body[0])
                lst_body.append(node.body[-1])
            else:
                lst_body.append(node.body[0])
            for body in lst_body:
                self._get_recursive_lineno(body, set_lineno, lst_line)
            return min(set_lineno), max(set_lineno)

        def search_import(self, lst_line):
            # get all line until meet "class "
            i = 0
            for line in lst_line:
                if line.startswith("class "):
                    break
                i += 1
            else:
                _logger.warning(
                    "Don't know what to do when missing class in python"
                    " file..."
                )

            str_code = "\n".join(lst_line[:i])
            str_code = str_code.strip()
            if "'''" in str_code:
                str_code = str_code.replace("'''", "\\'''")
            if "\\n" in str_code:
                str_code = str_code.replace("\\n", "\\\\n")
            d = {
                "m2o_model": self.model_id.id,
                "m2o_module": self.module.id,
                "code": str_code,
                "name": "header",
                "is_templated": True,
            }
            if not self.module.env["code.generator.model.code.import"].search(
                [
                    ("m2o_model", "=", self.model_id.id),
                    ("m2o_module", "=", self.module.id),
                    ("code", "=", str_code),
                ],
                limit=1,
            ):
                self.module.env["code.generator.model.code.import"].create(d)

        def search_method(self, class_model_ast, lst_line, module):
            sequence = -1
            lst_body = [a for a in class_model_ast.body]
            for i in range(len(lst_body)):
                node = lst_body[i]
                if i + 1 < len(lst_body):
                    next_node = lst_body[i + 1]
                else:
                    next_node = None
                if type(node) is ast.Assign:
                    if node.targets:
                        if node.targets[0].id == "_description":
                            value = self._fill_search_field(node.value)
                            self.model_id.description = value
                        elif node.targets[0].id == "_inherit":
                            value = self._fill_search_field(node.value)
                            if type(value) is list:
                                model_id = module.env["ir.model"].search(
                                    [("model", "in", value)]
                                )
                            else:
                                model_id = module.env["ir.model"].search(
                                    [("model", "=", value)]
                                )
                            if not model_id:
                                _logger.warning(
                                    f"Cannot identify model {value}."
                                )
                            else:
                                self.model_id.add_model_inherit(model_id)
                        elif node.targets[0].id == "_sql_constraints":
                            lst_value = self._fill_search_field(node.value)
                            constraint_ids = module.env[
                                "ir.model.constraint"
                            ].search(
                                [("module", "=", module.template_module_id.id)]
                            )
                            model_name = self.model_id.model.replace(".", "_")
                            for value in lst_value:
                                name = value[0]
                                db_name = f"{model_name}_{name}"
                                definition = value[1]
                                message = value[2]
                                _logger.warning(
                                    "Ignore next error about ALTER TABLE DROP"
                                    " CONSTRAINT."
                                )
                                constraint_id = constraint_ids.search(
                                    [("name", "=", db_name)]
                                )
                                if constraint_id:
                                    constraint_id.definition = definition
                                    constraint_id.message = message
                elif type(node) is ast.FunctionDef:
                    sequence += 1
                    d = {
                        "m2o_model": self.model_id.id,
                        "m2o_module": self.module.id,
                        "name": node.name,
                        "sequence": sequence,
                        "is_templated": True,
                    }
                    if node.args:
                        d["param"] = self._extract_argument(node.args)
                    if node.returns:
                        d["returns"] = node.returns.id
                    if node.decorator_list:
                        str_decorator = self._extract_decorator(
                            node.decorator_list
                        )
                        d["decorator"] = str_decorator
                    no_line_min, no_line_max = self._get_min_max_no_line(
                        node, lst_line
                    )
                    # Ignore this no_line_max, bug some times.
                    # no_line_min = min([a.lineno for a in node.body])
                    if next_node:
                        no_line_max = next_node.lineno - 1
                    else:
                        # TODO this will bug with multiple class
                        no_line_max = len(lst_line)
                    codes = ""
                    for line in lst_line[no_line_min - 1 : no_line_max]:
                        if line.startswith(" " * 8):
                            str_line = line[8:]
                        else:
                            str_line = line
                        codes += f"{str_line}\n"
                    # codes = "\n".join(lst_line[no_line_min - 1:no_line_max])
                    if "'''" in codes:
                        codes = codes.replace("'''", "\\'''")
                    if "\\n" in codes:
                        codes = codes.replace("\\n", "\\\\n")
                    d["code"] = codes.strip()
                    self.module.env["code.generator.model.code"].create(d)

    @staticmethod
    def _fmt_underscores(word):
        return word.lower().replace(".", "_")

    @staticmethod
    def _fmt_camel(word):
        return word.replace(".", "_").title().replace("_", "")

    @staticmethod
    def _fmt_title(word):
        return word.replace(".", " ").title()

    @staticmethod
    def _get_l_map(fn, collection):
        """
        Util function to get a list of a map operation
        :param fn:
        :param collection:
        :return:
        """

        return list(map(fn, collection))

    def _get_class_name(self, model):
        """
        Util function to get a model class name representation from a model name (code.generator -> CodeGenerator)
        :param model:
        :return:
        """

        result = []
        bypoint = model.split(".")
        for byp in bypoint:
            result += byp.split("_")
        return "".join(self._get_l_map(lambda e: e.capitalize(), result))

    @staticmethod
    def _lower_replace(string, replacee=" ", replacer="_"):
        """
        Util function to replace and get the lower content of a string
        :param string:
        :return:
        """

        v = (
            str(string)
            .lower()
            .replace(replacee, replacer)
            .replace("-", "_")
            .replace(".", "_")
            .replace("'", "_")
            .replace("`", "_")
            .replace("^", "_")
        )
        new_v = v.strip("_")

        while new_v.count("__"):
            new_v = new_v.replace("__", "_")
        return new_v

    def _get_model_model(self, model_model, replacee="."):
        """
        Util function to get a model res_id-like representation (code.generator -> code_generator)
        :param model_model:
        :param replacee:
        :return:
        """
        return self._lower_replace(model_model, replacee=replacee)

    @staticmethod
    def _get_python_class_4inherit(model):
        """
        Util function to get the Python Classes for inheritance
        :param model:
        :return:
        """

        class_4inherit = (
            "models.TransientModel"
            if model.transient
            else (
                "models.AbstractModel" if model._abstract else "models.Model"
            )
        )
        if model.m2o_inherit_py_class.name:
            class_4inherit += ", %s" % model.m2o_inherit_py_class.name

        return class_4inherit

    def _get_odoo_ttype_class(self, ttype):
        """
        Util function to get a field class name from a field type (char -> Char, many2one -> Many2one)
        :param ttype:
        :return:
        """

        return f"fields.{self._get_class_name(ttype)}"

    @staticmethod
    def _get_starting_spaces(compute_line):
        """
        Util function to count the starting spaces of a string
        :param compute_line:
        :return:
        """

        space_counter = 0
        for character in compute_line:
            if character.isspace():
                space_counter += 1

            else:
                break

        return space_counter

    @staticmethod
    def _set_limit_4xmlid(xmlid):
        """
        Util function to truncate (to 64 characters) an xml_id
        :param xmlid:
        :return:
        """

        # if 64 - len(xmlid) < 0:
        #     new_xml_id = "%s..." % xmlid[: 61 - len(xmlid)]
        #     _logger.warning(
        #         f"Slice xml_id {xmlid} to {new_xml_id} because length is upper"
        #         " than 63."
        #     )
        # else:
        #     new_xml_id = xmlid
        # return new_xml_id
        return xmlid

    @staticmethod
    def _prepare_compute_constrained_fields(l_fields):
        """

        :param l_fields:
        :return:
        """

        counter = 1
        prepared = ""
        for field in l_fields:
            prepared += "'%s'%s" % (
                field,
                ", " if counter < len(l_fields) else "",
            )
            counter += 1

        return prepared

    def _get_model_constrains(self, cw, model, module):
        """
        Function to obtain the model constrains
        :param model:
        :return:
        """

        if model.o2m_server_constrains:

            cw.emit()

            for sconstrain in model.o2m_server_constrains:
                l_constrained = self._get_l_map(
                    lambda e: e.strip(), sconstrain.constrained.split(",")
                )

                cw.emit(
                    f"@api.constrains({self._prepare_compute_constrained_fields(l_constrained)})"
                )
                cw.emit(f"def _check_{'_'.join(l_constrained)}(self):")

                l_code = sconstrain.txt_code.split("\n")
                with cw.indent():
                    for line in l_code:
                        cw.emit(line.rstrip())
                # starting_spaces = 2
                # for line in l_code:
                #     if self._get_starting_spaces(line) == 2:
                #         starting_spaces += 1
                #     l_model_constrains.append('%s%s' % (TAB4 * starting_spaces, line.strip()))
                #     starting_spaces = 2

                cw.emit()

            cw.emit()

        constraints_id = None
        if model.o2m_constraints:
            # TODO how to use this way? binding model not working
            constraints_id = model.o2m_constraints
        elif module.o2m_model_constraints:
            constraints_id = module.o2m_model_constraints

        if constraints_id:
            lst_constraint = []
            for constraint in constraints_id:
                constraint_name = constraint.name.replace(
                    "%s_" % self._get_model_model(model.model), ""
                )
                constraint_definition = constraint.definition
                constraint_message = (
                    constraint.message
                    if constraint.message
                    else UNDEFINEDMESSAGE
                )

                lst_constraint.append(
                    f"('{constraint_name}', '{constraint_definition}',"
                    f" '{constraint_message}')"
                )

            cw.emit()
            cw.emit_list(
                lst_constraint, ("[", "]"), before="_sql_constraints = "
            )
            cw.emit()

    def _set_static_description_file(self, module, application_icon):
        """
        Function to set the static descriptions files
        :param module:
        :param application_icon:
        :return:
        """

        static_description_icon_path = os.path.join(
            self.code_generator_data.static_description_path, "icon.png"
        )
        static_description_icon_code_generator_path = os.path.join(
            self.code_generator_data.static_description_path,
            "code_generator_icon.png",
        )
        # TODO hack to force icon or True
        if module.icon_child_image or module.icon_real_image:
            if module.icon_real_image:
                self.code_generator_data.write_file_binary(
                    static_description_icon_path,
                    base64.b64decode(module.icon_real_image),
                )
            if module.icon_child_image:
                self.code_generator_data.write_file_binary(
                    static_description_icon_code_generator_path,
                    base64.b64decode(module.icon_child_image),
                )
        else:
            # elif module.icon_image:

            # TODO use this when fix loading picture, now temporary disabled and force use icon from menu
            # self.code_generator_data.write_file_binary(static_description_icon_path,
            # base64.b64decode(module.icon_image))
            # TODO temp solution with icon from menu
            if module.icon and os.path.isfile(module.icon):
                with open(module.icon, "rb") as file:
                    content = file.read()
            else:
                if application_icon:
                    icon_path = application_icon[
                        application_icon.find(",") + 1 :
                    ]
                    # icon_path = application_icon.replace(",", "/")
                else:
                    icon_path = "static/description/icon_new_application.png"
                icon_path = os.path.normpath(
                    os.path.join(os.path.dirname(__file__), "..", icon_path)
                )
                with open(icon_path, "rb") as file:
                    content = file.read()
            if (
                module.template_module_id
                and module.template_module_id.icon_image
            ):
                # It's a template generator
                minimal_size_width = 350
                # Add logo in small corner
                logo = Image.open(
                    io.BytesIO(
                        base64.b64decode(module.template_module_id.icon_image)
                    )
                )
                icon = Image.open(icon_path)
                # Change original size for better quality
                if logo.width < minimal_size_width:
                    new_h = int(logo.height / logo.width * minimal_size_width)
                    new_w = minimal_size_width
                    logo = logo.resize((new_w, new_h), Image.ANTIALIAS)
                ratio = 0.3
                w = int(logo.width * ratio)
                if icon.width != icon.height:
                    h = int(logo.height / logo.width * w)
                else:
                    h = w
                size = w, h
                icon.thumbnail(size, Image.ANTIALIAS)
                x = logo.width - w
                logo.paste(icon, (x, 0))
                img_byte_arr = io.BytesIO()
                logo.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                # image = base64.b64decode(module.template_module_id.icon_image)
                self.code_generator_data.write_file_binary(
                    static_description_icon_path, img_byte_arr
                )
                module.icon_real_image = base64.b64encode(img_byte_arr)
                code_generator_image = base64.b64decode(
                    module.template_module_id.icon_image
                )
                module.icon_child_image = module.template_module_id.icon_image
                self.code_generator_data.write_file_binary(
                    static_description_icon_code_generator_path,
                    code_generator_image,
                )
            else:
                self.code_generator_data.write_file_binary(
                    static_description_icon_path, content
                )
                module.icon_real_image = base64.b64encode(content)
        # else:
        #     static_description_icon_path = ""

        return static_description_icon_path

    @staticmethod
    def _get_from_rec_name(record, model):
        """
        Util function to handle the _rec_name / rec_name access
        :param record:
        :param model:
        :return:
        """

        return (
            getattr(record, model._rec_name)
            if getattr(record, model._rec_name)
            else getattr(record, model.rec_name)
        )

    def set_module_init_file_extra(self, module):
        pass

    def set_module_translator(self, module_name, module_path):
        module_id = self.env["ir.module.module"].search(
            [("name", "=", module_name), ("state", "=", "installed")]
        )
        if not module_id:
            return

        i18n_path = os.path.join(module_path, "i18n")
        data = CodeGeneratorData(module_id, module_path)
        data.check_mkdir_and_create(i18n_path, is_file=False)

        # Create pot
        export = self.env["base.language.export"].create(
            {"format": "po", "modules": [(6, 0, [module_id.id])]}
        )

        export.act_getfile()
        po_file = export.data
        data = base64.b64decode(po_file).decode("utf-8")
        translation_file = os.path.join(i18n_path, f"{module_name}.pot")

        with open(translation_file, "w") as file:
            file.write(data)

        # Create po
        # TODO get this info from configuration/module
        # lst_lang = [
        #     ("fr_CA", "fr_CA"),
        #     ("fr_FR", "fr"),
        #     ("en_US", "en"),
        #     ("en_CA", "en_CA"),
        # ]
        lst_lang = [("fr_CA", "fr_CA")]
        for lang_local, lang_ISO in lst_lang:
            translation_file = os.path.join(i18n_path, f"{lang_ISO}.po")

            if not self.env["ir.translation"].search(
                [("lang", "=", lang_local)]
            ):
                with mute_logger("odoo.addons.base.models.ir_translation"):
                    self.env["base.language.install"].create(
                        {"lang": lang_local, "overwrite": True}
                    ).lang_install()
                self.env["base.update.translations"].create(
                    {"lang": lang_local}
                ).act_update()

            # Load existing translations
            # translations = self.env["ir.translation"].search([
            #     ('lang', '=', lang),
            #     ('module', '=', module_name)
            # ])

            export = self.env["base.language.export"].create(
                {
                    "lang": lang_local,
                    "format": "po",
                    "modules": [(6, 0, [module_id.id])],
                }
            )
            export.act_getfile()
            po_file = export.data
            data = base64.b64decode(po_file).decode("utf-8").strip() + "\n"

            # Special replace for lang fr_CA
            if lang_ISO in ["fr_CA", "fr", "en", "en_CA"]:
                data = data.replace(
                    '"Plural-Forms: \\n"',
                    '"Plural-Forms: nplurals=2; plural=(n > 1);\\n"',
                )

            with open(translation_file, "w") as file:
                file.write(data)

    def copy_missing_file(
        self, module_name, module_path, template_dir, lst_file_extra=[]
    ):
        """
        This function will create and copy file into template module.
        :param module_name:
        :param module_path:
        :param template_dir:
        :return:
        """
        # TODO bad conception, this method not suppose to be here, move this before generate code
        module_id = self.env["ir.module.module"].search(
            [("name", "=", module_name), ("state", "=", "installed")]
        )
        if not module_id:
            return

        template_copied_dir = os.path.join(template_dir, "not_supported_files")

        # Copy i18n files
        i18n_po_path = os.path.join(module_path, "i18n", "*.po")
        i18n_pot_path = os.path.join(module_path, "i18n", "*.pot")
        target_i18n_path = os.path.join(template_copied_dir, "i18n")
        lst_file = glob.glob(i18n_po_path) + glob.glob(i18n_pot_path)
        if lst_file:
            CodeGeneratorData.os_make_dirs(target_i18n_path)
            for file_name in lst_file:
                shutil.copy(file_name, target_i18n_path)

        # Copy readme file
        readme_file_path = os.path.join(module_path, "README.rst")
        target_readme_file_path = os.path.join(template_copied_dir)
        shutil.copy(readme_file_path, target_readme_file_path)

        # Copy readme dir
        readme_dir_path = os.path.join(module_path, "readme")
        target_readme_dir_path = os.path.join(template_copied_dir, "readme")
        shutil.copytree(readme_dir_path, target_readme_dir_path)

        # Copy tests dir
        tests_dir_path = os.path.join(module_path, "tests")
        target_tests_dir_path = os.path.join(template_copied_dir, "tests")
        shutil.copytree(tests_dir_path, target_tests_dir_path)

        for file_extra in lst_file_extra:
            # Special if exist, mail_message_subtype.xml
            mail_data_xml_path = os.path.join(module_path, file_extra)
            target_mail_data_xml_path = os.path.join(
                template_copied_dir, file_extra
            )
            if os.path.isfile(mail_data_xml_path):
                CodeGeneratorData.check_mkdir_and_create(
                    target_mail_data_xml_path
                )
                shutil.copy(mail_data_xml_path, target_mail_data_xml_path)

    def _set_manifest_file(self, module):
        """
        Function to set the module manifest file
        :param module:
        :return:
        """

        lang = "en_US"

        cw = CodeWriter()

        has_header = False
        if module.header_manifest:
            lst_header = module.header_manifest.split("\n")
            for line in lst_header:
                s_line = line.strip()
                if s_line:
                    cw.emit(s_line)
                    has_header = True
        if has_header:
            cw.emit()

        with cw.block(delim=("{", "}")):
            cw.emit(f"'name': '{module.shortdesc}',")

            if module.category_id:
                cw.emit(
                    "'category':"
                    f" '{module.category_id.with_context(lang=lang).name}',"
                )

            if module.summary and module.summary != "false":
                cw.emit(f"'summary': '{module.summary}',")

            if module.description:
                description = module.description.strip()
                lst_description = description.split("\n")
                if len(lst_description) == 1:
                    cw.emit(f"'description': '{description}',")
                else:
                    cw.emit("'description': '''")
                    for desc in lst_description:
                        cw.emit_raw(desc)
                    cw.emit("''',")

            if module.installed_version:
                cw.emit(f"'version': '{module.installed_version}',")

            if module.author:
                author = module.author.strip()
                lst_author = author.split(",")
                if len(lst_author) == 1:
                    cw.emit(f"'author': '{author}',")
                else:
                    cw.emit(f"'author': (")
                    with cw.indent():
                        for auth in lst_author[:-1]:
                            s_auth = auth.strip()
                            cw.emit(f"'{s_auth}, '")
                    cw.emit(f"'{lst_author[-1].strip()}'),")

            if module.contributors:
                cw.emit(f"'contributors': '{module.contributors}',")

            # if module.maintener:
            #     cw.emit(f"'maintainers': '{module.maintener}',")

            if module.license != "LGPL-3":
                cw.emit(f"'license': '{module.license}',")

            if module.sequence != 100:
                cw.emit(f"'sequence': {module.sequence},")

            if module.website:
                cw.emit(f"'website': '{module.website}',")

            if module.auto_install:
                cw.emit(f"'auto_install': True,")

            if module.demo:
                cw.emit(f"'demo': True,")

            if module.application:
                cw.emit(f"'application': True,")

            if module.dependencies_id:
                lst_depend = module.dependencies_id.mapped(
                    lambda did: f"'{did.depend_id.name}'"
                )
                cw.emit_list(
                    lst_depend, ("[", "]"), before="'depends': ", after=","
                )

            if module.external_dependencies_id and [
                a for a in module.external_dependencies_id if not a.is_template
            ]:
                with cw.block(
                    before="'external_dependencies':",
                    delim=("{", "}"),
                    after=",",
                ):
                    dct_depend = defaultdict(list)
                    for depend in module.external_dependencies_id:
                        if depend.is_template:
                            continue
                        dct_depend[depend.application_type].append(
                            f"'{depend.depend}'"
                        )
                    for application_type, lst_value in dct_depend.items():
                        cw.emit_list(
                            lst_value,
                            ("[", "]"),
                            before=f"'{application_type}': ",
                            after=",",
                        )

            lst_data = self._get_l_map(
                lambda dfile: f"'{dfile}'",
                self.code_generator_data.lst_manifest_data_files,
            )
            if lst_data:
                cw.emit_list(
                    lst_data, ("[", "]"), before="'data': ", after=","
                )

            cw.emit(f"'installable': True,")

            self.set_manifest_file_extra(cw, module)

        manifest_file_path = "__manifest__.py"
        self.code_generator_data.write_file_str(
            manifest_file_path, cw.render()
        )

    def set_manifest_file_extra(self, cw, module):
        pass

    def _get_id_view_model_data(self, record, model=None, is_internal=False):
        """
        Function to obtain the model data from a record
        :param record:
        :param is_internal: if False, add module name for external reference
        :return:
        """

        # special trick for some record
        xml_id = getattr(record, "xml_id")
        if xml_id:
            if is_internal:
                return xml_id.split(".")[1]
            return xml_id

        if model:
            record_model = model
        else:
            record_model = record.model

        ir_model_data = self.env["ir.model.data"].search(
            [
                ("model", "=", record_model),
                ("res_id", "=", record.id),
            ]
        )
        if not ir_model_data:
            return

        if is_internal:
            return ir_model_data[0].name
        return f"{ir_model_data[0].module}.{ir_model_data[0].name}"

    def _get_ir_model_data(self, record, give_a_default=False, module_name=""):
        """
        Function to obtain the model data from a record
        :param record:
        :param give_a_default:
        :param module_name:
        :return:
        """

        ir_model_data = self.env["ir.model.data"].search(
            [
                # TODO: Opción por valorar
                # ('module', '!=', '__export__'),
                ("model", "=", record._name),
                ("res_id", "=", record.id),
            ]
        )

        if ir_model_data:
            if module_name and module_name == ir_model_data[0].module:
                result = ir_model_data[0].name
            else:
                result = f"{ir_model_data[0].module}.{ir_model_data[0].name}"
        elif give_a_default:
            if record._rec_name:
                rec_name_v = getattr(record, record._rec_name)
                if not rec_name_v:
                    rec_name_v = uuid.uuid1().int
                second = self._lower_replace(rec_name_v)
            else:
                second = uuid.uuid1().int
            result = self._set_limit_4xmlid(
                f"{self._get_model_model(record._name)}_{second}"
            )
            # Check if name already exist
            model_data_exist = self.env["ir.model.data"].search(
                [("name", "=", result)]
            )
            new_result = result
            i = 0
            while model_data_exist:
                i += 1
                new_result = f"{result}_{i}"
                model_data_exist = self.env["ir.model.data"].search(
                    [("name", "=", new_result)]
                )

            self.env["ir.model.data"].create(
                {
                    "name": new_result,
                    "model": record._name,
                    "module": module_name,
                    "res_id": record.id,
                    "noupdate": True,  # If it's False, target record (res_id) will be removed while module update
                }
            )
            result = new_result
        else:
            result = False

        return result

    def _get_group_data_name(self, group):
        """
        Function to obtain the res_id-like group name (Code Generator / Manager -> code_generator_manager)
        :param group:
        :return:
        """

        return (
            self._get_ir_model_data(group)
            if self._get_ir_model_data(group)
            else self._lower_replace(group.name.replace(" /", ""))
        )

    def _get_model_data_name(self, model):
        """
        Function to obtain the res_id-like model name (code.generator.module -> code_generator_module)
        :param model:
        :return:
        """

        return (
            self._get_ir_model_data(model)
            if self._get_ir_model_data(model)
            else "model_%s" % self._get_model_model(model.model)
        )

    def _get_view_data_name(self, view):
        """
        Function to obtain the res_id-like view name
        :param view:
        :return:
        """

        return (
            self._get_ir_model_data(view)
            if self._get_ir_model_data(view)
            else "%s_%sview" % (self._get_model_model(view.model), view.type)
        )

    def _get_action_data_name(
        self, action, server=False, creating=False, module=None
    ):
        """
        Function to obtain the res_id-like action name
        :param action:
        :param server:
        :param creating:
        :return:
        """

        if not creating and self._get_ir_model_data(action):
            action_name = self._get_ir_model_data(action)
            if not module or "." not in action_name:
                return action_name
            lst_action = action_name.split(".")
            if module.name == lst_action[0]:
                # remove internal name
                return lst_action[1]
            # link is external
            return action_name

        else:
            model = (
                getattr(action, "res_model")
                if not server
                else getattr(action, "model_id").model
            )
            model_model = self._get_model_model(model)
            action_type = "action_window" if not server else "server_action"

            new_action_name = action.name
            # TODO No need to support limit of 64, why this code?
            # new_action_name = self._set_limit_4xmlid(
            #     "%s" % action.name[: 64 - len(model_model) - len(action_type)]
            # )

            result_name = f"{model_model}_{self._lower_replace(new_action_name)}_{action_type}"

            # if new_action_name != action.name:
            #     _logger.warning(
            #         f"Slice action name {action.name} to"
            #         f" {new_action_name} because length is upper than 63."
            #         f" Result: {result_name}."
            #     )

            return result_name

    def _get_action_act_url_name(self, action):
        """
        Function to obtain the res_id-like action name
        :param action:
        :return:
        """
        return f"action_{self._lower_replace(action.name)}"

    def _get_menu_data_name(self, menu):
        """
        Function to obtain the res_id-like menu name
        :param menu:
        :return:
        """

        return (
            self._get_ir_model_data(menu)
            if self._get_ir_model_data(menu)
            else self._lower_replace(menu.name)
        )

    def _set_model_xmldata_file(self, module, model, model_model):
        """
        Function to set the module data file
        :param module:
        :param model:
        :param model_model:
        :return:
        """

        expression_export_data = model.expression_export_data
        search = (
            []
            if not expression_export_data
            else [ast.literal_eval(expression_export_data)]
        )
        # Search with active_test to support when active is False
        nomenclador_data = (
            self.env[model.model]
            .sudo()
            .with_context(active_test=False)
            .search(search)
        )
        if not nomenclador_data:
            return

        lst_data_xml = []
        lst_id = []
        lst_depend = []
        lst_field_id_blacklist = [
            a.m2o_fields.id
            for a in model.m2o_module.o2m_nomenclator_blacklist_fields
        ]
        lst_field_id_whitelist = [
            a.m2o_fields.id
            for a in model.m2o_module.o2m_nomenclator_whitelist_fields
        ]
        for record in nomenclador_data:

            f2exports = model.field_id.filtered(
                lambda field: field.name not in MAGIC_FIELDS
            )
            lst_field = []
            for rfield in f2exports:
                # whitelist check
                if (
                    lst_field_id_whitelist
                    and rfield.id not in lst_field_id_whitelist
                ):
                    continue
                # blacklist check
                if rfield.id in lst_field_id_blacklist:
                    continue
                record_value = getattr(record, rfield.name)
                if record_value or (
                    not record_value
                    and rfield.ttype == "boolean"
                    and rfield.default == "True"
                ):
                    delete_node = False
                    if rfield.ttype == "many2one":
                        ref = self._get_ir_model_data(
                            record_value,
                            give_a_default=True,
                            module_name=module.name,
                        )
                        if not ref:
                            # This will cause an error at installation
                            _logger.error(
                                "Cannot find reference for field"
                                f" {rfield.name} model {model_model}"
                            )
                            continue
                        child = E.field({"name": rfield.name, "ref": ref})

                        if "." not in ref:
                            lst_depend.append(ref)

                    elif rfield.ttype == "one2many":
                        # TODO do we need to export one2many relation data, it's better to export many2one
                        # TODO maybe check if many2one is exported or export this one
                        continue
                        field_eval = ", ".join(
                            record_value.mapped(
                                lambda rvalue: "(4, ref('%s'))"
                                % self._get_ir_model_data(
                                    rvalue, give_a_default=True
                                )
                            )
                        )
                        child = E.field(
                            {"name": rfield.name, "eval": f"[{field_eval}]"}
                        )

                    elif rfield.ttype == "many2many":
                        # TODO add dependencies id in lst_depend
                        field_eval = ", ".join(
                            record_value.mapped(
                                lambda rvalue: "ref(%s)"
                                % self._get_ir_model_data(
                                    rvalue, give_a_default=True
                                )
                            )
                        )
                        child = E.field(
                            {
                                "name": rfield.name,
                                "eval": f"[(6,0, [{field_eval}])]",
                            }
                        )

                    elif rfield.ttype == "binary":
                        # Transform binary in string and remove b''
                        child = E.field(
                            {"name": rfield.name},
                            str(record_value)[2:-1],
                        )
                    elif rfield.ttype == "boolean":
                        # Don't show boolean if same value of default
                        if str(record_value) != rfield.default:
                            child = E.field(
                                {"name": rfield.name},
                                str(record_value),
                            )
                        else:
                            delete_node = True
                    elif rfield.related == "view_id.arch" or (
                        rfield.name == "arch" and rfield.model == "ir.ui.view"
                    ):
                        root = ET.fromstring(record_value)
                        child = E.field(
                            {"name": rfield.name, "type": "xml"}, root
                        )

                    else:
                        child = E.field(
                            {"name": rfield.name}, str(record_value)
                        )

                    if not delete_node:
                        lst_field.append(child)

            # TODO delete this comment, check why no need anymore rec_name
            # rec_name_v = self._get_from_rec_name(record, model)
            # if rec_name_v:
            #     rec_name_v = self._lower_replace(rec_name_v)
            #     id_record = self._set_limit_4xmlid(f"{model_model}_{rec_name_v}")
            # else:
            #     rec_name_v = uuid.uuid1().int
            id_record = self._get_ir_model_data(
                record, give_a_default=True, module_name=module.name
            )
            lst_id.append(id_record)
            record_xml = E.record(
                {"id": id_record, "model": model.model}, *lst_field
            )
            lst_data_xml.append(record_xml)

        # TODO find when is noupdate and not noupdate
        # <data noupdate="1">
        xml_no_update = E.data({"noupdate": "1"}, *lst_data_xml)
        module_file = E.odoo({}, xml_no_update)
        data_file_path = os.path.join(
            self.code_generator_data.data_path, f"{model_model}.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_file, pretty_print=True
        )
        self.code_generator_data.write_file_binary(
            data_file_path, result, data_file=True
        )

        abs_path_file = os.path.join("data", f"{model_model}.xml")

        self.code_generator_data.dct_data_metadata_file[abs_path_file] = lst_id
        if lst_depend:
            self.code_generator_data.dct_data_depend[
                abs_path_file
            ] = lst_depend

    def _set_module_menus(self, module):
        """
        Function to set the module menus file
        :param module:
        :return:
        """

        application_icon = None
        menus = module.with_context({"ir.ui.menu.full_list": True}).o2m_menus
        lst_menu = []
        max_loop = 500
        i = 0
        lst_items = [a for a in menus]
        origin_lst_items = lst_items[:]
        # Sorted menu by order of parent asc, and sort child by view_name
        while lst_items:
            has_update = False
            lst_item_cache = []
            for item in lst_items[:]:
                i += 1
                if i > max_loop:
                    _logger.error("Overrun loop when reorder menu.")
                    lst_items = []
                    break
                # Expect first menu by id is a root menu
                if not item.parent_id:
                    lst_menu.append(item)
                    lst_items.remove(item)
                    has_update = True
                elif (
                    item.parent_id in lst_menu
                    or item.parent_id not in origin_lst_items
                ):
                    lst_item_cache.append(item)
                    lst_items.remove(item)
                    has_update = True

            # Order last run of adding
            if lst_item_cache:
                lst_item_cache = sorted(
                    lst_item_cache,
                    key=lambda menu: self._get_menu_data_name(menu),
                )
                lst_menu += lst_item_cache

            if not has_update:
                lst_sorted_item = sorted(
                    lst_items, key=lambda menu: self._get_menu_data_name(menu)
                )
                for item in lst_sorted_item:
                    lst_menu.append(item)

        if not lst_menu:
            return ""

        lst_menu_xml = []

        for menu in lst_menu:

            menu_id = self._get_menu_data_name(menu)
            menu_name = menu.name
            dct_menu_item = {"id": menu_id}
            if menu_name != menu_id:
                dct_menu_item["name"] = menu_name

            try:
                menu.action
            except Exception as e:
                # missing action on menu
                _logger.error(f"Missing action window on menu {menu.name}.")
                continue

            if menu.action:
                dct_menu_item["action"] = self._get_action_data_name(
                    menu.action, module=module
                )

            if not menu.active:
                dct_menu_item["active"] = "False"

            if menu.sequence != 10:
                dct_menu_item["sequence"] = str(menu.sequence)

            if menu.parent_id:
                dct_menu_item["parent"] = self._get_menu_data_name(
                    menu.parent_id
                )

            if menu.groups_id:
                dct_menu_item["groups"] = self._get_m2m_groups(menu.groups_id)

            if menu.web_icon:
                # TODO move application_icon in code_generator_data
                application_icon = menu.web_icon
                # ignore actual icon, force a new icon
                dct_menu_item[
                    "web_icon"
                ] = f"{module.name},static/description/icon.png"

            menu_xml = E.menuitem(dct_menu_item)
            lst_menu_xml.append(ET.Comment("end line"))
            lst_menu_xml.append(menu_xml)

        lst_menu_xml.append(ET.Comment("end line"))
        module_menus_file = E.odoo({}, *lst_menu_xml)
        menu_file_path = os.path.join(
            self.code_generator_data.views_path, "menu.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_menus_file, pretty_print=True
        )

        # a menuitem is separate on each line, like this:
        # <menuitem id="menu_id"
        #           name="name"
        #           sequence="8"
        # />
        key = "<menuitem "
        new_result = ""
        for line in result.decode().split("\n"):
            if line.lstrip().startswith(key):
                start_index = line.index(key)
                offset_index = start_index + len(key)
                next_index = line.index(" ", offset_index)
                last_part = line[next_index + 1 :].replace(
                    '" ', f'"\n{"  " + " " * offset_index}'
                )[:-2]
                last_part += f'\n{"  " + " " * start_index}/>\n'
                new_result += (
                    "  "
                    + line[:next_index]
                    + f'\n{"  " + " " * offset_index}'
                    + last_part
                )
            else:
                new_result += line + "\n"

        new_result = new_result.replace("  <!--end line-->\n", "\n")[:-1]

        self.code_generator_data.write_file_str(
            menu_file_path, new_result, data_file=True
        )

        return application_icon

    def _setup_xml_indent(self, content, indent=0, is_end=False):
        # return "\n".join([f"{'    ' * indent}{a}" for a in content.split("\n")])
        str_content = content.rstrip().replace("\n", f"\n{'  ' * indent}")
        super_content = f"\n{'  ' * indent}{str_content}"
        if is_end:
            super_content += f"\n{'  ' * 1}"
        else:
            super_content += f"\n{'  ' * (indent - 1)}"
        return super_content

    def _change_xml_2_to_4_spaces(self, content):
        new_content = ""
        # Change 2 space for 4 space
        for line in content.split("\n"):
            # count first space
            if line.strip():
                new_content += (
                    f'{"  " * (len(line) - len(line.lstrip()))}{line.strip()}\n'
                )
            else:
                new_content += "\n"
        return new_content

    def _set_model_xmlview_file(self, model, model_model, module):
        """
        Function to set the model xml files
        :param model:
        :param model_model:
        :param module:
        :return:
        """

        if not (
            model.view_ids or model.o2m_act_window or model.o2m_server_action
        ):
            return

        dct_replace = {}
        dct_replace_template = {}
        lst_id = []
        lst_item_xml = []
        lst_item_template = []

        #
        # Views
        #
        for view in model.view_ids:

            view_type = view.type

            lst_view_type = list(
                dict(
                    self.env["code.generator.view"]
                    ._fields["view_type"]
                    .selection
                ).keys()
            )
            if view_type in lst_view_type:

                str_id_system = self._get_id_view_model_data(
                    view, model="ir.ui.view", is_internal=True
                )
                if not str_id_system:
                    str_id = f"{model_model}_view_{view_type}"
                else:
                    str_id = str_id_system
                if str_id in lst_id:
                    count_id = lst_id.count(str_id)
                    str_id += str(count_id)
                lst_id.append(str_id)

                self.code_generator_data.add_view_id(view.name, str_id)

                lst_field = []

                if view.name:
                    lst_field.append(E.field({"name": "name"}, view.name))

                lst_field.append(E.field({"name": "model"}, view.model))

                if view.key:
                    lst_field.append(E.field({"name": "key"}, view.key))

                if view.priority != 16:
                    lst_field.append(
                        E.field({"name": "priority"}, view.priority)
                    )

                if view.inherit_id:
                    lst_field.append(
                        E.field(
                            {
                                "name": "inherit_id",
                                "ref": self._get_view_data_name(view),
                            }
                        )
                    )

                    if view.mode == "primary":
                        lst_field.append(E.field({"name": "mode"}, "primary"))

                if not view.active:
                    lst_field.append(
                        E.field({"name": "active", "eval": False})
                    )

                if view.arch_db:
                    uid = str(uuid.uuid1())
                    dct_replace[uid] = self._setup_xml_indent(
                        view.arch_db, indent=3
                    )
                    lst_field.append(
                        E.field({"name": "arch", "type": "xml"}, uid)
                    )

                if view.groups_id:
                    lst_field.append(
                        self._get_m2m_groups_etree(view.groups_id)
                    )

                info = E.record(
                    {"id": str_id, "model": "ir.ui.view"}, *lst_field
                )
                lst_item_xml.append(ET.Comment("end line"))
                lst_item_xml.append(info)

            elif view_type == "qweb":
                template_value = {"id": view.key, "name": view.name}
                if view.inherit_id:
                    template_value["inherit_id"] = view.inherit_id.key

                uid = str(uuid.uuid1())
                dct_replace_template[uid] = self._setup_xml_indent(
                    view.arch, indent=2, is_end=True
                )
                info = E.template(template_value, uid)
                # lst_item_xml.append(ET.Comment("end line"))
                # lst_item_xml.append(info)
                lst_item_template.append(ET.Comment("end line"))
                lst_item_template.append(info)

            else:
                _logger.error(
                    f"View type {view_type} of {view.name} not supported."
                )

        #
        # Action Windows
        #
        for act_window in model.o2m_act_window:
            # Use descriptive method when contain this attributes, not supported in simplify view
            use_complex_view = bool(
                act_window.groups_id
                or act_window.help
                or act_window.multi
                or not act_window.auto_search
                or act_window.filter
                or act_window.search_view_id
                or act_window.usage
            )

            record_id = self._get_id_view_model_data(
                act_window, model="ir.actions.act_window", is_internal=True
            )
            if not record_id:
                record_id = self._get_action_data_name(
                    act_window, creating=True
                )

            if use_complex_view:
                lst_field = []

                if act_window.name:
                    lst_field.append(
                        E.field({"name": "name"}, act_window.name)
                    )

                if act_window.res_model or act_window.m2o_res_model:
                    lst_field.append(
                        E.field(
                            {"name": "res_model"},
                            act_window.res_model
                            or act_window.m2o_res_model.model,
                        )
                    )

                if act_window.binding_model_id:
                    binding_model = self._get_model_data_name(
                        act_window.binding_model_id
                    )
                    lst_field.append(
                        E.field(
                            {"name": "binding_model_id", "ref": binding_model}
                        )
                    )

                if act_window.view_id:
                    lst_field.append(
                        E.field(
                            {
                                "name": "view_id",
                                "ref": self._get_view_data_name(
                                    act_window.view_id
                                ),
                            }
                        )
                    )

                if act_window.domain != "[]" and act_window.domain:
                    lst_field.append(
                        E.field({"name": "domain"}, act_window.domain)
                    )

                if act_window.context != "{}":
                    lst_field.append(
                        E.field({"name": "context"}, act_window.context)
                    )

                if act_window.src_model or act_window.m2o_src_model:
                    lst_field.append(
                        E.field(
                            {"name": "src_model"},
                            act_window.src_model
                            or act_window.m2o_src_model.model,
                        )
                    )

                if act_window.target != "current":
                    lst_field.append(
                        E.field({"name": "target"}, act_window.target)
                    )

                if act_window.view_mode != "tree,form":
                    lst_field.append(
                        E.field({"name": "view_mode"}, act_window.view_mode)
                    )

                if act_window.view_type != "form":
                    lst_field.append(
                        E.field({"name": "view_type"}, act_window.view_type)
                    )

                if act_window.usage:
                    lst_field.append(E.field({"name": "usage", "eval": True}))

                if act_window.limit != 80:
                    lst_field.append(
                        E.field({"name": "limit"}, act_window.limit)
                    )

                if act_window.search_view_id:
                    lst_field.append(
                        E.field(
                            {
                                "name": "search_view_id",
                                "ref": self._get_view_data_name(
                                    act_window.search_view_id
                                ),
                            }
                        )
                    )

                if act_window.filter:
                    lst_field.append(E.field({"name": "filter", "eval": True}))

                if not act_window.auto_search:
                    lst_field.append(
                        E.field({"name": "auto_search", "eval": False})
                    )

                if act_window.multi:
                    lst_field.append(E.field({"name": "multi", "eval": True}))

                if act_window.help:
                    lst_field.append(
                        E.field(
                            {"name": "name", "type": "html"}, act_window.help
                        )
                    )

                if act_window.groups_id:
                    lst_field.append(
                        self._get_m2m_groups_etree(act_window.groups_id)
                    )

                info = E.record(
                    {"id": record_id, "model": "ir.actions.act_window"},
                    *lst_field,
                )
                lst_item_xml.append(ET.Comment("end line"))
                lst_item_xml.append(info)
            else:
                dct_act_window = {"id": record_id}

                if act_window.name:
                    dct_act_window["name"] = act_window.name

                if act_window.res_model or act_window.m2o_res_model:
                    dct_act_window["res_model"] = (
                        act_window.res_model or act_window.m2o_res_model.model
                    )

                if act_window.binding_model_id:
                    # TODO replace ref
                    pass

                if act_window.view_id:
                    # TODO replace ref
                    pass

                if act_window.domain != "[]" and act_window.domain:
                    dct_act_window["domain"] = (
                        act_window.res_model or act_window.m2o_res_model.model
                    )

                if act_window.context != "{}":
                    dct_act_window["context"] = act_window.context

                if act_window.src_model or act_window.m2o_src_model:
                    dct_act_window["src_model"] = (
                        act_window.src_model or act_window.m2o_src_model.model
                    )

                if act_window.target != "current":
                    dct_act_window["target"] = act_window.target

                if act_window.view_mode != "tree,form":
                    dct_act_window["view_mode"] = act_window.view_mode

                if act_window.view_type != "form":
                    dct_act_window["view_type"] = act_window.view_type

                if act_window.usage:
                    # TODO replace ref
                    pass

                if act_window.limit != 80:
                    dct_act_window["limit"] = act_window.limit

                if act_window.search_view_id:
                    # TODO replace ref
                    pass

                if act_window.filter:
                    # TODO replace ref
                    pass

                if not act_window.auto_search:
                    # TODO replace ref
                    pass

                if act_window.multi:
                    # TODO replace ref
                    pass

                if act_window.help:
                    # TODO how add type html and contents?
                    pass

                if act_window.groups_id:
                    # TODO check _get_m2m_groups_etree
                    pass

                info = E.act_window(dct_act_window)
                lst_item_xml.append(ET.Comment("end line"))
                lst_item_xml.append(info)

        #
        # Server Actions
        #
        for server_action in model.o2m_server_action:

            lst_field = []

            lst_field.append(E.field({"name": "name"}, server_action.name))

            lst_field.append(
                E.field(
                    {
                        "name": "model_id",
                        "ref": self._get_model_data_name(
                            server_action.model_id
                        ),
                    }
                )
            )

            lst_field.append(
                E.field(
                    {
                        "name": "binding_model_id",
                        "ref": self._get_model_data_name(model),
                    }
                )
            )

            if server_action.state == "code":
                lst_field.append(E.field({"name": "state"}, "code"))

                lst_field.append(E.field({"name": "code"}, server_action.code))

            else:
                lst_field.append(E.field({"name": "state"}, "multi"))

                if server_action.child_ids:
                    child_obj = ", ".join(
                        server_action.child_ids.mapped(
                            lambda child: "ref(%s)"
                            % self._get_action_data_name(child, server=True)
                        )
                    )
                    lst_field.append(
                        E.field(
                            {
                                "name": "child_ids",
                                "eval": f"[(6,0, [{child_obj}])]",
                            }
                        )
                    )

            record_id = self._get_id_view_model_data(
                server_action, model="ir.actions.server", is_internal=True
            )
            if not record_id:
                record_id = self._get_action_data_name(
                    server_action, server=True, creating=True
                )
            info = E.record(
                {"id": record_id, "model": "ir.actions.server"}, *lst_field
            )
            lst_item_xml.append(ET.Comment("end line"))

            if server_action.comment:
                lst_item_xml.append(
                    ET.Comment(text=f" {server_action.comment} ")
                )

            lst_item_xml.append(info)

        lst_item_xml.append(ET.Comment("end line"))
        root = E.odoo({}, *lst_item_xml)

        content = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            root, pretty_print=True
        )
        str_content = content.decode()

        str_content = str_content.replace("  <!--end line-->\n", "\n")
        for key, value in dct_replace.items():
            str_content = str_content.replace(key, value)
        str_content = self._change_xml_2_to_4_spaces(str_content)[:-1]

        wizards_path = self.code_generator_data.wizards_path
        views_path = self.code_generator_data.views_path
        xml_file_path = os.path.join(
            wizards_path if model.transient else views_path,
            f"{model_model}.xml",
        )
        self.code_generator_data.write_file_str(
            xml_file_path, str_content, data_file=True
        )

        if dct_replace_template:
            root_template = E.odoo({}, *lst_item_template)
            content_template = XML_VERSION_HEADER.encode(
                "utf-8"
            ) + ET.tostring(root_template, pretty_print=True)
            str_content_template = content_template.decode()

            str_content_template = str_content_template.replace(
                "  <!--end line-->\n", "\n"
            )
            for key, value in dct_replace_template.items():
                str_content_template = str_content_template.replace(key, value)
            str_content_template = self._change_xml_2_to_4_spaces(
                str_content_template
            )[:-1]

            views_path = self.code_generator_data.views_path
            xml_file_path = os.path.join(
                views_path,
                f"{module.name}_templates.xml",
            )
            self.code_generator_data.write_file_str(
                xml_file_path, str_content_template, data_file=True
            )

    def _set_model_xmlreport_file(self, model, model_model):
        """

        :param model:
        :param model_model:
        :return:
        """

        if not model.o2m_reports:
            return

        l_model_report_file = XML_HEAD + BLANK_LINE

        for report in model.o2m_reports:

            l_model_report_file.append(
                '<template id="%s">' % report.report_name
            )

            l_model_report_file.append(
                '<field name="arch" type="xml">%s</field>'
                % report.m2o_template.arch_db
            )

            l_model_report_file.append("</template>\n")

            l_model_report_file.append(
                '<record model="ir.actions.report" id="%s_actionreport">'
                % report.report_name
            )

            l_model_report_file.append(
                '<field name="model">%s</field>' % report.model
            )

            l_model_report_file.append(
                '<field name="name">%s</field>' % report.report_name
            )

            l_model_report_file.append(
                '<field name="file">%s</field>' % report.report_name
            )

            l_model_report_file.append(
                '<field name="string">%s</field>' % report.name
            )

            l_model_report_file.append(
                '<field name="report_type">%s</field>' % report.report_type
            )

            if report.print_report_name:
                l_model_report_file.append(
                    '<field name="print_report_name">%s</field>'
                    % report.print_report_name
                )

            if report.multi:
                l_model_report_file.append(
                    '<field name="multi">%s</field>' % report.multi
                )

            if report.attachment_use:
                l_model_report_file.append(
                    '<field name="attachment_use">%s</field>'
                    % report.attachment_use
                )

            if report.attachment:
                l_model_report_file.append(
                    '<field name="attachment">%s</field>' % report.attachment
                )

            if report.binding_model_id:
                l_model_report_file.append(
                    '<field name="binding_model_id" ref="%s" />'
                    % self._get_model_data_name(report.binding_model_id)
                )

            if report.groups_id:
                l_model_report_file.append(
                    self._get_m2m_groups(report.groups_id)
                )

            l_model_report_file.append("</record>")

            l_model_report_file += XML_ODOO_CLOSING_TAG

        xmlreport_file_path = os.path.join(
            self.code_generator_data.reports_path, f"{model_model}.xml"
        )
        self.code_generator_data.write_file_lst_content(
            xmlreport_file_path, l_model_report_file, data_file=True
        )

    def _set_model_py_file(self, module, model, model_model):
        """
        Function to set the model files
        :param model:
        :param model_model:
        :return:
        """

        cw = CodeWriter()

        code_ids = model.o2m_codes.filtered(
            lambda x: not x.is_templated
        ).sorted(key=lambda x: x.sequence)
        code_import_ids = model.o2m_code_import.filtered(
            lambda x: not x.is_templated
        ).sorted(key=lambda x: x.sequence)
        if code_import_ids:
            for code in code_import_ids:
                for code_line in code.code.split("\n"):
                    cw.emit(code_line)
        else:
            # search api or contextmanager
            # TODO ignore api, because need to search in code
            has_context_manager = False
            lst_import = MODEL_HEAD
            for code_id in code_ids:
                if (
                    code_id.decorator
                    and "@contextmanager" in code_id.decorator
                ):
                    has_context_manager = True
            if has_context_manager:
                lst_import.insert(1, "from contextlib import contextmanager")

            for line in lst_import:
                str_line = line.strip()
                cw.emit(str_line)

            if (
                model.m2o_inherit_py_class.name
                and model.m2o_inherit_py_class.module
            ):
                cw.emit(
                    f"from {model.m2o_inherit_py_class.module} import"
                    f" {model.m2o_inherit_py_class.name}"
                )

        cw.emit()
        cw.emit(
            "class"
            f" {self._get_class_name(model.model)}({self._get_python_class_4inherit(model)}):"
        )

        with cw.indent():
            """
            _name
            _table =
            _description
            _auto = False
            _log_access = False
            _order = ""
            _rec_name = ""
            _foreign_keys = []
            """
            cw.emit(f"_name = '{model.model}'")

            # Force unique inherit
            lst_inherit = sorted(
                list(set([a.depend_id.model for a in model.inherit_model_ids]))
            )
            if lst_inherit:
                if len(lst_inherit) == 1:
                    str_inherit = f"'{lst_inherit[0]}'"
                else:
                    str_inherit = f"""["{'", "'.join(lst_inherit)}"]"""
                cw.emit(f"_inherit = {str_inherit}")

            if model.description:
                new_description = model.description.replace("'", "\\'")
                cw.emit(f"_description = '{new_description}'")
            else:
                cw.emit(f"_description = '{model.name}'")
            if model.rec_name and model.rec_name != "name":
                cw.emit(f"_rec_name = '{model.rec_name}'")

            # TODO _order, _local_fields, _period_number, _inherits, _log_access, _auto, _parent_store
            # TODO _parent_name

            self._get_model_constrains(cw, model, module)

            self._get_model_fields(cw, model)

            # code_ids = self.env["code.generator.model.code"].search(
            #     [("m2o_module", "=", module.id)]
            # )

            # Add function
            for code in code_ids:
                cw.emit()
                if code.decorator:
                    for line in code.decorator.split(";"):
                        if line:
                            cw.emit(line)
                return_v = "" if not code.returns else f" -> {code.returns}"
                cw.emit(f"def {code.name}({code.param}){return_v}:")
                with cw.indent():
                    for code_line in code.code.split("\n"):
                        cw.emit(code_line)

        if model.transient:
            pypath = self.code_generator_data.wizards_path
        elif model.o2m_reports and self.env[model.model]._abstract:
            pypath = self.code_generator_data.reports_path
        else:
            pypath = self.code_generator_data.models_path

        model_file_path = os.path.join(pypath, f"{model_model}.py")

        self.code_generator_data.write_file_str(model_file_path, cw.render())

        return model_file_path

    def _set_module_security(self, module, l_model_rules, l_model_csv_access):
        """
        Function to set the module security file
        :param module:
        :param l_model_rules:
        :param l_model_csv_access:
        :return:
        """
        l_model_csv_access.insert(
            0,
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink",
        )

        if module.o2m_groups or l_model_rules:
            l_module_security = ["<data>\n"]

            for group in module.o2m_groups:

                l_module_security += [
                    '<record model="res.groups" id="%s">'
                    % self._get_group_data_name(group)
                ]
                l_module_security += [
                    '<field name="name">%s</field>' % group.name
                ]

                if group.comment:
                    l_module_security += [
                        '<field name="comment">%s</field>' % group.comment
                    ]

                if group.implied_ids:
                    l_module_security += [
                        '<field name="implied_ids" eval="[%s]"/>'
                        % ", ".join(
                            group.implied_ids.mapped(
                                lambda g: "(4, ref('%s'))"
                                % self._get_group_data_name(g)
                            )
                        )
                    ]

                l_module_security += ["</record>\n"]

            l_module_security += l_model_rules

            l_module_security += ["</data>"]

            module_name = module.name.lower().strip()
            security_file_path = os.path.join(
                self.code_generator_data.security_path, f"{module_name}.xml"
            )
            self.code_generator_data.write_file_lst_content(
                security_file_path,
                XML_HEAD + l_module_security + XML_ODOO_CLOSING_TAG,
                data_file=True,
                insert_first=True,
            )

        if len(l_model_csv_access) > 1:
            model_access_file_path = os.path.join(
                self.code_generator_data.security_path, "ir.model.access.csv"
            )
            self.code_generator_data.write_file_lst_content(
                model_access_file_path,
                l_model_csv_access,
                data_file=True,
                insert_first=True,
            )

    def _get_model_access(self, module, model):
        """
        Function to obtain the model access
        :param model:
        :return:
        """

        l_model_csv_access = []

        for access in model.access_ids:
            access_name = access.name

            access_model_data = self.env["ir.model.data"].search(
                [
                    ("module", "=", module.name),
                    ("model", "=", "ir.model.access"),
                    ("res_id", "=", access.id),
                ]
            )

            access_id = (
                access_model_data[0].name
                if access_model_data
                else self._lower_replace(access_name)
            )

            access_model = self._get_model_model(access.model_id.model)

            access_group = (
                self._get_group_data_name(access.group_id)
                if access.group_id
                else ""
            )

            access_read, access_create, access_write, access_unlink = (
                1 if access.perm_read else 0,
                1 if access.perm_create else 0,
                1 if access.perm_write else 0,
                1 if access.perm_unlink else 0,
            )

            l_model_csv_access.append(
                "%s,%s,model_%s,%s,%s,%s,%s,%s"
                % (
                    access_id,
                    access_name,
                    access_model,
                    access_group,
                    access_read,
                    access_create,
                    access_write,
                    access_unlink,
                )
            )

        return l_model_csv_access

    def _get_model_rules(self, model):
        """
        Function to obtain the model rules
        :param model:
        :return:
        """

        l_model_rules = []

        for rule in model.rule_ids:

            if rule.name:
                l_model_rules.append(
                    '<record model="ir.rule" id="%s">'
                    % self._lower_replace(rule.name)
                )
                l_model_rules.append(
                    '<field name="name">%s</field>' % rule.name
                )

            else:
                l_model_rules.append(
                    '<record model="ir.rule" id="%s_rrule_%s">'
                    % (self._get_model_data_name(rule.model_id), rule.id)
                )

            l_model_rules.append(
                '<field name="model_id" ref="%s"/>'
                % self._get_model_data_name(rule.model_id)
            )

            if rule.domain_force:
                l_model_rules.append(
                    '<field name="domain_force">%s</field>' % rule.domain_force
                )

            if not rule.active:
                l_model_rules.append('<field name="active" eval="False" />')

            if rule.groups:
                l_model_rules.append(self._get_m2m_groups(rule.groups))

            if not rule.perm_read:
                l_model_rules.append('<field name="perm_read" eval="False" />')

            if not rule.perm_create:
                l_model_rules.append(
                    '<field name="perm_create" eval="False" />'
                )

            if not rule.perm_write:
                l_model_rules.append(
                    '<field name="perm_write" eval="False" />'
                )

            if not rule.perm_unlink:
                l_model_rules.append(
                    '<field name="perm_unlink" eval="False" />'
                )

            l_model_rules.append("</record>\n")

        return l_model_rules

    def _get_m2m_groups(self, m2m_groups):
        """

        :param m2m_groups:
        :return:
        """

        return '<field name="groups_id" eval="[(6,0, [%s])]" />' % ", ".join(
            m2m_groups.mapped(
                lambda g: "ref(%s)" % self._get_group_data_name(g)
            )
        )

    def _get_m2m_groups_etree(self, m2m_groups):
        """

        :param m2m_groups:
        :return:
        """

        var = ", ".join(
            m2m_groups.mapped(
                lambda g: "ref(%s)" % self._get_group_data_name(g)
            )
        )
        return E.field({"name": "groups_id", "eval": f"[(6,0, [{var}])]"})

    def _get_model_fields(self, cw, model):
        """
        Function to obtain the model fields
        :param model:
        :return:
        """

        # TODO detect if contain code_generator_sequence, else order by name
        f2exports = model.field_id.filtered(
            lambda field: field.name not in MAGIC_FIELDS
        ).sorted(key=lambda r: r.code_generator_sequence)

        if model.inherit_model_ids:
            father_ids = self.env["ir.model"].browse(
                [a.depend_id.id for a in model.inherit_model_ids]
            )
            set_unique_field = set()
            for father_id in father_ids:
                fatherfieldnames = father_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                ).mapped("name")
                set_unique_field.update(fatherfieldnames)
            f2exports = f2exports.filtered(
                lambda field: field.name not in list(set_unique_field)
            )

        for f2export in f2exports:
            cw.emit()
            dct_field_attribute = {}

            # TODO use if cannot find information
            # field_selection = self.env[f2export.model].fields_get(f2export.name).get(f2export.name)

            # Respect sequence in list, order listed by human preference

            if (
                f2export.ttype == "reference" or f2export.ttype == "selection"
            ) and f2export.selection:
                if f2export.selection != "[]":
                    try:
                        # Transform string in list
                        lst_selection = ast.literal_eval(f2export.selection)
                        # lst_selection = [f"'{a}'" for a in lst_selection]
                        dct_field_attribute["selection"] = lst_selection
                    except Exception as e:
                        dct_field_attribute["selection"] = []
                        _logger.error(
                            f"The selection of field {f2export.name} is not a"
                            f" list: '{f2export.selection}'."
                        )
                else:
                    dct_field_attribute["selection"] = []

            if (
                f2export.field_description
                and f2export.name.replace("_", " ").title()
                != f2export.field_description
            ):
                dct_field_attribute["string"] = f2export.field_description

            if f2export.ttype in ["many2one", "one2many", "many2many"]:
                if f2export.relation:
                    dct_field_attribute["comodel_name"] = f2export.relation

                if f2export.ttype == "one2many" and f2export.relation_field:
                    dct_field_attribute[
                        "inverse_name"
                    ] = f2export.relation_field

                if (
                    f2export.ttype == "many2one"
                    and f2export.on_delete
                    and f2export.on_delete != "set null"
                ):
                    dct_field_attribute["ondelete"] = f2export.on_delete

                if f2export.domain and f2export.domain != "[]":
                    dct_field_attribute["domain"] = f2export.domain

                if f2export.ttype == "many2many":
                    # A relation who begin with x_ is an automated relation, ignore it
                    ignored_relation = (
                        False
                        if not f2export.relation_table
                        else f2export.relation_table.startswith("x_")
                    )
                    if not ignored_relation:
                        if f2export.relation_table:
                            dct_field_attribute[
                                "relation"
                            ] = f2export.relation_table
                        if f2export.column1:
                            dct_field_attribute["column1"] = f2export.column1
                        if f2export.column2:
                            dct_field_attribute["column2"] = f2export.column2

            if (
                f2export.ttype == "char" or f2export.ttype == "reference"
            ) and f2export.size != 0:
                dct_field_attribute["size"] = f2export.size

            if f2export.related:
                dct_field_attribute["related"] = f2export.related

            if f2export.readonly:
                dct_field_attribute["readonly"] = True

            if f2export.required:
                dct_field_attribute["required"] = True

            if f2export.index:
                dct_field_attribute["index"] = True

            if f2export.track_visibility:
                if f2export.track_visibility in ("onchange", "always"):
                    dct_field_attribute[
                        "track_visibility"
                    ] = f2export.track_visibility
                    # TODO is it the good place for this?
                    # lst_depend_model = [
                    #     "mail.thread",
                    #     "mail.activity.mixin",
                    # ]
                    # f2export.model_id.add_model_inherit(lst_depend_model)
                else:
                    _logger.warning(
                        "Cannot support track_visibility value"
                        f" {f2export.track_visibility}, only support"
                        " 'onchange' and 'always'."
                    )

            if f2export.default:
                # TODO support default = None
                # TODO validate with type for boolean
                if f2export.default == "True":
                    dct_field_attribute["default"] = True
                elif f2export.default == "False":
                    dct_field_attribute["default"] = False
                elif f2export.ttype == "integer":
                    dct_field_attribute["default"] = int(f2export.default)
                elif f2export.ttype in ("char", "selection"):
                    dct_field_attribute["default"] = f2export.default
                else:
                    _logger.warning(
                        f"Not supported default type {f2export.ttype}"
                    )
                    dct_field_attribute["default"] = f2export.default

            # TODO support states

            if f2export.groups:
                dct_field_attribute["groups"] = f2export.groups.mapped(
                    lambda g: self._get_group_data_name(g)
                )

            compute = f2export.compute and f2export.depends
            if f2export.code_generator_compute:
                dct_field_attribute[
                    "compute"
                ] = f2export.code_generator_compute
            elif compute:
                dct_field_attribute["compute"] = f"_compute_{f2export.name}"

            if (
                f2export.ttype == "one2many" or f2export.related or compute
            ) and f2export.copied:
                dct_field_attribute["copy"] = True

            # TODO support oldname

            # TODO support group_operator

            # TODO support inverse

            # TODO support search

            # TODO support store
            if f2export.store and f2export.code_generator_compute:
                dct_field_attribute["store"] = True
            elif not f2export.store:
                dct_field_attribute["store"] = False

            # TODO support compute_sudo

            if f2export.translate:
                dct_field_attribute["translate"] = True

            if not f2export.selectable:
                dct_field_attribute["selectable"] = False

            # TODO support digits, check dp.get_precision('Account')

            if f2export.help:
                dct_field_attribute["help"] = f2export.help.replace("\\'", '"')

            # Ignore it, by default it's copy=False
            # elif f2export.ttype != 'one2many' and not f2export.related and not compute and not f2export.copied:
            #     dct_field_attribute["copy"] = False

            lst_field_attribute = []
            for key, value in dct_field_attribute.items():
                if type(value) is str:
                    # TODO find another solution than removing \n, this cause error with cw.CodeWriter
                    value = value.replace("\n", " ").replace("'", "\\'")
                    if key == "default" and value.startswith("lambda"):
                        # Exception for lambda
                        lst_field_attribute.append(f"{key}={value}")
                    else:
                        lst_field_attribute.append(f"{key}='{value}'")
                elif type(value) is list:
                    # TODO find another solution than removing \n, this cause error with cw.CodeWriter
                    new_value = str(value).replace("\n", " ")
                    lst_field_attribute.append(f"{key}={new_value}")
                else:
                    lst_field_attribute.append(f"{key}={value}")

            cw.emit_list(
                lst_field_attribute,
                ("(", ")"),
                before=(
                    f"{f2export.name} ="
                    f" {self._get_odoo_ttype_class(f2export.ttype)}"
                ),
            )

            if compute:
                cw.emit()
                l_depends = self._get_l_map(
                    lambda e: e.strip(), f2export.depends.split(",")
                )

                cw.emit(
                    f"@api.depends({self._prepare_compute_constrained_fields(l_depends)})"
                )
                cw.emit(f"def _compute_{f2export.name}(self):")

                l_compute = f2export.compute.split("\n")
                # starting_spaces = 2
                # for line in l_compute:
                #     if self._get_starting_spaces(line) == 2:
                #         starting_spaces += 1
                #     l_model_fields.append('%s%s' % (TAB4 * starting_spaces, line.strip()))
                for line in l_compute:
                    with cw.indent():
                        cw.emit(line.rstrip())

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create log of code generator writer
        :return:
        """
        new_list = []
        for vals in vals_list:
            new_list.append(self.generate_writer(vals))

        return super(CodeGeneratorWriter, self).create(new_list)

    def get_lst_file_generate(self, module):
        l_model_csv_access = []
        l_model_rules = []

        module.view_file_sync = {}
        module.module_file_sync = {}

        if module.template_model_name:
            lst_model = module.template_model_name.split(";")
            for model in lst_model:
                model = model.strip()
                if model:
                    module.view_file_sync[model] = self.ExtractorView(
                        module, model
                    )
                    module.module_file_sync[model] = self.ExtractorModule(
                        module, model, module.view_file_sync[model]
                    )

        for model in module.o2m_models:

            model_model = self._get_model_model(model.model)

            if not module.nomenclator_only:
                # Wizard
                self._set_model_py_file(module, model, model_model)
                self._set_model_xmlview_file(model, model_model, module)

                # Report
                self._set_model_xmlreport_file(model, model_model)

            parameters = self.env["ir.config_parameter"].sudo()
            s_data2export = parameters.get_param(
                "code_generator.s_data2export", default="nomenclator"
            )
            if s_data2export != "nomenclator" or (
                s_data2export == "nomenclator" and model.nomenclator
            ):
                self._set_model_xmldata_file(module, model, model_model)

            if not module.nomenclator_only:
                l_model_csv_access += self._get_model_access(module, model)

                l_model_rules += self._get_model_rules(model)

        if not module.nomenclator_only:
            application_icon = self._set_module_menus(module)

            self.set_xml_data_file(module)

            self.set_xml_views_file(module)

            self.set_module_python_file(module)

            self.set_module_css_file(module)

            self._set_module_security(
                module, l_model_rules, l_model_csv_access
            )

            self._set_static_description_file(module, application_icon)

            # TODO info Moved in template module
            # self.set_module_translator(module)

        self.set_extra_get_lst_file_generate(module)

        self.code_generator_data.reorder_manifest_data_files()

        self._set_manifest_file(module)

        self.set_module_init_file_extra(module)

        self.code_generator_data.generate_python_init_file(module)

        self.code_generator_data.auto_format()
        if module.enable_pylint_check:
            # self.code_generator_data.flake8_check()
            self.code_generator_data.pylint_check()

    def set_xml_data_file(self, module):
        pass

    def set_xml_views_file(self, module):
        pass

    def set_module_css_file(self, module):
        pass

    def set_module_python_file(self, module):
        pass

    def set_extra_get_lst_file_generate(self, module):
        pass

    @api.multi
    def generate_writer(self, vals):
        modules = self.env["code.generator.module"].browse(
            vals.get("code_generator_ids")
        )

        # path = tempfile.gettempdir()
        path = tempfile.mkdtemp()
        _logger.info(f"Temporary path for code generator: {path}")
        morethanone = len(modules.ids) > 1
        if morethanone:
            # TODO validate it's working
            path += "/modules"
            CodeGeneratorData.os_make_dirs(path)

        os.chdir(path=path)

        basename = (
            "modules" if morethanone else modules[0].name.lower().strip()
        )
        vals["basename"] = basename
        rootdir = (
            path
            if morethanone
            else path + "/" + modules[0].name.lower().strip()
        )
        vals["rootdir"] = rootdir

        for module in modules:
            # TODO refactor this to share variable in another class,
            #  like that, self.code_generator_data will be associate to a class of generation of module
            self.code_generator_data = CodeGeneratorData(module, path)
            self.get_lst_file_generate(module)

            if module.enable_sync_code:
                self.code_generator_data.sync_code(
                    module.path_sync_code, module.name
                )

        vals["list_path_file"] = ";".join(
            self.code_generator_data.lst_path_file
        )

        return vals

    def get_list_path_file(self):
        return self.list_path_file.split(";")


class CodeGeneratorData:
    def __init__(self, module, path):
        self._lst_models_init_imports = []
        self._lst_wizards_init_imports = []
        self._lst_controllers_init_imports = []
        self._lst_path_file = set()
        self._dct_data_depend = defaultdict(list)
        self._dct_data_metadata_file = defaultdict(list)
        self._path = path
        self._module_name = module.name.lower().strip()
        self._module_path = os.path.join(path, self._module_name)
        self._data_path = "data"
        self._demo_path = "demo"
        self._tests_path = "tests"
        self._i18n_path = "i18n"
        self._migrations_path = "migrations"
        self._readme_path = "readme"
        self._components_path = "components"
        self._models_path = "models"
        self._css_path = os.path.join("static", "src", "scss")
        self._security_path = "security"
        self._views_path = "views"
        self._wizards_path = "wizard"
        self._controllers_path = "controllers"
        self._reports_path = "report"
        self._static_description_path = os.path.join("static", "description")
        self._lst_manifest_data_files = []
        self._dct_import_dir = defaultdict(list)
        self._dct_extra_module_init_path = defaultdict(list)
        self._dct_view_id = {}
        # Copy not_supported_files first and permit code to overwrite it
        self.copy_not_supported_files(module)

    def copy_not_supported_files(self, module):
        # TODO this is an hack to get code_generator module to search not_supported_files
        # TODO refactor this and move not_supported_files in models, this is wrong conception
        if not module.icon:
            return

        origin_path = os.path.normpath(
            os.path.join(module.icon, "..", "..", "..", "not_supported_files")
        )
        if os.path.isdir(origin_path):
            for root, dirs, files in os.walk(origin_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.join(
                        root[len(origin_path) + 1 :], file
                    )
                    _, ext = os.path.splitext(relative_path)
                    is_data_file = ext == ".xml"
                    self.copy_file(
                        file_path, relative_path, data_file=is_data_file
                    )

    @staticmethod
    def os_make_dirs(path, exist_ok=True):
        """
        Util function to wrap the makedirs method
        :param path:
        :param exist_ok:
        :return:
        """
        os.makedirs(path, exist_ok=exist_ok)

    @property
    def lst_path_file(self):
        return list(self._lst_path_file)

    @property
    def dct_data_depend(self):
        return self._dct_data_depend

    @property
    def dct_data_metadata_file(self):
        return self._dct_data_metadata_file

    @property
    def module_path(self):
        return self._module_path

    @property
    def data_path(self):
        return self._data_path

    @property
    def demo_path(self):
        return self._demo_path

    @property
    def tests_path(self):
        return self._tests_path

    @property
    def i18n_path(self):
        return self._i18n_path

    @property
    def migrations_path(self):
        return self._migrations_path

    @property
    def readme_path(self):
        return self._readme_path_path

    @property
    def components_path(self):
        return self._components_path

    @property
    def models_path(self):
        return self._models_path

    @property
    def css_path(self):
        return self._css_path

    @property
    def security_path(self):
        return self._security_path

    @property
    def views_path(self):
        return self._views_path

    @property
    def wizards_path(self):
        return self._wizards_path

    @property
    def controllers_path(self):
        return self._controllers_path

    @property
    def reports_path(self):
        return self._reports_path

    @property
    def static_description_path(self):
        return self._static_description_path

    @property
    def dct_view_id(self):
        return self._dct_view_id

    @property
    def lst_manifest_data_files(self):
        return self._lst_manifest_data_files

    @property
    def lst_import_dir(self):
        return list(self._dct_import_dir.keys())

    def add_view_id(self, name, str_id):
        self._dct_view_id[name] = str_id

    def add_module_init_path(self, component, import_line):
        self._dct_extra_module_init_path[component].append(import_line)

    def _get_lst_files_data_depends(self, lst_meta):
        set_files = set()
        for meta in lst_meta:
            for file_name, lst_key in self.dct_data_metadata_file.items():
                if meta in lst_key:
                    set_files.add(file_name)
                    break
            else:
                _logger.error(f"Cannot find key {meta}.")
        return list(set_files)

    def reorder_manifest_data_files(self):
        lst_manifest = []
        dct_hold_file = {}
        for manifest_data in self._lst_manifest_data_files:
            if manifest_data in self.dct_data_depend.keys():
                # find depend and report until order is right
                lst_meta = self.dct_data_depend.get(manifest_data)
                lst_files_depends = self._get_lst_files_data_depends(lst_meta)
                dct_hold_file[manifest_data] = lst_files_depends
            else:
                lst_manifest.append(manifest_data)

        i = 0
        max_i = len(dct_hold_file) + 1
        while dct_hold_file and i < max_i:
            i += 1
            for new_ele, lst_depend in dct_hold_file.items():
                final_index = -1
                for depend in lst_depend:
                    try:
                        index = lst_manifest.index(depend)
                    except ValueError:
                        # element not in list, continue
                        final_index = -1
                        break
                    if index > final_index:
                        final_index = index
                if final_index >= 0:
                    lst_manifest.insert(final_index + 1, new_ele)
                    del dct_hold_file[new_ele]
                    # Need to break or crash on loop because dict has change
                    break
        if dct_hold_file:
            _logger.error(f"Cannot reorder all manifest file: {dct_hold_file}")
        self._lst_manifest_data_files = lst_manifest

    def copy_directory(self, source_directory_path, directory_path):
        """
        Copy only directory without manipulation
        :param source_directory_path:
        :param directory_path:
        :return:
        """
        absolute_path = os.path.join(
            self._path, self._module_name, directory_path
        )
        # self.check_mkdir_and_create(absolute_path, is_file=False)
        status = shutil.copytree(source_directory_path, absolute_path)

    def copy_file(
        self,
        source_file_path,
        file_path,
        data_file=False,
        search_and_replace=[],
    ):
        # TODO if no search_and_replace, use system copy instead of read file and write
        # TODO problem, we need to add the filename in the system when calling write_file_*
        # TODO or document it why using this technique
        with open(source_file_path, "rb") as file_source:
            content = file_source.read()

        if search_and_replace:
            # switch binary to string
            content = content.decode("utf-8")
            for search, replace in search_and_replace:
                content = content.replace(search, replace)
            self.write_file_str(file_path, content, data_file=data_file)
        else:
            self.write_file_binary(file_path, content, data_file=data_file)

    def write_file_lst_content(
        self,
        file_path,
        lst_content,
        data_file=False,
        insert_first=False,
        empty_line_end_of_file=True,
    ):
        """
        Function to create a file with some content
        :param file_path:
        :param lst_content:
        :param data_file:
        :param insert_first:
        :param empty_line_end_of_file:
        :return:
        """

        str_content = "\n".join(lst_content)
        if empty_line_end_of_file and str_content and str_content[-1] != "\n":
            str_content += "\n"

        content = str_content.encode("utf-8")

        try:
            self.write_file_binary(
                file_path,
                content,
                data_file=data_file,
                insert_first=insert_first,
            )
        except Exception as e:
            _logger.error(e)
            raise e

    def write_file_str(
        self, file_path, content, mode="w", data_file=False, insert_first=False
    ):
        """
        Function to create a file with some binary content
        :param file_path:
        :param content:
        :param mode:
        :param data_file:
        :param insert_first:
        :return:
        """
        self.write_file_binary(
            file_path,
            content,
            mode=mode,
            data_file=data_file,
            insert_first=insert_first,
        )

    def write_file_binary(
        self,
        file_path,
        content,
        mode="wb",
        data_file=False,
        insert_first=False,
    ):
        """
        Function to create a file with some binary content
        :param file_path:
        :param content:
        :param mode:
        :param data_file: Will be add in manifest
        :param insert_first:
        :return:
        """

        # file_path suppose to be a relative path
        if file_path[0] == "/":
            _logger.warning(f"Path {file_path} not suppose to start with '/'.")
            file_path = file_path[1:]

        absolute_path = os.path.join(self._path, self._module_name, file_path)
        self._lst_path_file.add(absolute_path)

        if data_file and file_path not in self._lst_manifest_data_files:
            if insert_first:
                self._lst_manifest_data_files.insert(0, file_path)
            else:
                self._lst_manifest_data_files.append(file_path)

        self._check_import_python_file(file_path)

        self.check_mkdir_and_create(absolute_path)

        with open(absolute_path, mode) as file:
            file.write(content)

    @staticmethod
    def _split_path_all(path):
        all_parts = []
        while 1:
            parts = os.path.split(path)
            if parts[0] == path:  # sentinel for absolute paths
                all_parts.insert(0, parts[0])
                break
            elif parts[1] == path:  # sentinel for relative paths
                all_parts.insert(0, parts[1])
                break
            else:
                path = parts[0]
                all_parts.insert(0, parts[1])
        return all_parts

    def _check_import_python_file(self, file_path):
        if file_path and file_path[-3:] == ".py":
            dir_name = os.path.dirname(file_path)
            if dir_name == "tests":
                # Ignore tests python file
                return
            if len(self._split_path_all(dir_name)) > 1:
                # This is a odoo limitation, but we can support it if need it
                _logger.warning(
                    "You add python file more depth of 1 directory."
                )
                return
            python_module_name = os.path.splitext(os.path.basename(file_path))[
                0
            ]
            self._dct_import_dir[dir_name].append(python_module_name)

    @staticmethod
    def check_mkdir_and_create(file_path, is_file=True):
        if is_file:
            path_dir = os.path.dirname(file_path)
        else:
            path_dir = file_path
        CodeGeneratorData.os_make_dirs(path_dir)

    def sync_code(self, directory, name):
        try:
            # if not os.path.isdir(path_sync_code):
            #     osmakedirs(path_sync_code)
            # if module.clean_before_sync_code:
            path_sync_code = os.path.join(directory, name)
            if os.path.isdir(path_sync_code):
                shutil.rmtree(path_sync_code)
            shutil.copytree(self._module_path, path_sync_code)
        except Exception as e:
            _logger.error(e)

    def generate_python_init_file(self, cg_module):
        for component, lst_module in self._dct_import_dir.items():
            init_path = os.path.join(component, "__init__.py")
            if not component:
                lst_module = [a for a in self._dct_import_dir.keys() if a]

            lst_module.sort()

            cw = CodeWriter()

            if cg_module.license == "AGPL-3":
                cw.emit(
                    "# License AGPL-3.0 or later"
                    " (https://www.gnu.org/licenses/agpl)"
                )
                cw.emit()
            elif cg_module.license == "LGPL-3":
                cw.emit(
                    "# License LGPL-3.0 or later"
                    " (https://www.gnu.org/licenses/lgpl)"
                )
                cw.emit()
            else:
                _logger.warning(f"License {cg_module.license} not supported.")

            if component:
                for module in lst_module:
                    cw.emit(f"from . import {module}")
            elif lst_module:
                cw.emit(f"from . import {', '.join(lst_module)}")
            for extra_import in self._dct_extra_module_init_path.get(
                component, []
            ):
                cw.emit(extra_import)
            self.write_file_str(init_path, cw.render())

    def flake8_check(self):
        workspace_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        flake8_bin = os.path.join(workspace_path, ".venv", "bin", "flake8")
        config_path = os.path.join(workspace_path, ".flake8")
        cpu_count = os.cpu_count()
        try:
            out = subprocess.check_output(
                [
                    flake8_bin,
                    "-j",
                    str(cpu_count),
                    f"--config={config_path}",
                    self.module_path,
                ]
            )
            result = out
        except subprocess.CalledProcessError as e:
            result = e.output.decode()

        if result:
            _logger.warning(result)

    def pylint_check(self):
        workspace_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        cpu_count = os.cpu_count()
        try:
            out = subprocess.check_output(
                [
                    f"{workspace_path}/.venv/bin/pylint",
                    "-j",
                    str(cpu_count),
                    "--load-plugins=pylint_odoo",
                    "-e",
                    "odoolint",
                    self.module_path,
                ]
            )
            result = out
        except subprocess.CalledProcessError as e:
            result = e.output.decode()

        if result:
            _logger.warning(result)

    def auto_format(self):
        workspace_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        max_col = 79
        use_prettier = True
        use_format_black = True  # Else, oca-autopep8
        use_html5print = False
        enable_xml_formatter = False  # Else, prettier-xml
        # Manual format with def with programmer style
        for path_file in self.lst_path_file:
            relative_path = path_file[len(self.module_path) + 1 :]
            if path_file.endswith(".py"):
                # TODO not optimal, too many write for nothing
                if not use_format_black:
                    lst_line_write = []
                    has_change = False
                    with open(path_file, "r") as source:
                        for line in source.readlines():
                            if (
                                line.lstrip().startswith("def ")
                                or line.lstrip().startswith("return ")
                            ) and len(line) > max_col - 1:
                                has_change = True
                                next_tab_space = line.find("(") + 1
                                first_cut = max_col
                                first_cut = line.rfind(", ", 0, first_cut) + 1
                                first_part = line[:first_cut]
                                last_part = line[first_cut:].lstrip()
                                str_line = (
                                    f"{first_part}\n{' ' * next_tab_space}{last_part}"
                                )
                                lst_line_write.append(str_line[:-1])
                            else:
                                lst_line_write.append(line[:-1])
                    if has_change:
                        self.write_file_lst_content(
                            relative_path, lst_line_write
                        )

            elif path_file.endswith(".js"):
                if use_prettier:
                    cmd = f"prettier --write --tab-width 4 {path_file}"
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)
                elif use_html5print:
                    with open(path_file, "r") as source:
                        lines = source.read()
                        try:
                            lines_out = html5print.JSBeautifier.beautify(
                                lines, 4
                            )
                            self.write_file_str(relative_path, lines_out)
                        except Exception as e:
                            _logger.error(e)
                            _logger.error(f"Check file {path_file}")
                else:
                    cmd = (
                        f"cd {workspace_path};."
                        f" .venv/bin/activate;css-html-prettify.py {path_file}"
                    )
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.warning(result)

            elif path_file.endswith(".scss") or path_file.endswith(".css"):
                if use_prettier:
                    cmd = f"prettier --write {path_file}"
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)
                elif use_html5print:
                    with open(path_file, "r") as source:
                        lines = source.read()
                        try:
                            lines_out = html5print.CSSBeautifier.beautify(
                                lines, 2
                            )
                            self.write_file_str(relative_path, lines_out)
                        except Exception as e:
                            _logger.error(e)
                            _logger.error(f"Check file {path_file}")
                else:
                    cmd = (
                        f"cd {workspace_path};."
                        f" .venv/bin/activate;css-html-prettify.py {path_file}"
                    )
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.warning(result)

            elif path_file.endswith(".html"):
                if use_prettier:
                    cmd = f"prettier --write {path_file}"
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)
                elif use_html5print:
                    with open(path_file, "r") as source:
                        lines = source.read()
                        try:
                            lines_out = html5print.HTMLBeautifier.beautify(
                                lines, 4
                            )
                            self.write_file_str(relative_path, lines_out)
                        except Exception as e:
                            _logger.error(e)
                            _logger.error(f"Check file {path_file}")
                else:
                    cmd = (
                        f"cd {workspace_path};."
                        f" .venv/bin/activate;css-html-prettify.py {path_file}"
                    )
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.warning(result)

            elif path_file.endswith(".xml"):
                if use_prettier and not enable_xml_formatter:
                    cmd = (
                        "prettier --xml-whitespace-sensitivity ignore"
                        " --prose-wrap always --tab-width 4"
                        " --no-bracket-spacing --print-width 120 --write"
                        f" {path_file}"
                    )
                    result = subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)

        # Automatic format
        # TODO check diff before and after format to auto improvement of generation
        if use_format_black:
            cmd = (
                f"cd {workspace_path};. .venv/bin/activate;black -l {max_col}"
                f" --experimental-string-processing -t py37 {self.module_path}"
            )
            result = subprocess_cmd(cmd)

            if result:
                _logger.warning(result)
        else:
            maintainer_path = os.path.join(
                workspace_path, "script", "OCA_maintainer-tools"
            )
            cpu_count = os.cpu_count()
            cmd = (
                f"cd {maintainer_path};. env/bin/activate;cd"
                f" {workspace_path};oca-autopep8 -j{cpu_count}"
                f" --max-line-length {max_col} -ari {self.module_path}"
            )
            result = subprocess_cmd(cmd)

            if result:
                _logger.warning(result)

        if enable_xml_formatter:
            formatter = xmlformatter.Formatter(
                indent="4",
                indent_char=" ",
                selfclose=True,
                correct=True,
                preserve=["pre"],
                blanks=True,
            )
            for path_file in self.lst_path_file:
                if path_file.endswith(".xml"):
                    relative_path = path_file[len(self.module_path) + 1 :]
                    self.write_file_binary(
                        relative_path, formatter.format_file(path_file)
                    )


def subprocess_cmd(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    return proc_stdout
