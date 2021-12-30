import logging

import isort
from code_writer import CodeWriter

from odoo import api, fields, models
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
FROM_ODOO_IMPORTS_SUPERUSER = [
    "from odoo import _, api, models, fields, SUPERUSER_ID"
]
MODEL_SUPERUSER_HEAD = FROM_ODOO_IMPORTS_SUPERUSER + BREAK_LINE


class Struct(object):
    def __init__(self, **entries):
        self.__dict__.update(entries)


_logger = logging.getLogger(__name__)


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def set_module_init_file_extra(self, module):
        super(CodeGeneratorWriter, self).set_module_init_file_extra(module)
        if (
            module.pre_init_hook_show
            or module.post_init_hook_show
            or module.uninstall_hook_show
        ):
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

    def _write_sync_view_component(self, view_item_ids, cw, parent=None):
        for view_item_id in view_item_ids:
            # TODO view_item can be duplicated, use unique name
            var_create_view_item = (
                "view_item"
                if not view_item_id.child_id
                else f"view_item_{view_item_id.section_type}_{view_item_id.sequence}"
            )
            with cw.block(
                before=(
                    f"{var_create_view_item} ="
                    ' env["code.generator.view.item"].create'
                ),
                delim=("(", ")"),
            ):
                with cw.block(delim=("{", "}")):
                    cw.emit(f'"section_type": "{view_item_id.section_type}",')
                    cw.emit(f'"item_type": "{view_item_id.item_type}",')
                    if view_item_id.item_type == "button":
                        cw.emit(
                            f'"action_name": "{view_item_id.action_name}",'
                        )
                        if view_item_id.button_type:
                            cw.emit(
                                f'"button_type": "{view_item_id.button_type}",'
                            )
                        if view_item_id.icon:
                            cw.emit(f'"icon": "{view_item_id.icon}",')
                    elif view_item_id.item_type == "li":
                        if view_item_id.class_attr:
                            cw.emit(
                                f'"class_attr": "{view_item_id.class_attr}",'
                            )
                    elif view_item_id.item_type == "field":
                        cw.emit(
                            f'"action_name": "{view_item_id.action_name}",'
                        )
                        if view_item_id.placeholder:
                            cw.emit(
                                f'"placeholder": "{view_item_id.placeholder}",'
                            )
                        if view_item_id.password:
                            cw.emit(f'"password": {view_item_id.password},')
                    elif view_item_id.item_type in ("group", "div"):
                        if view_item_id.attrs:
                            cw.emit(f'"attrs": "{view_item_id.attrs}",')
                    elif view_item_id.item_type == "xpath":
                        if not view_item_id.expr or not view_item_id.position:
                            _logger.error(
                                f"Need expr and position of xpath {1}"
                            )
                        else:
                            cw.emit(f'"expr": "{view_item_id.expr}",')
                            cw.emit(f'"position": "{view_item_id.position}",')
                    elif view_item_id.item_type == "html":
                        # TODO support help and type bg-warning
                        if view_item_id.colspan != 1:
                            cw.emit(f'"colspan": {view_item_id.colspan},')
                        if view_item_id.background_type:
                            cw.emit(
                                '"background_type":'
                                f' "{view_item_id.background_type}",'
                            )

                    if (
                        view_item_id.label
                        and view_item_id.label != view_item_id.action_name
                    ):
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

    def _write_block_template_views(
        self, cw, view_id, view_item, tpl_ordered_section, view_type
    ):
        tpl_available_section = view_id.view_item_ids.mapped("section_type")
        s = set(tpl_available_section)
        lst_section = [x for x in tpl_ordered_section if x in s]

        for section in lst_section:
            cw.emit(f"# {section.upper()}")
            view_item_ids = view_id.view_item_ids.filtered(
                lambda field: field.section_type == section
                and not field.parent_id
            )

            self._write_sync_view_component(view_item_ids, cw)

        cw.emit('view_code_generator = env["code.generator.view"].create(')
        with cw.block(delim=("{", "}")):
            cw.emit('"code_generator_id": code_generator_id.id,')
            cw.emit(f'"view_type": "{view_type}",')
            if view_id.view_name:
                cw.emit(f'"view_name": "{view_id.view_name}",')
            cw.emit(f'"m2o_model": {view_item.var_model_name}.id,')
            cw.emit('"view_item_ids": [(6, 0, lst_item_view)],')
            if view_id.has_body_sheet:
                cw.emit(f'"has_body_sheet": {view_id.has_body_sheet},')
            if view_id.id_name:
                cw.emit(f'"id_name": "{view_id.id_name}",')
            if view_id.inherit_view_name:
                cw.emit(f'"inherit_view_name": "{view_id.inherit_view_name}",')
        cw.emit(")")
        cw.emit("lst_view_id.append(view_code_generator.id)")

    def _write_sync_template_action(self, cw, module, act_server_ids):
        cw.emit("# action_server view")
        cw.emit("if True:")
        with cw.indent():
            if act_server_ids:
                for act_server in act_server_ids:
                    var_act_server_id = self.env["ir.model.data"].search(
                        [
                            ("module", "=", module.template_module_name),
                            ("res_id", "=", act_server.id),
                            ("model", "=", "ir.actions.server"),
                        ]
                    )
                    var_model_id = (
                        f"model_{act_server.model_name.replace('.', '_')}"
                    )
                    with cw.block(
                        before=(
                            f'act_server_id = env["ir.actions.server"].create'
                        ),
                        delim=("(", ")"),
                    ):
                        with cw.block(delim=("{", "}")):
                            cw.emit(f'"name": "{act_server.name}",')
                            cw.emit(f'"model_id": {var_model_id}.id,')
                            cw.emit(f'"binding_model_id": {var_model_id}.id,')
                            cw.emit(f'"state": "{act_server.state}",')
                            cw.emit(f'"code": "{act_server.code}",')
                            if act_server.comment:
                                comment = act_server.comment.replace(
                                    '"', '\\"'
                                )
                                cw.emit(f'"comment": "{comment}",')
                    cw.emit()
                    if var_act_server_id:
                        # TODO instead of creating id, maybe add this feature directly in ir.actions.server?
                        cw.emit("# Add record id name")
                        with cw.block(
                            before=f'env["ir.model.data"].create',
                            delim=("(", ")"),
                        ):
                            with cw.block(delim=("{", "}")):
                                cw.emit(f'"name": "{var_act_server_id.name}",')
                                cw.emit(f'"model": "ir.actions.server",')
                                cw.emit('"module": MODULE_NAME,')
                                cw.emit(f'"res_id": act_server_id.id,')
                                cw.emit(f'"noupdate": True,')
            else:
                cw.emit("pass")
        cw.emit()

    def _write_sync_template_views(
        self, cw, view_item, lst_menu_id_create, is_first
    ):
        if not view_item.code_generator_id:
            return
        code_generator_views_id = (
            view_item.code_generator_id.code_generator_views_id
        )
        tlp_order_section_form = ("header", "title", "body")
        tlp_order_section_other = ("body",)
        lst_tag_support = list(
            dict(
                self.env["code.generator.view"]._fields["view_type"].selection
            ).keys()
        )
        if is_first:
            cw.emit("lst_view_id = []")
        for tag_name in lst_tag_support:
            view_ids = code_generator_views_id.filtered(
                lambda a: a.view_type == tag_name
            )
            if not view_ids:
                continue

            if tag_name == "form":
                tpl_order_section = tlp_order_section_form
            else:
                tpl_order_section = tlp_order_section_other
            cw.emit(f"# {tag_name} view")
            cw.emit("if True:")
            with cw.indent():
                cw.emit("lst_item_view = []")
                for view_id in view_ids:
                    self._write_block_template_views(
                        cw, view_id, view_item, tpl_order_section, tag_name
                    )
            cw.emit()
        if view_item.code_generator_id.code_generator_act_window_id:
            cw.emit("# act_window view")
            cw.emit("if True:")
            with cw.indent():
                for (
                    act_win_id
                ) in view_item.code_generator_id.code_generator_act_window_id:
                    with cw.block(
                        before=(
                            f"{act_win_id.id_name} ="
                            ' env["code.generator.act_window"].create'
                        ),
                        delim=("(", ")"),
                    ):
                        with cw.block(delim=("{", "}")):
                            cw.emit(
                                '"code_generator_id": code_generator_id.id,'
                            )
                            cw.emit(f'"name": "{act_win_id.name}",')
                            cw.emit(f'"id_name": "{act_win_id.id_name}",')
                    cw.emit()
        cw.emit()
        if view_item.code_generator_id.code_generator_menus_id:
            cw.emit("# menu view")
            cw.emit("if True:")
            with cw.indent():
                for (
                    menu_id
                ) in view_item.code_generator_id.code_generator_menus_id:
                    if menu_id.id not in lst_menu_id_create:
                        lst_menu_id_create.append(menu_id.id)
                    else:
                        # TODO this is a bug, lst_menu_id_create patch the bug, for each view, recreate all menu
                        # TODO need to associate menu to his view, or find a way to not associate like this
                        continue
                    # env["code.generator.menu"].create(
                    #     {
                    #         "code_generator_id": code_generator_id.id,
                    #         "parent_id_name": "base.next_id_9",
                    #         "id_name": "backup_conf_menu",
                    #     }
                    # )
                    with cw.block(
                        before='env["code.generator.menu"].create',
                        delim=("(", ")"),
                    ):
                        with cw.block(delim=("{", "}")):
                            cw.emit(
                                '"code_generator_id": code_generator_id.id,'
                            )
                            if menu_id.name:
                                cw.emit(f'"name": "{menu_id.name}",')
                            if menu_id.web_icon:
                                cw.emit(f'"web_icon": "{menu_id.web_icon}",')
                            cw.emit(f'"id_name": "{menu_id.id_name}",')
                            if menu_id.sequence != 10:
                                cw.emit(f'"sequence": {menu_id.sequence},')
                            if menu_id.parent_id_name:
                                cw.emit(
                                    '"parent_id_name":'
                                    f' "{menu_id.parent_id_name}",'
                                )
                            if menu_id.m2o_act_window:
                                cw.emit(
                                    '"m2o_act_window":'
                                    f" {menu_id.m2o_act_window.id_name}.id,"
                                )
                            if menu_id.ignore_act_window:
                                cw.emit('"ignore_act_window": True,')

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
        return code_generator_views_id

    def _set_hook_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()

        for line in MODEL_SUPERUSER_HEAD:
            str_line = line.strip()
            cw.emit(str_line)

        cw.emit("import os")
        if module.template_module_id and module.template_module_id.icon_image:
            # TODO need logging when has inherit
            cw.emit("import logging")
            # TODO this case need import os, find another dynamic way to specify import before write code
            cw.emit()
            cw.emit("_logger = logging.getLogger(__name__)")
            cw.emit()

        is_generator_demo = module.name == "code_generator_demo"

        # Add constant
        if module.hook_constant_code:
            if module.enable_template_code_generator_demo:
                cw.emit(
                    "# TODO HUMAN: change my module_name to create a specific"
                    " demo functionality"
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
                    for hook_line in hook_code.split("\n"):
                        cw.emit(hook_line)
                    if hook_feature_gen_conf:
                        with cw.indent():
                            cw.emit("# General configuration")
                            with cw.block(before="values =", delim=("{", "}")):
                                pass

                            cw.emit(
                                "event_config ="
                                " env['res.config.settings'].sudo().create(values)"
                            )
                            cw.emit("event_config.execute()")
                    if post_init_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit()
                            cw.emit("# The path of the actual file")
                            path_cg_module = (
                                module.template_module_path_generated_extension
                            )
                            if path_cg_module and path_cg_module != ".":
                                if path_cg_module[0] == "/":
                                    cw.emit(
                                        "path_module_generate ="
                                        f" '{path_cg_module}'"
                                    )
                                elif path_cg_module[0] in ("'", '"'):
                                    cw.emit(
                                        "path_module_generate ="
                                        " os.path.normpath(os.path.join(os.path.dirname(__file__),"
                                        f" '..', {path_cg_module}))"
                                    )
                                else:
                                    cw.emit(
                                        "path_module_generate ="
                                        f" '{path_cg_module}'"
                                    )
                            else:
                                cw.emit(
                                    "# path_module_generate ="
                                    " os.path.normpath(os.path.join(os.path.dirname(__file__),"
                                    " '..'))"
                                )
                            cw.emit()
                            cw.emit(
                                'short_name = MODULE_NAME.replace("_", "'
                                ' ").title()'
                            )
                            cw.emit()
                            cw.emit("# Add code generator")
                            if (
                                module.template_module_id
                                and module.template_module_id.category_id
                            ):
                                cw.emit(
                                    "categ_id ="
                                    ' env["ir.module.category"].search([("name",'
                                    ' "=",'
                                    f' "{module.template_module_id.category_id.display_name}")],'
                                    " limit=1)"
                                )
                            cw.emit("value = {")
                            with cw.indent():
                                if module.template_module_id:
                                    mod_id = module.template_module_id
                                    title = mod_id.name.replace(
                                        "_", " "
                                    ).title()
                                    if title == mod_id.shortdesc:
                                        cw.emit('"shortdesc": short_name,')
                                    else:
                                        cw.emit(
                                            '"shortdesc":'
                                            f' "{mod_id.shortdesc}",'
                                        )
                                    # Force update name with MODULE_NAME from hook
                                    cw.emit(f'"name": MODULE_NAME,')
                                    if mod_id.header_manifest:
                                        header_manifest = (
                                            mod_id.header_manifest.strip()
                                        )
                                        lst_header_manifest = (
                                            header_manifest.split("\n")
                                        )
                                        if len(lst_header_manifest) == 1:
                                            cw.emit(
                                                "'header_manifest':"
                                                f" '{header_manifest}',"
                                            )
                                        else:
                                            cw.emit("'header_manifest': '''")
                                            for desc in lst_header_manifest:
                                                if desc:
                                                    cw.emit_raw(desc + "\n")
                                            cw.emit("''',")
                                    cw.emit(f'"license": "{mod_id.license}",')
                                    if mod_id.category_id:
                                        cw.emit(f'"category_id": categ_id.id,')
                                    cw.emit(f'"summary": "{mod_id.summary}",')
                                    if mod_id.author:
                                        author = mod_id.author.strip()
                                        lst_author = author.split(",")
                                        if len(lst_author) == 1:
                                            cw.emit(f"'author': '{author}',")
                                        else:
                                            cw.emit(f"'author': (")
                                            with cw.indent():
                                                for hm in lst_author[:-1]:
                                                    s_hm = hm.strip()
                                                    cw.emit(f"'{s_hm}, '")
                                            cw.emit(
                                                f"'{lst_author[-1].strip()}'),"
                                            )
                                    else:
                                        cw.emit('"author": "",')
                                    cw.emit(f'"website": "{mod_id.website}",')
                                    cw.emit(
                                        f'"application": {mod_id.application},'
                                    )
                                else:
                                    # TODO need better support here, can we use existing object?
                                    # TODO need to support variable into class
                                    cw.emit('"shortdesc": short_name,')
                                    cw.emit('"name": MODULE_NAME,')
                                    cw.emit('"license": "AGPL-3",')
                                    cw.emit('"author": "TechnoLibre",')
                                    cw.emit(
                                        '"website": "https://technolibre.ca",'
                                    )
                                    cw.emit('"application": True,')
                                # with cw.block(before='"depends" :', delim=('[', '],')):
                                #     cw.emit('"code_generator",')
                                #     cw.emit('"code_generator_hook",')
                                cw.emit('"enable_sync_code": True,')
                                if (
                                    module.template_module_path_generated_extension
                                    and module.template_module_path_generated_extension
                                    != "."
                                ):
                                    cw.emit(
                                        '"path_sync_code":'
                                        " path_module_generate,"
                                    )
                                else:
                                    cw.emit(
                                        '# "path_sync_code":'
                                        " path_module_generate,"
                                    )
                                if (
                                    module.template_module_id
                                    and module.template_module_id.icon_image
                                ):
                                    cw.emit(
                                        '"icon":'
                                        " os.path.join(os.path.dirname(__file__),"
                                        ' "static", "description",'
                                        ' "code_generator_icon.png"),'
                                    )
                            cw.emit("}")
                            cw.emit()
                            cw.emit(
                                "# TODO HUMAN: enable your functionality to"
                                " generate"
                            )
                            enable_template_code_generator_demo = (
                                module.enable_template_code_generator_demo
                                if module.name == "code_generator_demo"
                                else False
                            )
                            if module.enable_template_code_generator_demo:
                                cw.emit(
                                    'value["enable_template_code_generator_demo"]'
                                    f" = {enable_template_code_generator_demo}"
                                )
                                cw.emit('value["template_model_name"] = ""')
                                if (
                                    module.template_module_path_generated_extension
                                    != "."
                                ):
                                    cw.emit(
                                        'value["template_module_path_generated_extension"]'
                                        f' = "{module.template_module_path_generated_extension}"'
                                    )
                                else:
                                    cw.emit(
                                        '# value["template_module_path_generated_extension"]'
                                        ' = "."'
                                    )
                                cw.emit(
                                    'value["enable_template_wizard_view"] ='
                                    " False"
                                )
                                cw.emit(
                                    'value["force_generic_template_wizard_view"]'
                                    " = False"
                                )
                                cw.emit(
                                    'value["disable_generate_access"] = False'
                                )
                                cw.emit(
                                    'value["enable_template_website_snippet_view"] = '
                                    f"{module.enable_template_website_snippet_view}"
                                )
                            elif module.enable_template_website_snippet_view:
                                cw.emit(
                                    'value["enable_generate_website_snippet"]'
                                    " = True"
                                )
                                cw.emit(
                                    'value["enable_generate_website_snippet_javascript"]'
                                    " = True"
                                )
                                cw.emit(
                                    'value["generate_website_snippet_type"] ='
                                    ' "effect"  #'
                                    " content,effect,feature,structure"
                                )
                            cw.emit(
                                'value["enable_sync_template"] ='
                                f" {module.enable_sync_template}"
                            )
                            cw.emit(f'value["ignore_fields"] = ""')
                            cw.emit(
                                'value["post_init_hook_show"] ='
                                f" {module.enable_template_code_generator_demo}"
                            )
                            cw.emit(
                                'value["uninstall_hook_show"] ='
                                f" {module.enable_template_code_generator_demo}"
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
                                    'if MODULE_NAME != "code_generator_demo"'
                                    ' and "code_generator_" in MODULE_NAME:'
                                )
                                with cw.indent():
                                    cw.emit(
                                        'if "code_generator_template" in'
                                        " MODULE_NAME:"
                                    )
                                    with cw.indent():
                                        cw.emit(
                                            'if value["enable_template_code_generator_demo"]:'
                                        )
                                        with cw.indent():
                                            cw.emit(
                                                "new_module_name ="
                                                ' f"code_generator_{MODULE_NAME['
                                                "len('code_generator_template_'):]}\""
                                            )
                                        cw.emit("else:")
                                        with cw.indent():
                                            cw.emit(
                                                "new_module_name ="
                                                ' MODULE_NAME[len("code_generator_template_"):]'
                                            )
                                    cw.emit("else:")
                                    with cw.indent():
                                        cw.emit(
                                            "new_module_name ="
                                            ' MODULE_NAME[len("code_generator_"):]'
                                        )
                                    cw.emit(
                                        'value["template_module_name"] ='
                                        " new_module_name"
                                    )
                                cw.emit(
                                    'value["hook_constant_code"] ='
                                    " f'MODULE_NAME = \"{new_module_name}\"'"
                                )
                            else:
                                cw.emit(
                                    'value["hook_constant_code"] ='
                                    " f'MODULE_NAME = \"{MODULE_NAME}\"'"
                                )
                            cw.emit()
                            cw.emit(
                                "code_generator_id ="
                                ' env["code.generator.module"].create(value)'
                            )
                            cw.emit()
                            lst_module_depend = []
                            if (
                                module.template_module_id
                                and module.template_module_id.dependencies_id
                            ):
                                lst_module_depend = [
                                    a.name
                                    for a in module.template_module_id.dependencies_id
                                ]
                            elif module.dependencies_id:
                                lst_module_depend = [
                                    a.depend_id.name
                                    for a in module.dependencies_id
                                ]

                            if lst_module_depend:
                                cw.emit("# Add dependencies")
                                lst_module_depend = sorted(lst_module_depend)
                                if len(lst_module_depend) > 1:
                                    cw.emit(
                                        "lst_depend_module ="
                                        f" {lst_module_depend}"
                                    )
                                    cw.emit(
                                        f"code_generator_id.add_module_dependency(lst_depend_module)"
                                    )
                                    if is_generator_demo:
                                        cw.emit(
                                            f"code_generator_id.add_module_dependency_template(lst_depend_module)"
                                        )
                                elif lst_module_depend:
                                    cw.emit(
                                        f'code_generator_id.add_module_dependency("{lst_module_depend[0]}")'
                                    )
                                    if is_generator_demo:
                                        cw.emit(
                                            f'code_generator_id.add_module_dependency_template("{lst_module_depend[0]}")'
                                        )

                            if module.external_dependencies_id:
                                cw.emit("# External dependencies")
                                for (
                                    ext_depend
                                ) in module.external_dependencies_id:
                                    if not ext_depend.is_template:
                                        continue
                                    cw.emit("value = {")
                                    with cw.indent():
                                        cw.emit(
                                            f'"module_id":'
                                            f" code_generator_id.id,"
                                        )
                                        cw.emit(
                                            f'"depend": "{ext_depend.depend}",'
                                        )
                                        cw.emit(
                                            '"application_type":'
                                            f' "{ext_depend.application_type}",'
                                        )
                                    cw.emit("}")
                                    cw.emit(
                                        "env['code.generator.module.external.dependency'].create(value)"
                                    )
                                    cw.emit()

                            lst_view_item_code_generator = []
                            lst_model_id = []
                            if module.template_model_name:
                                lst_model = [
                                    a.strip()
                                    for a in module.template_model_name.split(
                                        ";"
                                    )
                                    if a.strip()
                                ]

                                # Filter model and get model_id
                                for model_model in lst_model:
                                    model_id = self.env["ir.model"].search(
                                        [("model", "=", model_model)]
                                    )
                                    if not model_id:
                                        _logger.error(
                                            f"Model '{model_model}' not"
                                            " existing."
                                        )
                                        continue
                                    lst_model_id.append(model_id)

                                len_model = len(lst_model)
                                i = -1
                                dct_model_one2many = {}
                                for model_id in lst_model_id:
                                    i += 1
                                    model_model = model_id.model
                                    if module.enable_sync_template:
                                        view_file_sync = (
                                            module.view_file_sync.get(
                                                model_id.model
                                            )
                                        )
                                        if view_file_sync:
                                            lst_view_item_code_generator.append(
                                                view_file_sync
                                            )

                                    if "." in model_id.model:
                                        (
                                            application_name,
                                            _,
                                        ) = model_id.model.split(
                                            ".", maxsplit=1
                                        )
                                    else:
                                        application_name = model_id.model
                                    model_name = model_id.model.replace(
                                        ".", "_"
                                    )
                                    title_model_model = model_name.replace(
                                        "_", " "
                                    ).title()

                                    cw.emit()
                                    cw.emit(
                                        f"# Add/Update {title_model_model}"
                                    )

                                    # Prepare field data
                                    (
                                        dct_field_data,
                                        dct_field_data_one2many,
                                    ) = self._get_field_data(module, model_id)

                                    if dct_field_data_one2many:
                                        dct_model_one2many[
                                            model_id.model
                                        ] = dct_field_data_one2many

                                    self.write_model(
                                        cw,
                                        model_id,
                                        application_name,
                                        module,
                                        dct_field_data,
                                    )
                                    if (
                                        i >= len_model - 1
                                        and dct_model_one2many
                                    ):
                                        cw.emit()
                                        cw.emit(
                                            "# Added one2many field,"
                                            " many2one need to be create"
                                            " before add one2many"
                                        )
                                        for (
                                            model_name,
                                            dct_field,
                                        ) in dct_model_one2many.items():
                                            cw.emit(
                                                f'model_model = "{model_name}"'
                                            )
                                            with cw.block(
                                                before=f"dct_field =",
                                                delim=("{", "}"),
                                            ):
                                                for (
                                                    key,
                                                    dct_value,
                                                ) in dct_field.items():
                                                    with cw.block(
                                                        before=f'"{key}" :',
                                                        delim=("{", "},"),
                                                    ):
                                                        for (
                                                            sub_key,
                                                            value,
                                                        ) in dct_value.items():
                                                            self._write_dict_key(
                                                                cw,
                                                                sub_key,
                                                                value,
                                                            )
                                            cw.emit(
                                                "code_generator_id.add_update_model_one2many(model_model,"
                                                " dct_field)"
                                            )
                                            cw.emit()

                                    self._write_generated_template(
                                        module, model_id.model, cw
                                    )
                                    cw.emit()
                                    # TODO add data nomenclator, research data from model
                                    # TODO By default, no data will be nomenclator
                                    # cw.emit("# Add data nomenclator")
                                    # cw.emit("value = {")
                                    # with cw.indent():
                                    #     cw.emit("\"field_boolean\": True,")
                                    #     cw.emit("\"name\": \"demo\",")
                                    # cw.emit("}")
                                    # cw.emit(f"env[\"{model_id.model}\"].create(value)")
                                    # cw.emit()
                                    # Generate code
                                    self.write_code(cw, model_id, module)

                                    act_server_ids = self.env[
                                        "ir.actions.server"
                                    ].search(
                                        [
                                            (
                                                "model_name",
                                                "=",
                                                model_id.model,
                                            ),
                                            (
                                                "usage",
                                                "=",
                                                "ir_actions_server",
                                            ),
                                            ("model_id", "=", model_id.id),
                                        ]
                                    )
                                    if act_server_ids:
                                        cw.emit("# Generate server action")
                                        self._write_sync_template_action(
                                            cw, module, act_server_ids
                                        )

                                    # Support constraint
                                    constraint_ids = self.env[
                                        "ir.model.constraint"
                                    ].search(
                                        [
                                            (
                                                "module",
                                                "=",
                                                module.template_module_id.id,
                                            ),
                                            ("definition", "!=", False),
                                        ]
                                    )
                                    if constraint_ids:
                                        self.write_constraint(
                                            cw, constraint_ids, model_id
                                        )

                            if module.enable_template_wizard_view:
                                # Icon copy from sync
                                if module.enable_sync_template:
                                    if (
                                        module.template_module_id.icon_image
                                        and not module.icon_child_image
                                    ):
                                        module.icon_child_image = (
                                            module.template_module_id.icon_image
                                        )

                                cw.emit("# Generate view")
                                custom_view = (
                                    module.enable_sync_template
                                    and not module.force_generic_template_wizard_view
                                )
                                has_custom_view = False
                                has_menu = False
                                has_access = False
                                lst_menu_id_create = []
                                is_first = True
                                no_view = -1
                                if custom_view:
                                    for (
                                        view_item
                                    ) in lst_view_item_code_generator:
                                        if (
                                            not view_item
                                            or not view_item.code_generator_id
                                        ):
                                            continue
                                        no_view += 1
                                        if (
                                            view_item.code_generator_id.code_generator_menus_id
                                        ):
                                            has_menu = True
                                        view_id = (
                                            self._write_sync_template_views(
                                                cw,
                                                view_item,
                                                lst_menu_id_create,
                                                is_first,
                                            )
                                        )
                                        is_first = False
                                        if view_id:
                                            has_custom_view = True
                                        cw.emit()
                                else:
                                    # TODO This seems wrong, need to get this variable from extractor_view
                                    has_menu = True
                                    has_access = True

                                self.write_action_generate_view(
                                    cw,
                                    module,
                                    has_custom_view,
                                    has_access,
                                    has_menu,
                                )

                            for model_id in lst_model_id:
                                # This section need to be generated after view was created
                                if (
                                    module.enable_template_wizard_view
                                    and not module.force_generic_template_wizard_view
                                    and not module.disable_generate_access
                                ):
                                    model_name = model_id.model.replace(
                                        ".", "_"
                                    )
                                    variable_model_model = (
                                        f"model_{model_name}"
                                    )
                                    # TODO why force_generic_template_wizard_view force no access?
                                    access_ids = self.env[
                                        "ir.model.access"
                                    ].search(
                                        [
                                            (
                                                "model_id",
                                                "=",
                                                model_id.id,
                                            )
                                        ]
                                    )
                                    self.write_access(
                                        cw,
                                        access_ids,
                                        variable_model_model,
                                    )

                            cw.emit("# Generate module")
                            cw.emit("value = {")
                            with cw.indent():
                                cw.emit(
                                    '"code_generator_ids":'
                                    " code_generator_id.ids"
                                )
                            cw.emit("}")
                            cw.emit(
                                'env["code.generator.writer"].create(value)'
                            )

                    if uninstall_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit(
                                "code_generator_id ="
                                ' env["code.generator.module"].search([("name",'
                                ' "=", MODULE_NAME)])'
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

    def write_model(
        self,
        cw,
        model_id,
        application_name,
        module,
        dct_field_data,
    ):
        # TODO wrong place for this code, add it in inherit_model_ids when evaluate code
        field_id_track = model_id.field_id.filtered(
            lambda x: x.track_visibility
        )

        # Prepare model inherit data
        lst_dependency = [a.name for a in model_id.inherit_model_ids]
        if field_id_track:
            if "mail.thread" not in lst_dependency:
                lst_dependency.append("mail.thread")
            if "mail.activity.mixin" not in lst_dependency:
                lst_dependency.append("mail.activity.mixin")

        # Prepare model data
        dct_model_data = {}
        if (
            model_id
            and model_id.description
            # and model_id.description != model_id.name
        ):
            dct_model_data["description"] = model_id.description
        if application_name.lower() == "demo":
            dct_model_data["menu_name_keep_application"] = True
        if model_id.enable_activity or field_id_track:
            dct_model_data["enable_activity"] = True
        if model_id.rec_name and model_id.rec_name != "name":
            dct_model_data["rec_name"] = model_id.rec_name
        if (
            model_id.diagram_node_object
            and model_id.diagram_node_xpos_field
            and model_id.diagram_node_ypos_field
            and model_id.diagram_arrow_object
            and model_id.diagram_arrow_src_field
            and model_id.diagram_arrow_dst_field
        ):
            dct_model_data[
                "diagram_node_object"
            ] = model_id.diagram_node_object
            dct_model_data[
                "diagram_node_xpos_field"
            ] = model_id.diagram_node_xpos_field
            dct_model_data[
                "diagram_node_ypos_field"
            ] = model_id.diagram_node_ypos_field
            if model_id.diagram_node_shape_field:
                dct_model_data[
                    "diagram_node_shape_field"
                ] = model_id.diagram_node_shape_field
            if model_id.diagram_node_form_view_ref:
                # TODO validate it exist and add variable to link name if changed
                dct_model_data[
                    "diagram_node_form_view_ref"
                ] = model_id.diagram_node_form_view_ref
            dct_model_data[
                "diagram_arrow_object"
            ] = model_id.diagram_arrow_object
            dct_model_data[
                "diagram_arrow_src_field"
            ] = model_id.diagram_arrow_src_field
            dct_model_data[
                "diagram_arrow_dst_field"
            ] = model_id.diagram_arrow_dst_field
            if model_id.diagram_arrow_label:
                dct_model_data[
                    "diagram_arrow_label"
                ] = model_id.diagram_arrow_label
            if model_id.diagram_arrow_form_view_ref:
                # TODO validate it exist and add variable to link name if changed
                dct_model_data[
                    "diagram_arrow_form_view_ref"
                ] = model_id.diagram_arrow_form_view_ref
            if model_id.diagram_label_string:
                dct_model_data[
                    "diagram_label_string"
                ] = model_id.diagram_label_string

        cw.emit(f'model_model = "{model_id.model}"')
        model_name = model_id.model.replace(".", "_")
        cw.emit(f'model_name = "{model_name}"')

        if lst_dependency:
            cw.emit(f"lst_depend_model = {lst_dependency}")

        if dct_model_data:
            with cw.block(before="dct_model =", delim=("{", "}")):
                lst_sorted_key = sorted(dct_model_data)
                for key in lst_sorted_key:
                    value = dct_model_data.get(key)
                    self._write_dict_key(cw, key, value)

        if dct_field_data:
            with cw.block(before="dct_field =", delim=("{", "}")):
                lst_sorted_key = sorted(dct_field_data)
                for key in lst_sorted_key:
                    dct_value = dct_field_data.get(key)
                    with cw.block(before=f'"{key}":', delim=("{", "},")):
                        lst_sorted_subkey = sorted(dct_value)
                        for subkey in lst_sorted_subkey:
                            value = dct_value.get(subkey)
                            self._write_dict_key(cw, subkey, value)

        if dct_model_data or dct_field_data:
            # TODO check if contain view to create a variable
            var_model_name = f"model_{model_name}"
            with cw.block(
                before=(
                    f"{var_model_name} = code_generator_id.add_update_model"
                ),
                delim=("(", ")"),
            ):
                cw.emit("model_model,")
                cw.emit("model_name,")
                if dct_field_data:
                    cw.emit("dct_field=dct_field,")
                if dct_model_data:
                    cw.emit("dct_model=dct_model,")
                cw.emit("lst_depend_model=lst_depend_model,")

    @staticmethod
    def _write_dict_key(cw, key, value):
        if type(value) is str:
            if '"' in value:
                value = value.replace('"', '\\"')
            if "\n" in value:
                cw.emit_raw(f'{" " * cw.cur_indent}"{key}": """{value}""",\n')
            else:
                cw.emit(f'"{key}": "{value}",')
        elif type(value) is tuple:
            if value[0] == "noquote":
                cw.emit(f'"{key}": {value[1]},')
            else:
                _logger.error("Not supported tuple option in _write_dict_key")
        else:
            cw.emit(f'"{key}": {value},')

    def _get_field_data(self, module, model_id):
        dct_field_data = {}
        dct_field_data_one2many = {}

        if not module.enable_sync_template:
            return dct_field_data, dct_field_data_one2many

        dct_field_ast = {}
        module_file_sync = module.module_file_sync.get(model_id.model)
        view_file_sync = module.view_file_sync.get(model_id.model)
        lst_ignored_field = (
            module.ignore_fields.split(";") if module.ignore_fields else []
        )

        if module_file_sync and module_file_sync.is_enabled:
            dct_field_ast = module_file_sync.dct_model.get(model_id.model)

        # TODO Check name is different before ignored it
        if lst_ignored_field:
            lst_ignored_field += MAGIC_FIELDS
        else:
            lst_ignored_field = MAGIC_FIELDS[:]
        if "name" in dct_field_ast.keys() and "name" in lst_ignored_field:
            lst_ignored_field.remove("name")

        if dct_field_ast:
            lst_search = [
                ("model", "=", model_id.model),
                ("name", "in", list(dct_field_ast.keys())),
            ]
        else:
            # Add inherit field to ignore it, this can be wrong...
            # sometime, it wants to override inherit field
            inherit_model_ids = (
                self.env["ir.model"]
                .search([("model", "=", model_id.model)])
                .inherit_model_ids
            )
            lst_field_inherit = [
                b.name for a in inherit_model_ids for b in a.depend_id.field_id
            ]
            lst_ignored_field += lst_field_inherit
            lst_ignored_field = list(set(lst_ignored_field))
            lst_search = [
                ("model", "=", model_id.model),
                ("name", "not in", lst_ignored_field),
            ]
        f2exports = self.env["ir.model.fields"].search(lst_search)

        dct_var_id_view = {}
        for field_id in f2exports:
            dct_field_value = {}
            dct_field = {}
            var_id_view = f"field_{field_id.name}_id"
            dct_var_id_view[var_id_view] = field_id

            ast_attr = dct_field_ast.get(field_id.name)

            if view_file_sync:
                dct_field = view_file_sync.dct_field.get(field_id.name)

            if model_id.has_same_model_in_inherit_model():
                dct_field_value["is_show_whitelist_model_inherit"] = True

            # No need model when generate from model including field, already associated
            # dct_field_value["model"] = model_id.model
            # dct_field_value["name"] = field_id.name
            dct_field_value["field_description"] = field_id.field_description
            dct_field_value["ttype"] = field_id.ttype

            if field_id.required:
                dct_field_value["required"] = field_id.required

            if field_id.help:
                dct_field_value["help"] = field_id.help

            if ast_attr:
                lst_attr = ["track_visibility", "code_generator_compute"]
                if not module.disable_fix_code_generator_sequence:
                    lst_attr += [
                        "code_generator_sequence",
                        "code_generator_form_simple_view_sequence",
                        "code_generator_tree_view_sequence",
                    ]
                for attr in lst_attr:
                    item = ast_attr.get(attr)
                    if item:
                        dct_field_value[attr] = item

                default_value = ast_attr.get("default")
                if default_value:
                    if field_id.ttype not in ("char", "selection"):
                        # TODO how better support, remove the quote when it's a variable
                        dct_field_value["default"] = ("noquote", default_value)
                    else:
                        dct_field_value["default"] = default_value

                if "force_widget" in ast_attr.keys():
                    dct_field_value["force_widget"] = ast_attr.get(
                        "force_widget"
                    )

                compute = ast_attr.get("compute") if ast_attr else None
                if compute:
                    if field_id.store:
                        dct_field_value["store"] = True
                    dct_field_value["code_generator_compute"] = compute

            if dct_field:
                if dct_field.get("is_date_start_view"):
                    dct_field_value["is_date_start_view"] = True

                if dct_field.get("is_date_end_view"):
                    dct_field_value["is_date_end_view"] = True

            if field_id.ttype in ["many2one", "many2many"]:
                dct_field_value["relation"] = field_id.relation
            elif field_id.ttype == "one2many":
                dct_field_value["relation"] = field_id.relation
                field_many2one_ids = self.env["ir.model.fields"].search(
                    [
                        ("model", "=", field_id.relation),
                        ("ttype", "=", "many2one"),
                        ("name", "=", field_id.relation_field),
                    ]
                )
                if len(field_many2one_ids) == 1:
                    dct_field_value["relation_field"] = field_many2one_ids.name
                else:
                    _logger.error(
                        "Cannot support this situation, where is the"
                        f" many2one? Field '{field_id.relation_field}'"
                    )
            elif field_id.ttype == "selection":
                field_selection = (
                    self.env[model_id.model]
                    .fields_get(field_id.name)
                    .get(field_id.name)
                )
                dct_field_value["selection"] = str(
                    field_selection.get("selection")
                )

            # Separate queue to thread the information, one2many will be at the end
            if field_id.ttype == "one2many":
                dct_field_data_one2many[field_id.name] = dct_field_value
            else:
                dct_field_data[field_id.name] = dct_field_value

        return dct_field_data, dct_field_data_one2many

    def write_action_generate_view(
        self, cw, module, has_custom_view, has_access, has_menu_item
    ):
        cw.emit("# Action generate view")
        cw.emit(
            "wizard_view ="
            " env['code.generator.generate.views.wizard'].create({"
        )
        with cw.indent():
            cw.emit("'code_generator_id': code_generator_id.id,")
            cw.emit("'enable_generate_all': False,")
            if not has_menu_item:
                cw.emit("'disable_generate_menu': True,")
            if not has_access:
                cw.emit("'disable_generate_access': True,")
            if has_custom_view:
                cw.emit('"code_generator_view_ids": [(6, 0, lst_view_id)],')
            if module.enable_generate_portal:
                cw.emit(
                    "'enable_generate_portal':"
                    f" {module.enable_generate_portal},"
                )

        cw.emit("})")
        cw.emit("")
        cw.emit("wizard_view.button_generate_views()")
        cw.emit()

    def write_code(self, cw, model_id, module):
        code_import_ids = (
            self.env["code.generator.model.code.import"]
            .search(
                [
                    (
                        "m2o_model",
                        "=",
                        model_id.id,
                    ),
                    ("m2o_module", "=", module.id),
                    ("is_templated", "=", True),
                ]
            )
            .sorted(lambda code: code.sequence)
        )
        # Valide before writing
        dct_code_id = {}
        for code_id in code_import_ids:
            if code_id.code in dct_code_id.keys():
                _logger.warning(
                    "Find duplicate code for"
                    " model"
                    " code.generator.model.code.import"
                    f" : {code_id.code}"
                )
            else:
                dct_code_id[code_id.code] = code_id
        if (
            len(dct_code_id) == 1
            and list(dct_code_id.keys())[0]
            == "from odoo import _, api, models, fields"
        ):
            # No need to write with these default value
            dct_code_id = {}
        # Prepare code
        dct_new_code = {}
        if dct_code_id:
            for code_id in dct_code_id.values():
                # use isort to optimize it!
                sorted_code = isort.code(
                    code_id.code.strip().replace("\\b", "\\\\b")
                ).strip()
                if sorted_code != "from odoo import _, api, fields, models":
                    lst_line = sorted_code.split("\n")
                    dct_new_code[code_id] = lst_line
        code_ids = (
            self.env["code.generator.model.code"]
            .search(
                [
                    (
                        "m2o_module",
                        "=",
                        module.id,
                    ),
                    (
                        "is_templated",
                        "=",
                        True,
                    ),
                    (
                        "m2o_model",
                        "=",
                        model_id.id,
                    ),
                ]
            )
            .sorted(lambda code: code.sequence)
        )

        if dct_new_code or code_ids:
            cw.emit("# Generate code")
            cw.emit("if True:")
        with cw.indent():
            if dct_new_code:
                cw.emit("# Generate code header")
                str_line = f"\"code\": '''"
                for code_id, lst_line in dct_new_code.items():
                    with cw.block(
                        before="value =",
                        delim=("{", "}"),
                    ):
                        if len(lst_line) > 1:
                            cw.emit(str_line + lst_line[0])
                            for line in lst_line[1:-1]:
                                cw.emit_raw(line + "\n")
                            cw.emit_raw(f"{lst_line[-1]}''',\n")
                        elif lst_line:
                            cw.emit(f"{str_line}{lst_line[0]}''',")
                        cw.emit(f'"name": "{code_id.name}",')
                        if code_id.sequence:
                            cw.emit(f'"sequence": {code_id.sequence},')
                        cw.emit('"m2o_module": code_generator_id.id,')
                        model_name = model_id.model.replace(".", "_")
                        var_model_name = f"model_{model_name}"
                        cw.emit(f'"m2o_model": {var_model_name}.id,')
                    cw.emit(
                        'env["code.generator.model.code.import"].create(value)'
                    )
                    cw.emit()

            # TODO est-ce que le code est bien connecté à tous les modèles?
            if code_ids:
                cw.emit("# Generate code model")
                with cw.block(
                    before="lst_value =",
                    delim=("[", "]"),
                ):
                    for code_id in code_ids:
                        with cw.block(delim=("{", "}")):
                            lst_line = code_id.code.split("\n")
                            if len(lst_line) == 1:
                                cw.emit(f"\"code\": '''{lst_line[0]}''',")
                            else:
                                cw.emit(f"\"code\": '''{lst_line[0]}")
                            for line in lst_line[1:-1]:
                                cw.emit_raw(line + "\n")
                            if len(lst_line) > 1:
                                cw.emit_raw(f"{lst_line[-1]}''',\n")
                            cw.emit(f'"name": "{code_id.name}",')
                            if code_id.decorator:
                                cw.emit(f'"decorator": "{code_id.decorator}",')
                            if code_id.param:
                                cw.emit(f'"param": "{code_id.param}",')
                            if code_id.returns:
                                cw.emit(f'"returns": "{code_id.returns}",')
                            cw.emit(f'"sequence": {code_id.sequence},')
                            cw.emit('"m2o_module": code_generator_id.id,')
                            model_name = model_id.model.replace(".", "_")
                            var_model_name = f"model_{model_name}"
                            cw.emit(f'"m2o_model": {var_model_name}.id,')
                        cw.emit(",")
                cw.emit('env["code.generator.model.code"].create(lst_value)')
                cw.emit()

    def write_constraint(self, cw, constraint_ids, model_id):
        if not constraint_ids:
            return
        cw.emit()
        cw.emit("# Add constraint")
        cw.emit("if True:")
        with cw.indent():
            with cw.block(before="lst_value =", delim=("[", "]")):
                for constraint_id in constraint_ids:
                    with cw.block(delim=("{", "}")):
                        cw.emit(f'"name": "{constraint_id.name}",')
                        cw.emit(f'"definition": "{constraint_id.definition}",')
                        if constraint_id.message:
                            cw.emit(f'"message": "{constraint_id.message}",')
                        cw.emit(f'"type": "{constraint_id.type}",')
                        cw.emit('"code_generator_id": code_generator_id.id,')
                        cw.emit('"module": code_generator_id.id,')
                        var_model_name = (
                            f"model_{model_id.model.replace('.','_')}"
                        )
                        cw.emit(f'"model": {var_model_name}.id,')
                    cw.emit(",")
            cw.emit('env["ir.model.constraint"].create(lst_value)')
        cw.emit()

    def write_access(self, cw, access_ids, variable_model_model):
        if not access_ids:
            return
        cw.emit("# Generate access")
        cw.emit('lang = "en_US"')
        for access_id in access_ids:
            ir_model_data = self.env["ir.model.data"].search(
                [
                    ("model", "=", "res.groups"),
                    (
                        "res_id",
                        "=",
                        access_id.group_id.id,
                    ),
                ]
            )
            if not ir_model_data:
                _logger.warning(
                    "Missing information about group for creating access_id."
                )
                continue
            group_name = f"{ir_model_data.module}.{ir_model_data.name}"
            cw.emit(
                f'group_id = env.ref("{group_name}").with_context(lang=lang)'
            )
            cw.emit('access_id = env["ir.model.access"].create({')
            cw.emit(f'"name": "{access_id.name}",')
            cw.emit(f'"model_id": {variable_model_model}.id,')
            cw.emit('"group_id": group_id.id,')
            cw.emit(f'"perm_read": {access_id.perm_read},')
            cw.emit(f'"perm_create": {access_id.perm_create},')
            cw.emit(f'"perm_write": {access_id.perm_write},')
            cw.emit(f'"perm_unlink": {access_id.perm_unlink},')
            cw.emit("})")
            cw.emit()
            access_xml_id = (
                self.env["ir.model.data"]
                .search(
                    [
                        (
                            "model",
                            "=",
                            "ir.model.access",
                        ),
                        ("res_id", "=", access_id.id),
                    ]
                )
                .name
            )
            with cw.block(
                before=f'env["ir.model.data"].create',
                delim=("(", ")"),
            ):
                with cw.block(delim=("{", "}")):
                    cw.emit(f'"name": "{access_xml_id}",')
                    cw.emit(f'"model": "ir.model.access",')
                    cw.emit('"module": MODULE_NAME,')
                    cw.emit(f'"res_id": access_id.id,')
            cw.emit()

    def set_extra_get_lst_file_generate(self, module):
        super(CodeGeneratorWriter, self).set_extra_get_lst_file_generate(
            module
        )
        if (
            module.pre_init_hook_show
            or module.post_init_hook_show
            or module.uninstall_hook_show
        ):
            self._set_hook_file(module)
