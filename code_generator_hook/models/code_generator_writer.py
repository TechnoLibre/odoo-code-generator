from odoo import models, fields, api

from xml.dom import minidom, Node
from code_writer import CodeWriter
from odoo.models import MAGIC_COLUMNS

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
    "name",
]
BREAK_LINE = ["\n"]
FROM_ODOO_IMPORTS_SUPERUSER = ["from odoo import _, api, models, fields, SUPERUSER_ID"]
MODEL_SUPERUSER_HEAD = FROM_ODOO_IMPORTS_SUPERUSER + BREAK_LINE


class Struct(object):
    def __init__(self, **entries):
        self.__dict__.update(entries)


import logging
import ast
import glob
import os

_logger = logging.getLogger(__name__)


class ExtractorView:
    def __init__(self, module, model_model):
        self._module = module
        self.view_ids = module.env["ir.ui.view"].search([("model", "=", model_model)])
        self.code_generator_id = None
        model_name = model_model.replace(".", "_")
        self.var_model_name = f"model_{model_name}"
        if self.view_ids:
            # create temporary module
            value = {
                "name": f"TEMP_{model_name}",
                "shortdesc": "None",
            }
            self.code_generator_id = module.env["code.generator.module"].create(value)
            self._parse_view_ids()

    def _parse_view_ids(self):
        for view_id in self.view_ids:
            mydoc = minidom.parseString(view_id.arch_base.encode())

            lst_view_item_id = []

            # Sheet
            lst_sheet_xml = mydoc.getElementsByTagName("sheet")
            has_body_sheet = bool(lst_sheet_xml)
            sheet_xml = lst_sheet_xml[0] if lst_sheet_xml else None
            if len(lst_sheet_xml) > 1:
                _logger.warning("Cannot support multiple <sheet>.")

            # Search header
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
                            child_header, lst_view_item_id, "header", sequence=no_sequence
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
                            _logger.warning("Cannot support multiple class oe_title.")
                            continue
                        # TODO support multiple element in title
                        lst_field = div_xml.getElementsByTagName("field")
                        if not lst_field:
                            _logger.warning("Not supported title without field, TODO.")
                        elif len(lst_field) > 1:
                            _logger.warning("Not supported title without multiple field, TODO.")
                        else:
                            dct_field_attrs = dict(
                                div_xml.getElementsByTagName("field")[0].attributes.items()
                            )
                            name = dct_field_attrs.get("name")
                            if not name:
                                _logger.warning("Cannot identify field type in title.")
                            else:
                                dct_attributes = {
                                    "action_name": name,
                                    "section_type": "title",
                                    "item_type": "field",
                                    "sequence": no_sequence,
                                }
                                view_item_id = self._module.env["code.generator.view.item"].create(
                                    dct_attributes
                                )
                                lst_view_item_id.append(view_item_id.id)
                                no_sequence += 1

            lst_body_xml = []
            # Detect
            lst_form_xml = mydoc.getElementsByTagName("form")
            lst_search_xml = mydoc.getElementsByTagName("search")
            lst_tree_xml = mydoc.getElementsByTagName("tree")
            lst_content = lst_form_xml + lst_search_xml + lst_tree_xml
            if not lst_content:
                _logger.warning("Cannot find <form>.")
            elif len(lst_content) > 1:
                _logger.warning("Cannot support multiple <form>/<tree>/<search.")
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
                        if has_body_sheet:
                            _logger.warning("How can find body xml outside of his sheet?")
                        else:
                            lst_body_xml.append(child_form)

            if lst_sheet_xml:
                lst_body_xml = [a for a in lst_sheet_xml.childNodes]
            sequence = 1
            lst_node = []
            for body_xml in lst_body_xml:
                if body_xml.nodeType is Node.TEXT_NODE:
                    data = body_xml.data.strip()
                    if data:
                        _logger.warning("Not supported.")
                elif body_xml.nodeType is Node.ELEMENT_NODE:
                    status = self._extract_child_xml(
                        body_xml, lst_view_item_id, "body", lst_node=lst_node, sequence=sequence
                    )
                    if status:
                        lst_node.append(body_xml)
                    else:
                        lst_node = []
                    sequence += 1
            if lst_node:
                _logger.warning("Missing node in buffer.")

            view_code_generator = self._module.env["code.generator.view"].create(
                {
                    "code_generator_id": self.code_generator_id.id,
                    "view_type": view_id.type,
                    # "view_name": "view_backup_conf_form",
                    # "m2o_model": model_db_backup.id,
                    "view_item_ids": [(6, 0, lst_view_item_id)],
                    "has_body_sheet": has_body_sheet,
                }
            )

    def _extract_child_xml(
        self, node, lst_view_item_id, section_type, lst_node=[], parent=None, sequence=1
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
        dct_key_keep = {"name": "action_name", "string": "label", "attrs": "attrs"}
        dct_attributes = {
            "section_type": section_type,
            "item_type": node.nodeName,
            "sequence": sequence,
        }

        if parent:
            dct_attributes["parent_id"] = parent.id

        if node.nodeName in ("group", "div"):
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
        elif node.nodeName == "field":
            for key, value in node.attributes.items():
                if key == "password":
                    dct_attributes["password"] = value
                if key == "placeholder":
                    dct_attributes["placeholder"] = value
        elif node.nodeName == "separator":
            # Accumulate nodes
            return True
        else:
            _logger.warning(f"Unknown this case '{node.nodeName}'.")
            return

        # TODO use external function to get attributes items to remove duplicate code, search "node.attributes.items()"
        for key, value in node.attributes.items():
            attributes_name = dct_key_keep.get(key)
            if attributes_name:
                dct_attributes[attributes_name] = value
        # TODO validate dct_attributes has all needed key with dct_key_keep (except button_type)
        view_item_id = self._module.env["code.generator.view.item"].create(dct_attributes)
        lst_view_item_id.append(view_item_id.id)
        sequence += 1

        # Child, except HTML
        if dct_attributes["item_type"] != "html":
            child_sequence = 1
            for child in node.childNodes:
                if child.nodeType is Node.TEXT_NODE:
                    data = child.data.strip()
                    if data:
                        _logger.warning("Not supported.")
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
    def __init__(self, module, model_model):
        self.is_enabled = False
        self.working_directory = module.path_sync_code
        self.model = model_model
        self.dct_model = {}
        self.py_filename = ""
        if not module.template_module_path_generated_extension:
            return
        relative_path_generated_module = module.template_module_path_generated_extension.replace(
            "'", ""
        ).replace(", ", "/")
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
        for py_file in lst_py_file:
            filename = py_file.split("/")[-1]
            if filename == "__init__.py":
                continue
            with open(py_file, "r") as source:
                f_ast = ast.parse(source.read())
                class_model_ast = self.search_class_model(f_ast)
                if class_model_ast:
                    self.py_filename = filename
                    break
        if class_model_ast:
            self.search_field(class_model_ast)
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

    def _fill_search_field(self, ast_obj, var_name):
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
            lst_value = [self._fill_search_field(a, var_name) for a in ast_obj.elts]
            result = lst_value
        elif ast_obj_type is ast.Tuple:
            lst_value = [self._fill_search_field(a, var_name) for a in ast_obj.elts]
            result = tuple(lst_value)
        else:
            # TODO missing ast.Dict?
            result = None
            _logger.error(
                f"Cannot support keyword of variable {var_name} type {ast_obj_type} in filename "
                f"{self.py_filename}."
            )
        return result

    def search_field(self, class_model_ast):
        dct_field = {}
        self.dct_model[self.model] = dct_field
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
                    "sequence": sequence,
                }
                for keyword in node.value.keywords:
                    value = self._fill_search_field(keyword.value, var_name)
                    # Waste to stock None value
                    if value is not None:
                        d[keyword.arg] = value

                dct_field[var_name] = d


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def set_module_init_file_extra(self, module):
        super(CodeGeneratorWriter, self).set_module_init_file_extra(module)
        if module.pre_init_hook_show or module.post_init_hook_show or module.uninstall_hook_show:
            lst_import = []
            if module.pre_init_hook_show:
                lst_import.append("pre_init_hook")
            if module.post_init_hook_show:
                lst_import.append("post_init_hook")
            if module.uninstall_hook_show:
                lst_import.append("uninstall_hook")
            # Specify root component
            self.code_generator_data.add_module_init_path(
                "", f'from .hooks import {", ".join(lst_import)}'
            )

    def set_manifest_file_extra(self, cw, module):
        super(CodeGeneratorWriter, self).set_manifest_file_extra(cw, module)
        if module.pre_init_hook_show:
            cw.emit(f"'pre_init_hook': 'pre_init_hook',")

        if module.post_init_hook_show:
            cw.emit(f"'post_init_hook': 'post_init_hook',")

        if module.uninstall_hook_show:
            cw.emit(f"'uninstall_hook': 'uninstall_hook',")

    def _write_generated_template(self, module, model_model, cw):
        pass

    def _write_sync_template_model(
        self,
        module,
        model_model,
        cw,
        var_model_model,
        lst_keep_f2exports,
        module_file_sync,
        lst_force_f2exports=None,
    ):
        if module_file_sync and module_file_sync.is_enabled:
            dct_field_ast = module_file_sync.dct_model.get(model_model)
        else:
            dct_field_ast = {}
        lst_ignored_field = module.ignore_fields.split(";") if module.ignore_fields else []
        # TODO Check name is different before ignored it
        if lst_force_f2exports:
            f2exports = lst_force_f2exports
        else:
            if lst_ignored_field:
                lst_ignored_field += MAGIC_FIELDS
            else:
                lst_ignored_field = MAGIC_FIELDS
            if "name" in dct_field_ast.keys():
                lst_ignored_field.remove("name")
            lst_search = [("model", "=", model_model), ("name", "not in", lst_ignored_field)]
            f2exports = self.env["ir.model.fields"].search(lst_search)

        dct_var_id_view = {}
        has_field_name = False
        for field_id in f2exports:
            if not lst_force_f2exports and field_id.ttype == "one2many":
                # TODO refactor, simplify this with a struct
                lst_keep_f2exports.append((field_id, model_model, var_model_model))
                continue

            if field_id.name == "name":
                has_field_name = True

            var_value_field_name = f"value_field_{field_id.name}"
            var_id_view = f"{var_model_model}_field_{field_id.name}_id"
            dct_var_id_view[var_id_view] = field_id

            ast_attr = dct_field_ast.get(field_id.name)
            with cw.block(before=f"{var_value_field_name} =", delim=("{", "}")):
                cw.emit(f'"name": "{field_id.name}",')
                cw.emit(f'"model": "{model_model}",')
                cw.emit(f'"field_description": "{field_id.field_description}",')
                if ast_attr:
                    cw.emit(f'"code_generator_sequence": {ast_attr.get("sequence")},')
                cw.emit(f'"ttype": "{field_id.ttype}",')
                if field_id.ttype in ["many2one", "many2many", "one2many"]:
                    cw.emit(f'"comodel_name": "{field_id.relation}",')
                    cw.emit(f'"relation": "{field_id.relation}",')
                    if field_id.ttype == "one2many":
                        field_many2one_ids = self.env["ir.model.fields"].search(
                            [
                                ("model", "=", field_id.relation),
                                ("ttype", "=", "many2one"),
                                ("name", "not in", MAGIC_FIELDS),
                            ]
                        )
                        if len(field_many2one_ids) == 1:
                            cw.emit(f'"relation_field": "{field_many2one_ids.name}",')
                        else:
                            _logger.error("Cannot support this situation, where is the many2one?")
                elif field_id.ttype == "selection":
                    field_selection = (
                        self.env[model_model].fields_get(field_id.name).get(field_id.name)
                    )
                    cw.emit(f'"selection": "{str(field_selection.get("selection"))}",')
                cw.emit(f'"model_id": {var_model_model}.id,')
                field_default = ast_attr.get("default") if ast_attr else None
                if field_default:
                    if field_id.ttype in ("char", "selection"):
                        cw.emit(f'"default": "{field_default}",')
                    else:
                        cw.emit(f'"default": {field_default},')
                # field_id.compute always output False, use ast research instead
                compute = ast_attr.get("compute") if ast_attr else None
                if compute:
                    if field_id.store:
                        cw.emit(f'"store": {field_id.store},')
                    cw.emit(f'"code_generator_compute": "{compute}",')
                if field_id.required:
                    cw.emit(f'"required": {field_id.required},')
                if field_id.help:
                    cw.emit(f'"help": "{field_id.help}",')
            # If need a variable, uncomment next line
            # cw.emit(f'{var_id_view} = env["ir.model.fields"].create({var_value_field_name})')
            cw.emit(f'env["ir.model.fields"].create({var_value_field_name})')
            cw.emit()

        if lst_force_f2exports:
            lst_force_f2exports.clear()
        elif f2exports:
            cw.emit("# Hack to solve field name")
            cw.emit(
                f'field_x_name = env["ir.model.fields"].search([("model_id", "=", {var_model_model}.id), '
                f'("name", "=", "x_name")])'
            )
            if has_field_name:
                cw.emit("field_x_name.unlink()")
            else:
                cw.emit('field_x_name.name = "name"')
            cw.emit(f'{var_model_model}.rec_name = "name"')

    def _write_sync_view_component(self, view_item_ids, cw, parent=None):
        for view_item_id in view_item_ids:
            # TODO view_item can be duplicated, use unique name
            var_create_view_item = (
                "view_item"
                if not view_item_id.child_id
                else f"view_item_{view_item_id.section_type}_{view_item_id.sequence}"
            )
            with cw.block(
                before=f'{var_create_view_item} = env["code.generator.view.item"].create',
                delim=("(", ")"),
            ):
                with cw.block(delim=("{", "}")):
                    cw.emit(f'"section_type": "{view_item_id.section_type}",')
                    cw.emit(f'"item_type": "{view_item_id.item_type}",')
                    if view_item_id.item_type == "button":
                        cw.emit(f'"action_name": "{view_item_id.action_name}",')
                        if view_item_id.button_type:
                            cw.emit(f'"button_type": "{view_item_id.button_type}",')
                        if view_item_id.icon:
                            cw.emit(f'"icon": "{view_item_id.icon}",')
                    elif view_item_id.item_type == "field":
                        cw.emit(f'"action_name": "{view_item_id.action_name}",')
                        if view_item_id.placeholder:
                            cw.emit(f'"placeholder": "{view_item_id.placeholder}",')
                        if view_item_id.password:
                            cw.emit(f'"password": {view_item_id.password},')
                    elif view_item_id.item_type in ("group", "div"):
                        if view_item_id.attrs:
                            cw.emit(f'"attrs": "{view_item_id.attrs}",')
                    elif view_item_id.item_type == "html":
                        # TODO support help and type bg-warning
                        if view_item_id.colspan != 1:
                            cw.emit(f'"colspan": {view_item_id.colspan},')
                        if view_item_id.background_type:
                            cw.emit(f'"background_type": "{view_item_id.background_type}",')

                    if view_item_id.label:
                        if "\n" in view_item_id.label:
                            cw.emit('"label": """')
                            for label in view_item_id.label.split("\n"):
                                cw.emit(label)
                            cw.emit('""",')
                        else:
                            cw.emit(f'"label": "{view_item_id.label}",')
                    if view_item_id.is_help:
                        cw.emit(f'"is_help": {view_item_id.is_help},')

                    if parent:
                        cw.emit(f'"parent_id": {parent}.id,')
                    cw.emit(f'"sequence": {view_item_id.sequence},')

            cw.emit(f"lst_item_view.append({var_create_view_item}.id)")
            cw.emit()

            if view_item_id.child_id:
                self._write_sync_view_component(
                    view_item_id.child_id, cw, parent=var_create_view_item
                )

    def _write_sync_template_views(self, cw, view_item):
        if not view_item.code_generator_id:
            return
        code_generator_views_id = view_item.code_generator_id.code_generator_views_id
        form_view_ids = code_generator_views_id.filtered(
            lambda view_id: view_id.view_type == "form"
        )
        search_view_ids = code_generator_views_id.filtered(
            lambda view_id: view_id.view_type == "search"
        )
        cw.emit("lst_view_id = []")
        cw.emit("# form view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("lst_item_view = []")

            for form_view_id in form_view_ids:
                tpl_ordered_section = ("header", "title", "body")
                tpl_available_section = form_view_id.view_item_ids.mapped("section_type")
                s = set(tpl_available_section)
                lst_section = [x for x in tpl_ordered_section if x in s]

                for section in lst_section:
                    cw.emit(f"# {section.upper()}")
                    view_item_ids = form_view_id.view_item_ids.filtered(
                        lambda field: field.section_type == section and not field.parent_id
                    )

                    self._write_sync_view_component(view_item_ids, cw)

                cw.emit('view_code_generator = env["code.generator.view"].create(')
                with cw.block(delim=("{", "}")):
                    cw.emit('"code_generator_id": code_generator_id.id,')
                    cw.emit('"view_type": "form",')
                    cw.emit(f'# "view_name": "view_backup_conf_form",')
                    cw.emit(f'"m2o_model": {view_item.var_model_name}.id,')
                    cw.emit('"view_item_ids": [(6, 0, lst_item_view)],')
                    cw.emit(f'"has_body_sheet": {form_view_id.has_body_sheet},')
                cw.emit(")")
                cw.emit("lst_view_id.append(view_code_generator.id)")
        cw.emit()
        cw.emit("# tree view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("pass")
        cw.emit()
        cw.emit("# search view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("pass")
        cw.emit()
        cw.emit("# act_window view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("pass")
        cw.emit()
        cw.emit("# action_server view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("pass")
        cw.emit()
        cw.emit("# menu view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("pass")

        # TODO implement portal
        # cw.emit()
        # cw.emit('# portal view')
        # cw.emit('if True:')
        # with cw.indent():
        #     cw.emit("pass")

        # TODO implement website
        # cw.emit()
        # cw.emit('# website view')
        # cw.emit('if True:')
        # with cw.indent():
        #     cw.emit("pass")

    def _set_hook_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()
        lst_keep_f2exports = []

        for line in MODEL_SUPERUSER_HEAD:
            str_line = line.strip()
            cw.emit(str_line)

        is_generator_demo = module.name == "code_generator_demo"

        # Add constant
        if module.hook_constant_code:
            if module.enable_template_code_generator_demo:
                cw.emit(
                    "# TODO HUMAN: change my module_name to create a specific demo functionality"
                )
            for line in module.hook_constant_code.split("\n"):
                cw.emit(line)

        def _add_hook(
            cw,
            hook_show,
            hook_code,
            hook_feature_gen_conf,
            post_init_hook_feature_code_generator,
            uninstall_hook_feature_code_generator,
            method_name,
            has_second_arg,
        ):
            if hook_show:
                cw.emit()
                cw.emit()
                if has_second_arg:
                    cw.emit(f"def {method_name}(cr, e):")
                else:
                    cw.emit(f"def {method_name}(cr):")
                with cw.indent():
                    for line in hook_code.split("\n"):
                        cw.emit(line)
                    if hook_feature_gen_conf:
                        with cw.indent():
                            cw.emit("# General configuration")
                            with cw.block(before="values =", delim=("{", "}")):
                                pass

                            cw.emit(
                                "event_config = env['res.config.settings'].sudo().create(values)"
                            )
                            cw.emit("event_config.execute()")
                    if post_init_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit()
                            cw.emit("# The path of the actual file")
                            if module.template_module_path_generated_extension:
                                cw.emit(
                                    "path_module_generate = os.path.normpath(os.path.join(os.path.dirname"
                                    f"(__file__), '..', {module.template_module_path_generated_extension}))"
                                )
                            else:
                                cw.emit(
                                    "# path_module_generate = os.path.normpath(os.path.join(os.path.dirname"
                                    "(__file__), '..'))"
                                )
                            cw.emit()
                            cw.emit('short_name = MODULE_NAME.replace("_", " ").title()')
                            cw.emit()
                            cw.emit("# Add code generator")
                            cw.emit("value = {")
                            with cw.indent():
                                cw.emit('"shortdesc": short_name,')
                                cw.emit('"name": MODULE_NAME,')
                                cw.emit('"license": "AGPL-3",')
                                cw.emit('"author": "TechnoLibre",')
                                cw.emit('"website": "https://technolibre.ca",')
                                cw.emit('"application": True,')
                                # with cw.block(before='"depends" :', delim=('[', '],')):
                                #     cw.emit('"code_generator",')
                                #     cw.emit('"code_generator_hook",')
                                cw.emit('"enable_sync_code": True,')
                                if module.template_module_path_generated_extension:
                                    cw.emit('"path_sync_code": path_module_generate,')
                                else:
                                    cw.emit('# "path_sync_code": path_module_generate,')
                            cw.emit("}")
                            cw.emit()
                            cw.emit("# TODO HUMAN: enable your functionality to generate")
                            enable_template_code_generator_demo = (
                                module.enable_template_code_generator_demo
                                if module.name == "code_generator_demo"
                                else False
                            )
                            if module.enable_template_code_generator_demo:
                                cw.emit(
                                    'value["enable_template_code_generator_demo"] = '
                                    f"{enable_template_code_generator_demo}"
                                )
                                cw.emit('value["template_model_name"] = ""')
                                cw.emit('value["enable_template_wizard_view"] = False')
                                cw.emit(
                                    'value["enable_template_website_snippet_view"] = '
                                    f"{module.enable_template_website_snippet_view}"
                                )
                            elif module.enable_template_website_snippet_view:
                                cw.emit('value["enable_generate_website_snippet"] = True')
                                cw.emit(
                                    'value["enable_generate_website_snippet_javascript"] = True'
                                )
                                cw.emit(
                                    'value["generate_website_snippet_type"] = "effect"'
                                    "  # content,effect,feature,structure"
                                )
                            cw.emit(
                                f'value["enable_sync_template"] = {module.enable_sync_template}'
                            )
                            cw.emit(f'value["ignore_fields"] = ""')
                            cw.emit(
                                f'value["post_init_hook_show"] = {module.enable_template_code_generator_demo}'
                            )
                            cw.emit(
                                f'value["uninstall_hook_show"] = {module.enable_template_code_generator_demo}'
                            )
                            cw.emit(
                                'value["post_init_hook_feature_code_generator"] = '
                                f"{module.enable_template_code_generator_demo}"
                            )
                            cw.emit(
                                'value["uninstall_hook_feature_code_generator"] = '
                                f"{module.enable_template_code_generator_demo}"
                            )
                            cw.emit()
                            if module.enable_template_code_generator_demo:
                                cw.emit("new_module_name = MODULE_NAME")
                                cw.emit(
                                    'if MODULE_NAME != "code_generator_demo" and "code_generator_" in MODULE_NAME:'
                                )
                                with cw.indent():
                                    cw.emit('if "code_generator_template" in MODULE_NAME:')
                                    with cw.indent():
                                        cw.emit('if value["enable_template_code_generator_demo"]:')
                                        with cw.indent():
                                            cw.emit(
                                                'new_module_name = f"code_generator_{MODULE_NAME['
                                                "len('code_generator_template_'):]}\""
                                            )
                                        cw.emit("else:")
                                        with cw.indent():
                                            cw.emit(
                                                'new_module_name = MODULE_NAME[len("code_generator_template_"):]'
                                            )
                                    cw.emit("else:")
                                    with cw.indent():
                                        cw.emit(
                                            'new_module_name = MODULE_NAME[len("code_generator_"):]'
                                        )
                                    cw.emit('value["template_module_name"] = new_module_name')
                                cw.emit(
                                    'value["hook_constant_code"] = f\'MODULE_NAME = "{new_module_name}"\''
                                )
                            else:
                                cw.emit(
                                    'value["hook_constant_code"] = f\'MODULE_NAME = "{MODULE_NAME}"\''
                                )
                            cw.emit()
                            cw.emit(
                                'code_generator_id = env["code.generator.module"].create(value)'
                            )
                            cw.emit()
                            if module.dependencies_template_id:
                                cw.emit("# Add dependencies")
                                cw.emit("# TODO HUMAN: update your dependencies")
                                with cw.block(before="lst_depend =", delim=("[", "]")):
                                    for depend in module.dependencies_template_id:
                                        cw.emit(f'"{depend.depend_id.name}",')
                                cw.emit(
                                    'lst_dependencies = env["ir.module.module"]'
                                    '.search([("name", "in", lst_depend)])'
                                )
                                cw.emit("for depend in lst_dependencies:")
                                with cw.indent():
                                    with cw.block(before="value =", delim=("{", "}")):
                                        cw.emit('"module_id": code_generator_id.id,')
                                        cw.emit('"depend_id": depend.id,')
                                        cw.emit('"name": depend.display_name,')
                                    cw.emit('env["code.generator.module.dependency"].create(value)')
                                cw.emit()
                                if is_generator_demo:
                                    with cw.block(before="lst_depend =", delim=("[", "]")):
                                        for depend in module.dependencies_template_id:
                                            cw.emit(f'"{depend.depend_id.name}",')
                                    cw.emit(
                                        'lst_dependencies = env["ir.module.module"]'
                                        '.search([("name", "in", lst_depend)])'
                                    )
                                    cw.emit("for depend in lst_dependencies:")
                                    with cw.indent():
                                        with cw.block(before="value =", delim=("{", "}")):
                                            cw.emit('"module_id": code_generator_id.id,')
                                            cw.emit('"depend_id": depend.id,')
                                            cw.emit('"name": depend.display_name,')
                                        cw.emit(
                                            'env["code.generator.module.template.dependency"].create(value)'
                                        )
                                    cw.emit()

                            lst_view_item_code_generator = []
                            if module.template_model_name:
                                lst_model = module.template_model_name.split(";")
                                len_model = len(lst_model)
                                i = -1
                                for model_model in lst_model:
                                    i += 1
                                    model_name = model_model.replace(".", "_")
                                    title_model_model = model_name.replace("_", " ").title()
                                    variable_model_model = f"model_{model_name}"
                                    cw.emit(f"# Add {title_model_model}")
                                    cw.emit("value = {")
                                    with cw.indent():
                                        cw.emit(f'"name": "{model_name}",')
                                        cw.emit(f'"model": "{model_model}",')
                                        cw.emit('"m2o_module": code_generator_id.id,')
                                        cw.emit('"rec_name": None,')
                                        cw.emit('"nomenclator": True,')
                                    cw.emit("}")
                                    cw.emit(
                                        f'{variable_model_model} = env["ir.model"].create(value)'
                                    )
                                    cw.emit("")
                                    self._write_generated_template(module, model_model, cw)
                                    cw.emit("##### Begin Field")
                                    if module.enable_sync_template:
                                        module_file_sync = ExtractorModule(module, model_model)
                                        view_file_sync = ExtractorView(module, model_model)
                                        lst_view_item_code_generator.append(view_file_sync)
                                        self._write_sync_template_model(
                                            module,
                                            model_model,
                                            cw,
                                            variable_model_model,
                                            lst_keep_f2exports,
                                            module_file_sync,
                                        )
                                    else:
                                        cw.emit("value_field_boolean = {")
                                        with cw.indent():
                                            cw.emit('"name": "field_boolean",')
                                            cw.emit('"model": "demo.model",')
                                            cw.emit('"field_description": "field description",')
                                            cw.emit('"ttype": "boolean",')
                                            cw.emit(f'"model_id": {variable_model_model}.id,')
                                        cw.emit("}")
                                        cw.emit(
                                            'env["ir.model.fields"].create(value_field_boolean)'
                                        )
                                        cw.emit()
                                        cw.emit("# FIELD TYPE Many2one")
                                        cw.emit("#value_field_many2one = {")
                                        with cw.indent():
                                            cw.emit('#"name": "field_many2one",')
                                            cw.emit('#"model": "demo.model",')
                                            cw.emit('#"field_description": "field description",')
                                            cw.emit('#"ttype": "many2one",')
                                            cw.emit('#"comodel_name": "model.name",')
                                            cw.emit('#"relation": "model.name",')
                                            cw.emit(f'#"model_id": {variable_model_model}.id,')
                                        cw.emit("#}")
                                        cw.emit(
                                            '#env["ir.model.fields"].create(value_field_many2one)'
                                        )
                                        cw.emit("")
                                        cw.emit("# Hack to solve field name")
                                        cw.emit(
                                            "field_x_name = env[\"ir.model.fields\"].search([('model_id', '=', "
                                            f"{variable_model_model}.id), ('name', '=', 'x_name')])"
                                        )
                                        cw.emit('field_x_name.name = "name"')
                                        cw.emit(f'{variable_model_model}.rec_name = "name"')
                                        cw.emit("")
                                    if i >= len_model - 1 and lst_keep_f2exports:
                                        cw.emit("")
                                        cw.emit(
                                            "# Added one2many field, many2many need to be creat before add "
                                            "one2many"
                                        )
                                        for (
                                            field_id,
                                            model_model,
                                            variable_model_model,
                                        ) in lst_keep_f2exports:
                                            # Finish to print one2many move at the end
                                            self._write_sync_template_model(
                                                module,
                                                model_model,
                                                cw,
                                                variable_model_model,
                                                lst_keep_f2exports,
                                                None,
                                                lst_force_f2exports=[field_id],
                                            )
                                    cw.emit("##### End Field")
                                    cw.emit()
                                    # TODO add data nomenclator, research data from model
                                    # TODO By default, no data will be nomenclator
                                    # cw.emit("# Add data nomenclator")
                                    # cw.emit("value = {")
                                    # with cw.indent():
                                    #     cw.emit("\"field_boolean\": True,")
                                    #     cw.emit("\"name\": \"demo\",")
                                    # cw.emit("}")
                                    # cw.emit(f"env[\"{model_model}\"].create(value)")
                                    # cw.emit()
                            if module.enable_template_wizard_view:
                                cw.emit("# Generate view")

                                # TODO
                                custom_view = module.enable_sync_template
                                if module.enable_sync_template:
                                    for view_item in lst_view_item_code_generator:
                                        i += 1
                                        cw.emit("##### Begin Views")
                                        self._write_sync_template_views(cw, view_item)
                                        cw.emit("##### End Views")
                                        cw.emit()

                                cw.emit("# Action generate view")
                                cw.emit(
                                    "wizard_view = env['code.generator.generate.views.wizard'].create({"
                                )
                                with cw.indent():
                                    cw.emit("'code_generator_id': code_generator_id.id,")
                                    cw.emit("'enable_generate_all': False,")
                                    if custom_view:
                                        cw.emit('"code_generator_view_ids": [(6, 0, lst_view_id)],')
                                    if module.enable_generate_portal:
                                        cw.emit(
                                            f"'enable_generate_portal': {module.enable_generate_portal},"
                                        )
                                cw.emit("})")
                                cw.emit("")
                                cw.emit("wizard_view.button_generate_views()")
                                cw.emit()
                            cw.emit("# Generate module")
                            cw.emit("value = {")
                            with cw.indent():
                                cw.emit('"code_generator_ids": code_generator_id.ids')
                            cw.emit("}")
                            cw.emit(
                                'code_generator_writer = env["code.generator.writer"].create(value)'
                            )
                    if uninstall_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit(
                                'code_generator_id = env["code.generator.module"].search([("name", "=", MODULE_NAME)])'
                            )
                            cw.emit("if code_generator_id:")
                            with cw.indent():
                                cw.emit("code_generator_id.unlink()")

        _add_hook(
            cw,
            module.pre_init_hook_show,
            module.pre_init_hook_code,
            module.pre_init_hook_feature_general_conf,
            False,
            False,
            "pre_init_hook",
            False,
        )
        _add_hook(
            cw,
            module.post_init_hook_show,
            module.post_init_hook_code,
            module.post_init_hook_feature_general_conf,
            module.post_init_hook_feature_code_generator,
            False,
            "post_init_hook",
            True,
        )
        _add_hook(
            cw,
            module.uninstall_hook_show,
            module.uninstall_hook_code,
            module.uninstall_hook_feature_general_conf,
            False,
            module.post_init_hook_feature_code_generator,
            "uninstall_hook",
            True,
        )

        hook_file_path = "hooks.py"

        self.code_generator_data.write_file_str(hook_file_path, cw.render())

    def set_extra_get_lst_file_generate(self, module):
        super(CodeGeneratorWriter, self).set_extra_get_lst_file_generate(module)
        if module.pre_init_hook_show or module.post_init_hook_show or module.uninstall_hook_show:
            self._set_hook_file(module)
