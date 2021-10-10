from odoo import models, fields, api

from code_writer import CodeWriter
from odoo.models import MAGIC_COLUMNS
import logging

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

    def _write_sync_template_model(
        self,
        module,
        model_model,
        cw,
        var_model_model,
        lst_keep_f2exports,
        module_file_sync,
        view_file_sync,
        lst_force_f2exports=None,
    ):
        if module_file_sync and module_file_sync.is_enabled:
            dct_field_ast = module_file_sync.dct_model.get(model_model)
        else:
            dct_field_ast = {}
        lst_ignored_field = (
            module.ignore_fields.split(";") if module.ignore_fields else []
        )
        # TODO Check name is different before ignored it
        if lst_force_f2exports:
            f2exports = lst_force_f2exports
        else:
            if lst_ignored_field:
                lst_ignored_field += MAGIC_FIELDS
            else:
                lst_ignored_field = MAGIC_FIELDS[:]
            if "name" in dct_field_ast.keys():
                try:
                    lst_ignored_field.remove("name")
                except Exception as e:
                    print(e)
            if dct_field_ast:
                lst_search = [
                    ("model", "=", model_model),
                    ("name", "in", list(dct_field_ast.keys())),
                ]
            else:
                # Add inherit field to ignore it, this can be wrong...
                # sometime, it wants to override inherit field
                inherit_model_ids = (
                    self.env["ir.model"]
                    .search([("model", "=", model_model)])
                    .inherit_model_ids
                )
                lst_field_inherit = [
                    b.name
                    for a in inherit_model_ids
                    for b in a.depend_id.field_id
                ]
                lst_ignored_field += lst_field_inherit
                lst_ignored_field = list(set(lst_ignored_field))
                lst_search = [
                    ("model", "=", model_model),
                    ("name", "not in", lst_ignored_field),
                ]
            f2exports = self.env["ir.model.fields"].search(lst_search)

        dct_var_id_view = {}
        has_field_name = False
        for field_id in f2exports:
            if not lst_force_f2exports and field_id.ttype == "one2many":
                # TODO refactor, simplify this with a struct
                lst_keep_f2exports.append(
                    (field_id, model_model, var_model_model)
                )
                continue

            if field_id.name == "name":
                has_field_name = True

            var_value_field_name = f"value_field_{field_id.name}"
            var_id_view = f"{var_model_model}_field_{field_id.name}_id"
            dct_var_id_view[var_id_view] = field_id

            ast_attr = dct_field_ast.get(field_id.name)
            with cw.block(
                before=f"{var_value_field_name} =", delim=("{", "}")
            ):
                cw.emit(f'"name": "{field_id.name}",')
                cw.emit(f'"model": "{model_model}",')
                cw.emit(
                    f'"field_description": "{field_id.field_description}",'
                )
                if ast_attr and not module.disable_fix_code_generator_sequence:
                    cw.emit(
                        '"code_generator_sequence":'
                        f' {ast_attr.get("sequence")},'
                    )
                if view_file_sync:
                    dct_field = view_file_sync.dct_field.get(field_id.name)
                    if dct_field and dct_field.get("is_date_start_view"):
                        cw.emit(f'"is_date_start_view": True,')
                if view_file_sync:
                    dct_field = view_file_sync.dct_field.get(field_id.name)
                    if dct_field and dct_field.get("is_date_end_view"):
                        cw.emit(f'"is_date_end_view": True,')
                cw.emit(f'"ttype": "{field_id.ttype}",')
                if field_id.ttype in ["many2one", "many2many", "one2many"]:
                    # cw.emit(f'"comodel_name": "{field_id.relation}",')
                    cw.emit(f'"relation": "{field_id.relation}",')
                    if field_id.ttype == "one2many":
                        # field_many2one_ids = self.env[
                        #     "ir.model.fields"
                        # ].search(
                        #     [
                        #         ("model", "=", field_id.relation),
                        #         ("ttype", "=", "many2one"),
                        #         ("name", "not in", MAGIC_FIELDS),
                        #     ]
                        # )
                        field_many2one_ids = self.env[
                            "ir.model.fields"
                        ].search(
                            [
                                ("model", "=", field_id.relation),
                                ("ttype", "=", "many2one"),
                                ("name", "=", field_id.relation_field),
                            ]
                        )
                        if len(field_many2one_ids) == 1:
                            cw.emit(
                                '"relation_field":'
                                f' "{field_many2one_ids.name}",'
                            )
                        else:
                            _logger.error(
                                "Cannot support this situation, where is the"
                                " many2one?"
                            )
                elif field_id.ttype == "selection":
                    field_selection = (
                        self.env[model_model]
                        .fields_get(field_id.name)
                        .get(field_id.name)
                    )
                    cw.emit(
                        '"selection":'
                        f' "{str(field_selection.get("selection"))}",'
                    )
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
                    if "\n" in field_id.help:
                        cw.emit_raw(
                            f'{" " * cw.cur_indent}"help":'
                            f' "{field_id.help}",\n'
                        )
                    else:
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
                'field_x_name = env["ir.model.fields"].search([("model_id",'
                f' "=", {var_model_model}.id), ("name", "=", "x_name")])'
            )
            cw.emit(f'{var_model_model}.rec_name = "name"')
            if has_field_name:
                cw.emit("field_x_name.unlink()")
            else:
                cw.emit('field_x_name.name = "name"')

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
                    elif view_item_id.item_type == "html":
                        # TODO support help and type bg-warning
                        if view_item_id.colspan != 1:
                            cw.emit(f'"colspan": {view_item_id.colspan},')
                        if view_item_id.background_type:
                            cw.emit(
                                '"background_type":'
                                f' "{view_item_id.background_type}",'
                            )

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
            cw.emit(f'# "view_name": "view_backup_conf_form",')
            cw.emit(f'"m2o_model": {view_item.var_model_name}.id,')
            cw.emit('"view_item_ids": [(6, 0, lst_item_view)],')
            if view_id.has_body_sheet:
                cw.emit(f'"has_body_sheet": {view_id.has_body_sheet},')
            if view_id.id_name:
                cw.emit(f'"id_name": "{view_id.id_name}",')
        cw.emit(")")
        cw.emit("lst_view_id.append(view_code_generator.id)")

    def _write_sync_template_action(self, cw, module, act_server_ids):
        cw.emit("# action_server view")
        cw.emit("if True:")
        with cw.indent():
            # TODO support ir_cron here, update _write_generated_template
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

    def _write_sync_template_views(self, cw, view_item):
        if not view_item.code_generator_id:
            return
        code_generator_views_id = (
            view_item.code_generator_id.code_generator_views_id
        )
        form_view_ids = code_generator_views_id.filtered(
            lambda view_id: view_id.view_type == "form"
        )
        search_view_ids = code_generator_views_id.filtered(
            lambda view_id: view_id.view_type == "search"
        )
        tree_view_ids = code_generator_views_id.filtered(
            lambda view_id: view_id.view_type == "tree"
        )
        cw.emit("lst_view_id = []")
        cw.emit("# form view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("lst_item_view = []")

            for view_id in form_view_ids:
                tpl_ordered_section = ("header", "title", "body")
                self._write_block_template_views(
                    cw, view_id, view_item, tpl_ordered_section, "form"
                )
        cw.emit()
        cw.emit("# tree view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("lst_item_view = []")
            for view_id in tree_view_ids:
                tpl_ordered_section = ("body",)
                self._write_block_template_views(
                    cw, view_id, view_item, tpl_ordered_section, "tree"
                )

        cw.emit()
        cw.emit("# search view")
        cw.emit("if True:")
        with cw.indent():
            cw.emit("lst_item_view = []")
            for view_id in search_view_ids:
                tpl_ordered_section = ("body",)
                self._write_block_template_views(
                    cw, view_id, view_item, tpl_ordered_section, "search"
                )
        cw.emit()
        cw.emit("# act_window view")
        cw.emit("if True:")
        with cw.indent():
            if view_item.code_generator_id.code_generator_act_window_id:
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
            else:
                cw.emit("pass")
        cw.emit()
        cw.emit("# menu view")
        cw.emit("if True:")
        with cw.indent():
            if view_item.code_generator_id.code_generator_menus_id:
                for (
                    menu_id
                ) in view_item.code_generator_id.code_generator_menus_id:
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
                            cw.emit(f'"id_name": "{menu_id.id_name}",')
                            if menu_id.sequence != 10:
                                cw.emit(f'"sequence": "{menu_id.sequence}",')
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
            else:
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
        return code_generator_views_id

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

        if module.template_module_id and module.template_module_id.icon_image:
            # TODO this case need import os, find another dynamic way to specify import before write code
            cw.emit("import os")
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
            lst_inherit_module_name_added = []
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
                                "event_config ="
                                " env['res.config.settings'].sudo().create(values)"
                            )
                            cw.emit("event_config.execute()")
                    if post_init_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit()
                            cw.emit("# The path of the actual file")
                            if (
                                module.template_module_path_generated_extension
                                and module.template_module_path_generated_extension
                                != "."
                            ):
                                cw.emit(
                                    "path_module_generate ="
                                    " os.path.normpath(os.path.join(os.path.dirname"
                                    "(__file__), '..',"
                                    f" '{module.template_module_path_generated_extension}'))"
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
                                    ' "=", '
                                    f'"{module.template_module_id.category_id.display_name}")])'
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
                                cw.emit(
                                    'value["enable_template_wizard_view"] ='
                                    " False"
                                )
                                cw.emit(
                                    'value["force_generic_template_wizard_view"]'
                                    " = False"
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
                            if module.dependencies_template_id:
                                cw.emit("# Add dependencies")
                                cw.emit(
                                    "# TODO HUMAN: update your dependencies"
                                )
                                with cw.block(
                                    before="lst_depend =", delim=("[", "]")
                                ):
                                    for (
                                        depend
                                    ) in module.dependencies_template_id:
                                        cw.emit(f'"{depend.depend_id.name}",')
                                cw.emit(
                                    "code_generator_id.add_module_dependency(lst_depend)"
                                )
                                cw.emit()
                                if is_generator_demo:
                                    with cw.block(
                                        before="lst_depend =", delim=("[", "]")
                                    ):
                                        for (
                                            depend
                                        ) in module.dependencies_template_id:
                                            cw.emit(
                                                f'"{depend.depend_id.name}",'
                                            )
                                    cw.emit(
                                        "code_generator_id.add_module_dependency_template(lst_depend)"
                                    )
                                    cw.emit()

                            lst_view_item_code_generator = []
                            model_id = None
                            if module.template_model_name:
                                lst_model = module.template_model_name.split(
                                    ";"
                                )
                                len_model = len(lst_model)
                                i = -1
                                for model_model in lst_model:
                                    i += 1
                                    model_id = self.env["ir.model"].search(
                                        [("model", "=", model_model)]
                                    )
                                    if "." in model_model:
                                        (
                                            application_name,
                                            _,
                                        ) = model_model.split(".", maxsplit=1)
                                    else:
                                        application_name = model_model
                                    model_name = model_model.replace(".", "_")
                                    title_model_model = model_name.replace(
                                        "_", " "
                                    ).title()
                                    variable_model_model = (
                                        f"model_{model_name}"
                                    )
                                    cw.emit(f"# Add {title_model_model}")
                                    cw.emit("value = {")
                                    with cw.indent():
                                        cw.emit(f'"name": "{model_name}",')
                                        if (
                                            model_id
                                            and model_id.description
                                            and model_id.description
                                            != model_name
                                        ):
                                            cw.emit(
                                                '"description":'
                                                f' "{model_id.description}",'
                                            )
                                        cw.emit(f'"model": "{model_model}",')
                                        cw.emit(
                                            '"m2o_module":'
                                            " code_generator_id.id,"
                                        )
                                        cw.emit('"rec_name": None,')
                                        if application_name.lower() == "demo":
                                            cw.emit(
                                                '"menu_name_keep_application":'
                                                " True,"
                                            )
                                        if model_id.enable_activity:
                                            cw.emit('"enable_activity": True,')
                                        if (
                                            model_id.diagram_node_object
                                            and model_id.diagram_node_xpos_field
                                            and model_id.diagram_node_ypos_field
                                            and model_id.diagram_arrow_object
                                            and model_id.diagram_arrow_src_field
                                            and model_id.diagram_arrow_dst_field
                                        ):
                                            cw.emit(
                                                '"diagram_node_object":'
                                                f' "{model_id.diagram_node_object}",'
                                            )
                                            cw.emit(
                                                '"diagram_node_xpos_field":'
                                                f' "{model_id.diagram_node_xpos_field}",'
                                            )
                                            cw.emit(
                                                '"diagram_node_ypos_field":'
                                                f' "{model_id.diagram_node_ypos_field}",'
                                            )
                                            if (
                                                model_id.diagram_node_shape_field
                                            ):
                                                cw.emit(
                                                    '"diagram_node_shape_field":'
                                                    f' "{model_id.diagram_node_shape_field}",'
                                                )
                                            if (
                                                model_id.diagram_node_form_view_ref
                                            ):
                                                # TODO validate it exist and add variable to link name if changed
                                                cw.emit(
                                                    '"diagram_node_form_view_ref":'
                                                    f' "{model_id.diagram_node_form_view_ref}",'
                                                )
                                            cw.emit(
                                                '"diagram_arrow_object":'
                                                f' "{model_id.diagram_arrow_object}",'
                                            )
                                            cw.emit(
                                                '"diagram_arrow_src_field":'
                                                f' "{model_id.diagram_arrow_src_field}",'
                                            )
                                            cw.emit(
                                                '"diagram_arrow_dst_field":'
                                                f' "{model_id.diagram_arrow_dst_field}",'
                                            )
                                            if model_id.diagram_arrow_label:
                                                cw.emit(
                                                    '"diagram_arrow_label":'
                                                    f' "{model_id.diagram_arrow_label}",'
                                                )
                                            if (
                                                model_id.diagram_arrow_form_view_ref
                                            ):
                                                # TODO validate it exist and add variable to link name if changed
                                                cw.emit(
                                                    '"diagram_arrow_form_view_ref":'
                                                    f' "{model_id.diagram_arrow_form_view_ref}",'
                                                )
                                            if model_id.diagram_label_string:
                                                cw.emit(
                                                    '"diagram_label_string":'
                                                    f' "{model_id.diagram_label_string}",'
                                                )
                                        cw.emit('"nomenclator": True,')
                                    cw.emit("}")
                                    cw.emit(
                                        f"{variable_model_model} ="
                                        ' env["ir.model"].create(value)'
                                    )
                                    cw.emit()
                                    # inherit
                                    if model_id and model_id.inherit_model_ids:
                                        if (
                                            module.template_module_id
                                            and module.template_module_id.dependencies_id
                                        ):
                                            lst_module_depend = sorted(
                                                list(
                                                    set(
                                                        [
                                                            a.name
                                                            for a in module.template_module_id.dependencies_id
                                                        ]
                                                    ).difference(
                                                        set(
                                                            lst_inherit_module_name_added
                                                        )
                                                    )
                                                )
                                            )
                                        if lst_module_depend:
                                            lst_inherit_module_name_added += (
                                                lst_module_depend
                                            )
                                            cw.emit("# Module dependency")
                                            if len(lst_module_depend) == 1:
                                                dependency_name = (
                                                    module.template_module_id.dependencies_id.name
                                                )
                                                cw.emit(
                                                    f"code_generator_id.add_module_dependency('{dependency_name}')"
                                                )
                                            else:
                                                cw.emit(
                                                    "lst_depend_module ="
                                                    f" {str(lst_module_depend)}"
                                                )
                                                cw.emit(
                                                    f"code_generator_id.add_module_dependency(lst_depend_module)"
                                                )
                                            cw.emit()

                                        lst_dependency = [
                                            a.name
                                            for a in model_id.inherit_model_ids
                                        ]
                                        if lst_dependency:
                                            cw.emit("# Model inherit")
                                            if len(lst_dependency) == 1:
                                                cw.emit(
                                                    f"{variable_model_model}.add_model_inherit('{lst_dependency[0]}')"
                                                )
                                            else:
                                                cw.emit(
                                                    "lst_depend_model ="
                                                    f" {str(lst_dependency)}"
                                                )
                                                cw.emit(
                                                    f"{variable_model_model}.add_model_inherit(lst_depend_model)"
                                                )
                                        cw.emit()
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
                                                    '"depend":'
                                                    f' "{ext_depend.depend}",'
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
                                    self._write_generated_template(
                                        module, model_model, cw
                                    )
                                    cw.emit("##### Begin Field")
                                    if module.enable_sync_template:
                                        module_file_sync = (
                                            module.module_file_sync.get(
                                                model_model
                                            )
                                        )
                                        view_file_sync = (
                                            module.view_file_sync.get(
                                                model_model
                                            )
                                        )
                                        if view_file_sync:
                                            lst_view_item_code_generator.append(
                                                view_file_sync
                                            )
                                        self._write_sync_template_model(
                                            module,
                                            model_model,
                                            cw,
                                            variable_model_model,
                                            lst_keep_f2exports,
                                            module_file_sync,
                                            view_file_sync,
                                        )
                                    else:
                                        cw.emit("value_field_boolean = {")
                                        with cw.indent():
                                            cw.emit('"name": "field_boolean",')
                                            cw.emit('"model": "demo.model",')
                                            cw.emit(
                                                '"field_description": "field'
                                                ' description",'
                                            )
                                            cw.emit('"ttype": "boolean",')
                                            cw.emit(
                                                '"model_id":'
                                                f" {variable_model_model}.id,"
                                            )
                                        cw.emit("}")
                                        cw.emit(
                                            'env["ir.model.fields"].create(value_field_boolean)'
                                        )
                                        cw.emit()
                                        cw.emit("# FIELD TYPE Many2one")
                                        cw.emit("#value_field_many2one = {")
                                        with cw.indent():
                                            cw.emit(
                                                '#"name": "field_many2one",'
                                            )
                                            cw.emit('#"model": "demo.model",')
                                            cw.emit(
                                                '#"field_description": "field'
                                                ' description",'
                                            )
                                            cw.emit('#"ttype": "many2one",')
                                            # cw.emit(
                                            #     '#"comodel_name":'
                                            #     ' "model.name",'
                                            # )
                                            cw.emit(
                                                '#"relation": "model.name",'
                                            )
                                            cw.emit(
                                                '#"model_id":'
                                                f" {variable_model_model}.id,"
                                            )
                                        cw.emit("#}")
                                        cw.emit(
                                            '#env["ir.model.fields"].create(value_field_many2one)'
                                        )
                                        cw.emit("")
                                        cw.emit("# Hack to solve field name")
                                        cw.emit(
                                            "field_x_name ="
                                            " env[\"ir.model.fields\"].search([('model_id',"
                                            " '=',"
                                            f" {variable_model_model}.id),"
                                            " ('name', '=', 'x_name')])"
                                        )
                                        cw.emit('field_x_name.name = "name"')
                                        cw.emit(
                                            f"{variable_model_model}.rec_name"
                                            ' = "name"'
                                        )
                                        cw.emit("")
                                    if (
                                        i >= len_model - 1
                                        and lst_keep_f2exports
                                    ):
                                        cw.emit("")
                                        cw.emit(
                                            "# Added one2many field, many2many"
                                            " need to be create before add"
                                            " one2many"
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
                                    # Generate code
                                    code_import_ids = (
                                        self.env[
                                            "code.generator.model.code.import"
                                        ]
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
                                        == "from odoo import _, api, models,"
                                        " fields"
                                    ):
                                        # No need to write with these default value
                                        dct_code_id = {}
                                    if dct_code_id:
                                        cw.emit("# Generate code")
                                        cw.emit("if True:")
                                        with cw.indent():
                                            cw.emit("# Generate code header")
                                            for code_id in dct_code_id.value():
                                                with cw.block(
                                                    before="value =",
                                                    delim=("{", "}"),
                                                ):
                                                    str_line = f"\"code\": '''"
                                                    lst_line = (
                                                        code_id.code.split(
                                                            "\n"
                                                        )
                                                    )
                                                    cw.emit(
                                                        str_line + lst_line[0]
                                                    )
                                                    for line in lst_line[1:-1]:
                                                        # str_line += line
                                                        cw.emit_raw(
                                                            line + "\n"
                                                        )
                                                        # str_line = ""
                                                    cw.emit_raw(
                                                        f"{lst_line[-1]}''',\n"
                                                    )
                                                    cw.emit(
                                                        '"name":'
                                                        f' "{code_id.name}",'
                                                    )
                                                    if code_id.sequence:
                                                        cw.emit(
                                                            '"sequence":'
                                                            f" {code_id.sequence},"
                                                        )
                                                    cw.emit(
                                                        '"m2o_module":'
                                                        " code_generator_id.id,"
                                                    )
                                                    model_name = (
                                                        model_model.replace(
                                                            ".", "_"
                                                        )
                                                    )
                                                    var_model_name = (
                                                        f"model_{model_name}"
                                                    )
                                                    cw.emit(
                                                        '"m2o_model":'
                                                        f" {var_model_name}.id,"
                                                    )
                                                cw.emit(
                                                    'env["code.generator.model.code.import"].create(value)'
                                                )
                                                cw.emit()
                                            code_ids = (
                                                self.env[
                                                    "code.generator.model.code"
                                                ]
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
                                                    ]
                                                )
                                                .sorted(
                                                    lambda code: code.sequence
                                                )
                                            )

                                            if code_ids:
                                                cw.emit(
                                                    "# Generate code model"
                                                )
                                                with cw.block(
                                                    before="lst_value =",
                                                    delim=("[", "]"),
                                                ):
                                                    for code_id in code_ids:
                                                        with cw.block(
                                                            delim=("{", "}")
                                                        ):
                                                            str_line = (
                                                                f"\"code\": '''"
                                                            )
                                                            lst_line = code_id.code.split(
                                                                "\n"
                                                            )
                                                            cw.emit(
                                                                str_line
                                                                + lst_line[0]
                                                            )
                                                            for (
                                                                line
                                                            ) in lst_line[
                                                                1:-1
                                                            ]:
                                                                # str_line += line
                                                                cw.emit_raw(
                                                                    line + "\n"
                                                                )
                                                                # str_line = ""
                                                            cw.emit_raw(
                                                                f"{lst_line[-1]}''',\n"
                                                            )
                                                            cw.emit(
                                                                '"name":'
                                                                f' "{code_id.name}",'
                                                            )
                                                            if (
                                                                code_id.decorator
                                                            ):
                                                                cw.emit(
                                                                    '"decorator":'
                                                                    f' "{code_id.decorator}",'
                                                                )
                                                            if code_id.param:
                                                                cw.emit(
                                                                    '"param":'
                                                                    f' "{code_id.param}",'
                                                                )
                                                            if code_id.returns:
                                                                cw.emit(
                                                                    '"returns":'
                                                                    f' "{code_id.returns}",'
                                                                )
                                                            cw.emit(
                                                                '"sequence":'
                                                                f" {code_id.sequence},"
                                                            )
                                                            cw.emit(
                                                                '"m2o_module":'
                                                                " code_generator_id.id,"
                                                            )
                                                            model_name = model_model.replace(
                                                                ".", "_"
                                                            )
                                                            var_model_name = f"model_{model_name}"
                                                            cw.emit(
                                                                '"m2o_model":'
                                                                f" {var_model_name}.id,"
                                                            )
                                                        cw.emit(",")
                                                cw.emit(
                                                    'env["code.generator.model.code"].create(lst_value)'
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
                                cw.emit()
                                cw.emit("# Add constraint")
                                cw.emit("if True:")
                                with cw.indent():
                                    with cw.block(
                                        before="lst_value =", delim=("[", "]")
                                    ):
                                        for constraint_id in constraint_ids:
                                            with cw.block(delim=("{", "}")):
                                                cw.emit(
                                                    '"name":'
                                                    f' "{constraint_id.name}",'
                                                )
                                                cw.emit(
                                                    '"definition":'
                                                    f' "{constraint_id.definition}",'
                                                )
                                                if constraint_id.message:
                                                    cw.emit(
                                                        '"message":'
                                                        f' "{constraint_id.message}",'
                                                    )
                                                cw.emit(
                                                    '"type":'
                                                    f' "{constraint_id.type}",'
                                                )
                                                cw.emit(
                                                    '"code_generator_id":'
                                                    " code_generator_id.id,"
                                                )
                                                cw.emit(
                                                    '"module":'
                                                    " code_generator_id.id,"
                                                )
                                                model_name = (
                                                    model_model.replace(
                                                        ".", "_"
                                                    )
                                                )
                                                var_model_name = (
                                                    f"model_{model_name}"
                                                )
                                                cw.emit(
                                                    '"model":'
                                                    f" {var_model_name}.id,"
                                                )
                                            cw.emit(",")
                                    cw.emit(
                                        'env["ir.model.constraint"].create(lst_value)'
                                    )
                                cw.emit()

                            access_ids = None
                            if module.enable_template_wizard_view and model_id:
                                # Icon copy from sync
                                if module.enable_sync_template:
                                    if (
                                        module.template_module_id.icon_image
                                        and not module.icon_child_image
                                    ):
                                        module.icon_child_image = (
                                            module.template_module_id.icon_image
                                        )

                                if (
                                    not module.force_generic_template_wizard_view
                                ):
                                    access_ids = self.env[
                                        "ir.model.access"
                                    ].search([("model_id", "=", model_id.id)])
                                else:
                                    access_ids = None
                                cw.emit("# Generate view")
                                custom_view = (
                                    module.enable_sync_template
                                    and not module.force_generic_template_wizard_view
                                )
                                has_custom_view = False
                                if custom_view:
                                    for (
                                        view_item
                                    ) in lst_view_item_code_generator:
                                        if not view_item:
                                            continue
                                        i += 1
                                        cw.emit("##### Begin Views")
                                        view_id = (
                                            self._write_sync_template_views(
                                                cw, view_item
                                            )
                                        )
                                        if view_id:
                                            has_custom_view = True
                                        cw.emit("##### End Views")
                                        cw.emit()

                                act_server_ids = self.env[
                                    "ir.actions.server"
                                ].search(
                                    [
                                        ("model_name", "=", model_model),
                                        ("usage", "=", "ir_actions_server"),
                                        ("model_id", "=", model_id.id),
                                    ]
                                )
                                if act_server_ids:
                                    cw.emit("# Generate server action")
                                    self._write_sync_template_action(
                                        cw, module, act_server_ids
                                    )

                                cw.emit("# Action generate view")
                                cw.emit(
                                    "wizard_view ="
                                    " env['code.generator.generate.views.wizard'].create({"
                                )
                                with cw.indent():
                                    cw.emit(
                                        "'code_generator_id':"
                                        " code_generator_id.id,"
                                    )
                                    cw.emit("'enable_generate_all': False,")
                                    if has_custom_view:
                                        cw.emit(
                                            '"code_generator_view_ids": [(6,'
                                            " 0, lst_view_id)],"
                                        )
                                    if module.enable_generate_portal:
                                        cw.emit(
                                            "'enable_generate_portal':"
                                            f" {module.enable_generate_portal},"
                                        )

                                    if access_ids:
                                        cw.emit(
                                            "'disable_generate_access': True"
                                        )
                                cw.emit("})")
                                cw.emit("")
                                cw.emit("wizard_view.button_generate_views()")
                                cw.emit()

                            if access_ids:
                                cw.emit("# Generate access")
                                cw.emit('lang = "en_US"')
                                for access_id in access_ids:
                                    ir_model_data = self.env[
                                        "ir.model.data"
                                    ].search(
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
                                            "Missing information about group"
                                            " for creating access_id."
                                        )
                                        continue
                                    group_name = f"{ir_model_data.module}.{ir_model_data.name}"
                                    cw.emit(
                                        "group_id ="
                                        f' env.ref("{group_name}").with_context(lang=lang)'
                                    )
                                    cw.emit(
                                        "access_id ="
                                        ' env["ir.model.access"].create({'
                                    )
                                    cw.emit(f'"name": "{access_id.name}",')
                                    cw.emit(
                                        '"model_id":'
                                        f" {variable_model_model}.id,"
                                    )
                                    cw.emit('"group_id": group_id.id,')
                                    cw.emit(
                                        f'"perm_read": {access_id.perm_read},'
                                    )
                                    cw.emit(
                                        '"perm_create":'
                                        f" {access_id.perm_create},"
                                    )
                                    cw.emit(
                                        '"perm_write":'
                                        f" {access_id.perm_write},"
                                    )
                                    cw.emit(
                                        '"perm_unlink":'
                                        f" {access_id.perm_unlink},"
                                    )
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
                                            cw.emit(
                                                f'"name": "{access_xml_id}",'
                                            )
                                            cw.emit(
                                                f'"model": "ir.model.access",'
                                            )
                                            cw.emit('"module": MODULE_NAME,')
                                            cw.emit(f'"res_id": access_id.id,')
                                    cw.emit()

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
