import glob
import logging
import os
import xml.dom.minicompat
from collections import defaultdict
from xml.dom import Node, minidom

import unidecode

_logger = logging.getLogger(__name__)


class ExtractorView:
    def __init__(self, module, model_model, number_view):
        self._module = module
        self.env = module.env
        model_name = model_model.replace(".", "_")
        self.view_ids = (
            self.env["ir.ui.view"]
            .search([("model", "=", model_model)])
            .filtered(
                lambda i: i.xml_id.startswith(
                    f"{module.template_module_name}."
                )
            )
        )
        self.code_generator_id = None
        self.model_id = self.env["ir.model"].search(
            [("model", "=", model_model)]
        )
        self.dct_model = defaultdict(dict)
        self.dct_field = defaultdict(dict)
        self.module_attr = defaultdict(dict)
        self.var_model_name = f"model_{model_name}"
        self.var_model = model_model
        if self.view_ids:
            # create temporary module
            name = f"TEMP_{model_name}"
            i = 1
            while self.env["code.generator.module"].search(
                [("name", "=", name)]
            ):
                name = f"TEMP_{i}_{model_name}"
                i += 1
            value = {
                "name": name,
                "shortdesc": "None",
            }
            self.code_generator_id = self.env["code.generator.module"].create(
                value
            )
            self._parse_view_ids()
            if number_view == 0:
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
                        record_id = dict(record.attributes.items()).get("id")
                        if not record_id:
                            _logger.warning(
                                "Missing id when searching ir.actions.server."
                            )
                            continue
                        xml_id = f"{module.template_module_name}.{record_id}"
                        result = self.env.ref(xml_id, raise_if_not_found=False)
                        if result:
                            result.comment = last_record.data.strip()

    def _parse_menu(self):
        ir_model_data_ids = self.env["ir.model.data"].search(
            [
                ("model", "=", "ir.ui.menu"),
                ("module", "=", self._module.template_module_name),
            ]
        )
        if not ir_model_data_ids:
            return
        lst_id_menu = [a.res_id for a in ir_model_data_ids]
        menu_ids = self.env["ir.ui.menu"].browse(lst_id_menu)
        for menu_id in menu_ids:

            # TODO optimise request ir.model.data, this is duplicated
            menu_action = None
            if menu_id.action:
                # Create act_window
                menu_data_id = self.env["ir.model.data"].search(
                    [
                        ("model", "=", "ir.actions.act_window"),
                        ("res_id", "=", menu_id.action.id),
                    ]
                )
                menu_name = unidecode.unidecode(menu_data_id.name)
                dct_act_value = {
                    "id_name": menu_name,
                    "name": menu_id.action.name,
                    "code_generator_id": self.code_generator_id.id,
                }
                if menu_id.action.res_model:
                    dct_act_value["model_name"] = menu_id.action.res_model
                menu_action = self.env["code.generator.act_window"].create(
                    dct_act_value
                )
            # Create menu
            menu_data_id = self.env["ir.model.data"].search(
                [("model", "=", "ir.ui.menu"), ("res_id", "=", menu_id.id)]
            )
            menu_name = unidecode.unidecode(menu_data_id.name)
            dct_menu_value = {
                "code_generator_id": self.code_generator_id.id,
                "id_name": menu_name,
            }
            if menu_id.name:
                dct_menu_value["name"] = menu_id.name
            if menu_id.web_icon:
                dct_menu_value["web_icon"] = menu_id.web_icon
            dct_menu_value["sequence"] = menu_id.sequence
            if menu_id.parent_id:
                menu_data_parent_id = self.env["ir.model.data"].search(
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
            else:
                dct_menu_value["ignore_act_window"] = True

            self.env["code.generator.menu"].create(dct_menu_value)
            # If need to associated
            # menu_id.m2o_module = self._module.id

    def _parse_view_ids(self):
        for view_id in self.view_ids:
            mydoc = minidom.parseString(view_id.arch_base.encode())

            lst_view_item_id = []

            dct_view_attr = {}

            # Search graph
            lst_graph_xml = mydoc.getElementsByTagName("graph")
            if lst_graph_xml:
                if len(lst_graph_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple graph in view name"
                        f" {view_id.name}"
                    )
                else:
                    graph_view = lst_graph_xml[0]
                    dct_view_attr.update(dict(graph_view.attributes.items()))

            # Search search
            lst_search_xml = mydoc.getElementsByTagName("search")
            if lst_search_xml:
                if len(lst_search_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple search in view name"
                        f" {view_id.name}"
                    )
                else:
                    search_view = lst_search_xml[0]
                    dct_view_attr.update(dict(search_view.attributes.items()))

            # Search pivot
            lst_pivot_xml = mydoc.getElementsByTagName("pivot")
            if lst_pivot_xml:
                if len(lst_pivot_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple pivot in view name"
                        f" {view_id.name}"
                    )
                else:
                    pivot_view = lst_pivot_xml[0]
                    dct_view_attr.update(dict(pivot_view.attributes.items()))

            # Search kanban
            lst_kanban_xml = mydoc.getElementsByTagName("kanban")
            if lst_kanban_xml:
                if len(lst_kanban_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple kanban in view name"
                        f" {view_id.name}"
                    )
                else:
                    kanban_view = lst_kanban_xml[0]
                    dct_view_attr.update(dict(kanban_view.attributes.items()))

            # Search form
            lst_form_xml = mydoc.getElementsByTagName("form")
            if lst_form_xml:
                if len(lst_form_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple form in view name"
                        f" {view_id.name}"
                    )
                else:
                    form_view = lst_form_xml[0]
                    dct_view_attr.update(dict(form_view.attributes.items()))
                sequence_form = 10
                lst_form_field_xml = mydoc.getElementsByTagName("field")
                for field_xml in lst_form_field_xml:
                    field_name = dict(field_xml.attributes.items()).get("name")
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
                if len(lst_tree_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple tree in view name"
                        f" {view_id.name}"
                    )
                else:
                    tree_view = lst_tree_xml[0]
                    dct_view_attr.update(dict(tree_view.attributes.items()))
                sequence_tree = 10
                lst_tree_field_xml = mydoc.getElementsByTagName("field")
                for field_xml in lst_tree_field_xml:
                    field_name = dict(field_xml.attributes.items()).get("name")
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
                if len(lst_timeline_xml) != 1:
                    _logger.warning(
                        "Cannot support multiple timeline in view name"
                        f" {view_id.name}"
                    )
                else:
                    timeline_view = lst_timeline_xml[0]
                    dct_view_attr.update(
                        dict(timeline_view.attributes.items())
                    )
                for timeline_xml in lst_timeline_xml:
                    if "date_start" in timeline_xml.attributes.keys():
                        del dct_view_attr["date_start"]
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
                        del dct_view_attr["date_stop"]
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
                            "Cannot support multiple diagram in the same file."
                        )
                        continue
                    # Search 1 node, 1 arrow and maybe 1 label
                    find_node = False
                    find_arrow = False
                    find_label = False
                    node_object = None
                    node_xpos = None
                    node_ypos = None
                    node_shape = None
                    node_form_view_ref = None
                    arrow_object = None
                    arrow_source = None
                    arrow_destination = None
                    diagram_label_string = None
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
                                arrow_destination = dct_att.get("destination")
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
                                diagram_label_string = dct_att.get("string")
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
                        self.model_id.diagram_arrow_src_field = arrow_source
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

            # Search footer
            footer_xml = None
            no_sequence = 1
            lst_footer_xml = mydoc.getElementsByTagName("footer")
            if len(lst_footer_xml) > 1:
                _logger.warning("Cannot support multiple footer.")
            for footer_xml in lst_footer_xml:
                # TODO get inside attributes for footer
                for child_footer in footer_xml.childNodes:
                    if child_footer.nodeType is Node.TEXT_NODE:
                        data = child_footer.data.strip()
                        if data:
                            _logger.warning("Not supported.")
                    elif child_footer.nodeType is Node.ELEMENT_NODE:
                        self._extract_child_xml(
                            child_footer,
                            lst_view_item_id,
                            "footer",
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
                                view_item_id = self.env[
                                    "code.generator.view.item"
                                ].create(dct_attributes)
                                lst_view_item_id.append(view_item_id.id)
                                no_sequence += 1

            lst_body_xml = []
            lst_tag_support = list(
                dict(
                    self.env["code.generator.view"]
                    ._fields["view_type"]
                    .selection
                ).keys()
            )
            lst_tag_support_xpath = ["xpath"]
            lst_content = [
                b
                for a in lst_tag_support
                for b in mydoc.getElementsByTagName(a)
            ]
            lst_content_xpath = [
                b
                for a in lst_tag_support_xpath
                for b in mydoc.getElementsByTagName(a)
            ]
            has_content = any(lst_content + lst_content_xpath)
            if not has_content:
                _logger.warning(
                    "Cannot find a xml type from list:"
                    f" {lst_tag_support + lst_tag_support_xpath}."
                )
            elif len(lst_content) > 1:
                _logger.warning(f"Cannot support multiple {lst_content}.")
            elif lst_content_xpath:
                lst_body_xml = lst_content_xpath
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
                            or child_form == footer_xml
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
                        # TODO why cumulate here when change value in lst_sheet_xml next lines
                        lst_body_xml.append(child_form)

            if lst_sheet_xml:
                # TODO validate this, test with and without <sheet>
                if type(lst_sheet_xml) is xml.dom.minicompat.NodeList:
                    lst_body_xml = [
                        a
                        for a in lst_sheet_xml[0].childNodes
                        if a != footer_xml
                    ]
                else:
                    lst_body_xml = [
                        a for a in lst_sheet_xml.childNodes if a != footer_xml
                    ]
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
                "view_name": view_id.name,
                # "m2o_model": model_db_backup.id,
                "view_item_ids": [(6, 0, lst_view_item_id)],
                "has_body_sheet": has_body_sheet,
            }

            # Update attributes
            lst_view_attr_copy = list(dct_view_attr.keys())[:]
            if "string" in dct_view_attr.keys():
                value["view_attr_string"] = dct_view_attr.get("string")
                lst_view_attr_copy.remove("string")
            if "class" in dct_view_attr.keys():
                value["view_attr_class"] = dct_view_attr.get("class")
                lst_view_attr_copy.remove("class")
            if "default_group_by" in dct_view_attr.keys():
                # TODO support it in parameter of timeline view
                # Ignore it, from timeline
                lst_view_attr_copy.remove("default_group_by")
            if "event_open_popup" in dct_view_attr.keys():
                # TODO support it in parameter of timeline view
                # Ignore it, from timeline
                lst_view_attr_copy.remove("event_open_popup")
            if lst_view_attr_copy:
                _logger.warning(
                    "Not support multiple attr dct view, keys:"
                    f" {lst_view_attr_copy}"
                )

            # ID and inherit ID
            inherit_view_name = None
            if view_id.inherit_id:
                if not view_id.inherit_id.model_data_id:
                    _logger.error(
                        "Missing model data id of inherit id view_name"
                        f" {view_id.name}"
                    )
                else:
                    inherit_view_name = (
                        view_id.inherit_id.model_data_id.complete_name
                    )
                    value["inherit_view_name"] = inherit_view_name
            if view_id.model_data_id:
                id_name = view_id.model_data_id.name
                if (
                    inherit_view_name is None
                    or id_name != inherit_view_name.split(".")[1]
                ):
                    value["id_name"] = view_id.model_data_id.name
            else:
                _logger.error(
                    f"Missing model data id view_name {view_id.name}"
                )

            view_code_generator = self.env["code.generator.view"].create(value)

    def _extract_child_xml(
        self,
        node,
        lst_view_item_id,
        section_type,
        lst_node=None,
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

        for key, value in node.attributes.items():
            if key == "t-name":
                dct_attributes["t_name"] = value
            elif key == "t-attf-class":
                dct_attributes["t_attf_class"] = value
            elif key == "t-if":
                dct_attributes["t_if"] = value
            elif key == "title":
                dct_attributes["title"] = value
            elif key == "aria-label":
                dct_attributes["aria_label"] = value
            elif key == "role":
                dct_attributes["role"] = value
            elif key == "name":
                dct_attributes["name"] = value
            elif key == "widget":
                dct_attributes["widget"] = value
            elif key == "domain":
                dct_attributes["domain"] = value
            elif key == "context":
                dct_attributes["context"] = value
            elif key == "class":
                dct_attributes["class_attr"] = value
            elif key == "string":
                dct_attributes["label"] = value

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
                    if key == "class":
                        if value in lst_key_html_class:
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
                elif key == "widget":
                    field_name = dict(node.attributes.items()).get("name")
                    # TODO update dict instead of overwrite it
                    self.module_attr[self.var_model][field_name] = {
                        "force_widget": value
                    }
                elif key == "placeholder":
                    dct_attributes["placeholder"] = value
                elif key == "name":
                    dct_attributes["name"] = value
                elif key == "type":
                    dct_attributes["type"] = value
        elif node.nodeName in ("xpath",):
            for key, value in node.attributes.items():
                if key == "expr":
                    dct_attributes["expr"] = value
                elif key == "position":
                    dct_attributes["position"] = value
        elif node.nodeName == "separator":
            # Accumulate nodes
            return True
        elif node.nodeName == "templates":
            _logger.warning(f"Node template is not supported, ignore it.")
            return
        elif node.nodeName in ("node", "arrow", "label"):
            # Ignore it, this is the diagram, it's supported somewhere else
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
        if "button_type" in dct_attributes.keys():
            button_type_value = dct_attributes.get("button_type")
            if " " in button_type_value:
                # TODO cannot support multiple type, because of limitation of button_type = fields.Selection()
                # patch, workaround
                if "btn-primary" in button_type_value:
                    dct_attributes["button_type"] = "btn-primary"
                elif "btn-secondary" in button_type_value:
                    dct_attributes["button_type"] = "btn-secondary"
                else:
                    _logger.warning(
                        "Cannot support multiple value in button_type, value"
                        f" : {button_type_value}"
                    )
        view_item_id = self.env["code.generator.view.item"].create(
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
