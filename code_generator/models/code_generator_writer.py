from odoo import models, fields, api

import os
import shutil
import tempfile
import uuid
from lxml.builder import E
from lxml import etree as ET
from collections import defaultdict

from code_writer import CodeWriter
from odoo.models import MAGIC_COLUMNS

UNDEFINEDMESSAGE = 'Restriction message not yet define.'
MAGIC_FIELDS = MAGIC_COLUMNS + ['display_name', '__last_update', 'access_url', 'access_token', 'access_warning']
MODULE_NAME = 'code_generator'
BLANK_LINE = ['']
BREAK_LINE_OFF = '\n'
BREAK_LINE = ['\n']
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF
XML_VERSION = ['<?xml version= "1.0" encoding="utf-8"?>']
XML_ODOO_OPENING_TAG = ['<odoo>']
XML_HEAD = XML_VERSION + XML_ODOO_OPENING_TAG
XML_ODOO_CLOSING_TAG = ['</odoo>']
FROM_ODOO_IMPORTS = ['from odoo import _, api, models, fields']
MODEL_HEAD = FROM_ODOO_IMPORTS + BREAK_LINE
FROM_ODOO_IMPORTS_SUPERUSER = ['from odoo import _, api, models, fields, SUPERUSER_ID']
MODEL_SUPERUSER_HEAD = FROM_ODOO_IMPORTS_SUPERUSER + BREAK_LINE


class CodeGeneratorWriter(models.Model):
    _name = 'code.generator.writer'
    _description = 'Code Generator Writer'

    code_generator_ids = fields.Many2many(comodel_name="code.generator.module")

    list_path_file = fields.Char(string="List path file", help="Value are separated by ;")

    rootdir = fields.Char(string="Root dir")

    basename = fields.Char(string="Base name")

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
        bypoint = model.split('.')
        for byp in bypoint:
            result += byp.split('_')
        return ''.join(self._get_l_map(lambda e: e.capitalize(), result))

    @staticmethod
    def _lower_replace(string, replacee=' ', replacer='_'):
        """
        Util function to replace and get the lower content of a string
        :param string:
        :return:
        """

        return str(string).lower().replace(replacee, replacer)

    def _get_model_model(self, model_model, replacee='.'):
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

        class_4inherit = 'models.TransientModel' if model.transient else \
            ('models.AbstractModel' if model._abstract else 'models.Model')
        if model.m2o_inherit_py_class.name:
            class_4inherit += ', %s' % model.m2o_inherit_py_class.name

        return class_4inherit

    def _get_odoo_ttype_class(self, ttype):
        """
        Util function to get a field class name from a field type (char -> Char, many2one -> Many2one)
        :param ttype:
        :return:
        """

        return f'fields.{self._get_class_name(ttype)}'

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

        return '%s...' % xmlid[:61 - len(xmlid)] if (64 - len(xmlid)) < 0 else xmlid

    @staticmethod
    def _prepare_compute_constrained_fields(l_fields):
        """

        :param l_fields:
        :return:
        """

        counter = 1
        prepared = ''
        for field in l_fields:
            prepared += '\'%s\'%s' % (field, ', ' if counter < len(l_fields) else '')
            counter += 1

        return prepared

    def _get_model_constrains(self, cw, model):
        """
        Function to obtain the model constrains
        :param model:
        :return:
        """

        if model.o2m_server_constrains:

            cw.emit()

            for sconstrain in model.o2m_server_constrains:
                l_constrained = self._get_l_map(lambda e: e.strip(), sconstrain.constrained.split(','))

                cw.emit(f"@api.constrains({self._prepare_compute_constrained_fields(l_constrained)})")
                cw.emit(f"def _check_{'_'.join(l_constrained)}(self):")

                l_code = sconstrain.txt_code.split('\n')
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

        if model.o2m_constraints:

            with cw.indent():
                lst_constraint = []
                constraint_counter = 0
                for constraint in model.o2m_constraints:
                    constraint_name = constraint.name.replace('%s_' % self._get_model_model(model.model), '')
                    constraint_definition = constraint.definition
                    constraint_message = constraint.message if constraint.message else UNDEFINEDMESSAGE
                    constraint_counter += 1
                    constraint_separator = ',' if constraint_counter < len(model.o2m_constraints) else ''

                    lst_constraint.append(f"('{constraint_name}', '{constraint_definition}', '{constraint_message}')"
                                          f"{constraint_separator}")

                cw.emit_list(lst_constraint, ('[', ']'), before='_sql_constraints = ')

            cw.emit()

    def _set_static_description_file(self, module, application_icon):
        """
        Function to set the static descriptions files
        :param module:
        :param application_icon:
        :return:
        """

        static_description_icon_path = ""
        # TODO hack to force icon or True
        if module.icon_image or True:
            static_description_icon_path = os.path.join(self.code_generator_data.static_description_path, 'icon.png')

            # TODO use this when fix loading picture, now temporary disabled and force use icon from menu
            # self.code_generator_data.write_file_binary(static_description_icon_path,
            # base64.b64decode(module.icon_image))
            # TODO temp solution with icon from menu
            if application_icon:
                icon_path = application_icon[application_icon.find(",") + 1:]
                # icon_path = application_icon.replace(",", "/")
            else:
                icon_path = "static/description/icon_new_application.png"
            icon_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", icon_path))
            with open(icon_path, "rb") as file:
                content = file.read()
                self.code_generator_data.write_file_binary(static_description_icon_path, content)

        return static_description_icon_path

    @staticmethod
    def _get_from_rec_name(record, model):
        """
        Util function to handle the _rec_name / rec_name access
        :param record:
        :param model:
        :return:
        """

        return getattr(record, model._rec_name) if getattr(record, model._rec_name) else getattr(record, model.rec_name)

    def set_module_init_file_extra(self, module):
        pass

    def _set_manifest_file(self, module):
        """
        Function to set the module manifest file
        :param module:
        :return:
        """

        lang = "en_US"

        cw = CodeWriter()
        with cw.block(delim=('{', '}')):
            cw.emit(f"'name': '{module.shortdesc}',")

            if module.category_id:
                cw.emit(f"'category': '{module.category_id.with_context(lang=lang).name}',")

            if module.summary and module.summary != 'false':
                cw.emit(f"'summary': '{module.summary}',")

            if module.description:
                cw.emit(f"'description': '{module.description}',")

            if module.installed_version:
                cw.emit(f"'version': '{module.installed_version}',")

            if module.author:
                cw.emit(f"'author': '{module.author}',")

            if module.url:
                cw.emit(f"'author': '{module.author}',")

            if module.sequence != 100:
                cw.emit(f"'sequence': {module.sequence},")

            if module.contributors:
                cw.emit(f"'contributors': '{module.contributors}',")

            # if module.maintener:
            #     cw.emit(f"'maintainers': '{module.maintener}',")

            if module.website:
                cw.emit(f"'website': '{module.website}',")

            if module.auto_install:
                cw.emit(f"'auto_install': True,")

            if module.demo:
                cw.emit(f"'demo': True,")

            if module.license != 'LGPL-3':
                cw.emit(f"'license': '{module.license}',")

            if module.application:
                cw.emit(f"'application': True,")

            if module.dependencies_id:
                lst_depend = module.dependencies_id.mapped(lambda did: f"'{did.depend_id.name}'")
                cw.emit_list(lst_depend, ('[', ']'), before="'depends': ", after=',')

            if module.external_dependencies_id:
                with cw.block(before="'external_dependencies':", delim=('{', '}'), after=','):
                    dct_depend = defaultdict(list)
                    for depend in module.external_dependencies_id:
                        dct_depend[depend.application_type].append(f"'{depend.depend}'")
                    for application_type, lst_value in dct_depend.items():
                        cw.emit_list(lst_value, ('[', ']'), before=f"'{application_type}': ", after=',')

            lst_data = self._get_l_map(lambda dfile: f"'{dfile}'", self.code_generator_data.lst_manifest_data_files)
            if lst_data:
                cw.emit_list(lst_data, ('[', ']'), before="'data': ", after=',')

            cw.emit(f"'installable': True,")

            self.set_manifest_file_extra(cw, module)

        manifest_file_path = '__manifest__.py'
        self.code_generator_data.write_file_str(manifest_file_path, cw.render())

    def set_manifest_file_extra(self, cw, module):
        pass

    def _get_ir_model_data(self, record, give_a_default=False):
        """
        Function to obtain the model data from a record
        :param record:
        :param give_a_default:
        :return:
        """

        ir_model_data = self.env['ir.model.data'].search([
            # TODO: Opción por valorar
            # ('module', '!=', '__export__'),
            ('model', '=', record._name),
            ('res_id', '=', record.id)
        ])
        return '%s.%s' % (ir_model_data[0].module, ir_model_data[0].name) if ir_model_data else \
            (self._set_limit_4xmlid('%s_%s' % (
                self._get_model_model(record._name),
                self._lower_replace(getattr(record, record._rec_name) if record._rec_name else '')
            ))) if give_a_default else False

    def _get_group_data_name(self, group):
        """
        Function to obtain the res_id-like group name (Code Generator / Manager -> code_generator_manager)
        :param group:
        :return:
        """

        return self._get_ir_model_data(group) if self._get_ir_model_data(group) else self._lower_replace(
            group.name.replace(' /', ''))

    def _get_model_data_name(self, model):
        """
        Function to obtain the res_id-like model name (code.generator.module -> code_generator_module)
        :param model:
        :return:
        """

        return self._get_ir_model_data(model) if self._get_ir_model_data(model) else 'model_%s' % self._get_model_model(
            model.model)

    def _get_view_data_name(self, view):
        """
        Function to obtain the res_id-like view name
        :param view:
        :return:
        """

        return self._get_ir_model_data(view) if self._get_ir_model_data(view) else \
            '%s_%sview' % (self._get_model_model(view.model), view.type)

    def _get_action_data_name(self, action, server=False, creating=False):
        """
        Function to obtain the res_id-like action name
        :param action:
        :param server:
        :param creating:
        :return:
        """

        if not creating and self._get_ir_model_data(action):
            return self._get_ir_model_data(action)

        else:
            model = getattr(action, 'res_model') if not server else getattr(action, 'model_id').model
            model_model = self._get_model_model(model)
            action_type = 'action_window' if not server else 'server_action'

            action_name = self._set_limit_4xmlid('%s' % action.name[:64 - len(model_model) - len(action_type)])

            return '%s_%s_%s' % (model_model, self._lower_replace(action_name), action_type)

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

        return self._get_ir_model_data(menu) if self._get_ir_model_data(menu) else self._lower_replace(menu.name)

    def _set_model_xmldata_file(self, model, model_model):
        """
        Function to set the module data file
        :param model:
        :param model_model:
        :return:
        """

        nomenclador_data = self.env[model.model].sudo().search([])
        if not nomenclador_data:
            return

        lst_menu_xml = []
        lst_id = []
        lst_depend = []
        lst_field_id_blacklist = [a.m2o_fields.id for a in model.m2o_module.o2m_nomenclator_blacklist_fields]
        lst_field_id_whitelist = [a.m2o_fields.id for a in model.m2o_module.o2m_nomenclator_whitelist_fields]
        for record in nomenclador_data:

            f2exports = model.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS)
            lst_field = []
            for rfield in f2exports:
                # whitelist check
                if lst_field_id_whitelist and rfield.id not in lst_field_id_whitelist:
                    continue
                # blacklist check
                if rfield.id in lst_field_id_blacklist:
                    continue
                record_value = getattr(record, rfield.name)
                if record_value:

                    if rfield.ttype == 'many2one':
                        ref = self._get_ir_model_data(record_value, give_a_default=True)
                        child = E.field({"name": rfield.name, "ref": ref})

                        if "." not in ref:
                            lst_depend.append(ref)

                    elif rfield.ttype == 'one2many':
                        field_eval = ', '.join(
                            record_value.mapped(lambda rvalue: '(4, ref(\'%s\'))' % self._get_ir_model_data(
                                rvalue, give_a_default=True
                            ))
                        )
                        child = E.field({"name": rfield.name, "eval": f"[{field_eval}]"})

                    elif rfield.ttype == 'many2many':
                        # TODO add dependencies id in lst_depend
                        field_eval = ', '.join(
                            record_value.mapped(lambda rvalue: 'ref(%s)' % self._get_ir_model_data(
                                rvalue, give_a_default=True
                            )))
                        child = E.field({"name": rfield.name, "eval": f"[(6,0, [{field_eval}])]"})

                    else:
                        child = E.field({"name": rfield.name}, str(record_value))

                    lst_field.append(child)

            id_record = self._set_limit_4xmlid('%s_%s') % (
                model_model,
                self._lower_replace(self._get_from_rec_name(record, model)) if self._get_from_rec_name(record,
                                                                                                       model)
                else uuid.uuid1().int
            )
            lst_id.append(id_record)
            record_xml = E.record({"model": model.model, "id": id_record}, *lst_field)
            lst_menu_xml.append(record_xml)

        module_file = E.odoo({}, *lst_menu_xml)
        data_file_path = os.path.join(self.code_generator_data.data_path, f'{model_model}.xml')
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(module_file, pretty_print=True)
        self.code_generator_data.write_file_binary(data_file_path, result, data_file=True)

        abs_path_file = os.path.join('data', f'{model_model}.xml')

        self.code_generator_data.dct_data_metadata_file[abs_path_file] = lst_id
        if lst_depend:
            self.code_generator_data.dct_data_depend[abs_path_file] = lst_depend

    def _set_module_menus(self, module):
        """
        Function to set the module menus file
        :param module:
        :return:
        """

        application_icon = None
        menus = module.with_context({'ir.ui.menu.full_list': True}).o2m_menus
        lst_menu = []
        lst_items = [a for a in menus]
        # Sorted menu by order of parent asc, and sort child by view_name
        while lst_items:
            has_update = False
            lst_item_cache = []
            for item in lst_items[:]:
                # Expect first menu by id is a root menu
                if not item.parent_id:
                    lst_menu.append(item)
                    lst_items.remove(item)
                    has_update = True
                elif item.parent_id in lst_menu:
                    lst_item_cache.append(item)
                    lst_items.remove(item)
                    has_update = True

            # Order last run of adding
            if lst_item_cache:
                lst_item_cache = sorted(lst_item_cache, key=lambda menu: self._get_menu_data_name(menu))
                lst_menu += lst_item_cache

            if not has_update:
                lst_sorted_item = sorted(lst_items, key=lambda menu: self._get_menu_data_name(menu))
                for item in lst_sorted_item:
                    lst_menu.append(item)

        if not lst_menu:
            return ""

        lst_menu_xml = []

        for menu in lst_menu:

            dct_menu_item = {
                "id": self._get_menu_data_name(menu),
                "name": menu.name
            }

            if menu.action:
                dct_menu_item["action"] = self._get_action_data_name(menu.action)

            if not menu.active:
                dct_menu_item["active"] = "False"

            if menu.sequence != 10:
                dct_menu_item["sequence"] = str(menu.sequence)

            if menu.parent_id:
                dct_menu_item["parent"] = self._get_menu_data_name(menu.parent_id)

            if menu.groups_id:
                dct_menu_item["groups"] = self._get_m2m_groups(menu.groups_id)

            if menu.web_icon:
                # TODO move application_icon in code_generator_data
                application_icon = menu.web_icon
                # ignore actual icon, force a new icon
                dct_menu_item["web_icon"] = f'{module.name},static/description/icon.png'

            menu_xml = E.menuitem(dct_menu_item)
            lst_menu_xml.append(menu_xml)

        module_menus_file = E.odoo({}, *lst_menu_xml)
        menu_file_path = os.path.join(self.code_generator_data.views_path, 'menus.xml')
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(module_menus_file, pretty_print=True)
        self.code_generator_data.write_file_binary(menu_file_path, result, data_file=True)

        return application_icon

    def _set_model_xmlview_file(self, model, model_model):
        """
        Function to set the model xml files
        :param model:
        :param model_model:
        :return:
        """

        if not (model.view_ids or model.o2m_act_window or model.o2m_server_action):
            return

        l_model_view_file = XML_HEAD + BLANK_LINE

        lst_id = []

        #
        # Views
        #
        for view in model.view_ids:

            view_type = view.type

            if view_type in ["tree", "form"]:

                str_id = f"{model_model}_view_{view_type}"
                if str_id in lst_id:
                    count_id = lst_id.count(str_id)
                    str_id += str(count_id)
                lst_id.append(str_id)

                self.code_generator_data.add_view_id(view.name, str_id)

                l_model_view_file.append(f'<record model="ir.ui.view" id="{str_id}">')

                if view.name:
                    l_model_view_file.append('<field name="name">%s</field>' % view.name)

                l_model_view_file.append('<field name="model">%s</field>' % view.model)

                if view.key:
                    l_model_view_file.append('<field name="key">%s</field>' % view.key)

                if view.priority != 16:
                    l_model_view_file.append('<field name="priority">%s</field>' % view.priority)

                if view.inherit_id:
                    l_model_view_file.append('<field name="inherit_id" ref="%s"/>' % self._get_view_data_name(view))

                    if view.mode == 'primary':
                        l_model_view_file.append('<field name="mode">primary</field>')

                if not view.active:
                    l_model_view_file.append('<field name="active" eval="False" />')

                if view.arch_db:
                    l_model_view_file.append('<field name="arch" type="xml">%s</field>' % view.arch_db)

                if view.groups_id:
                    l_model_view_file.append(self._get_m2m_groups(view.groups_id))

                l_model_view_file.append('</record>\n')

            elif view_type == "qweb":

                if view.inherit_id:
                    l_model_view_file.append(
                        f'<template id="{view.key}" name="{view.name}" inherit_id="{view.inherit_id.key}">')
                else:
                    l_model_view_file.append(f'<template id="{view.key}" name="{view.name}">')

                l_model_view_file.append(view.arch)
                l_model_view_file.append('</template>\n')

            else:
                print(f"Error, view type {view_type} of {view.name} not supported.")

        #
        # Action Windows
        #
        for act_window in model.o2m_act_window:

            l_model_view_file.append(
                '<record model="ir.actions.act_window" id="%s">' % self._get_action_data_name(act_window,
                                                                                              creating=True)
            )

            if act_window.name:
                l_model_view_file.append('<field name="name">%s</field>' % act_window.name)

            if act_window.res_model or act_window.m2o_res_model:
                l_model_view_file.append(
                    '<field name="res_model">%s</field>' % act_window.res_model or act_window.m2o_res_model.model
                )

            if act_window.binding_model_id:
                l_model_view_file.append(
                    '<field name="binding_model_id" ref="%s" />' % self._get_model_data_name(
                        act_window.binding_model_id)
                )

            if act_window.view_id:
                l_model_view_file.append(
                    '<field name="view_id" ref="%s" />' % self._get_view_data_name(act_window.view_id))

            if act_window.domain != '[]' and act_window.domain:
                l_model_view_file.append('<field name="domain">%s</field>' % act_window.domain)

            if act_window.context != '{}':
                l_model_view_file.append('<field name="context">%s</field>' % act_window.context)

            if act_window.src_model or act_window.m2o_src_model:
                l_model_view_file.append(
                    '<field name="src_model">%s</field>' % act_window.src_model or act_window.m2o_src_model.model
                )

            if act_window.target != 'current':
                l_model_view_file.append('<field name="target">%s</field>' % act_window.target)

            if act_window.view_mode != 'tree,form':
                l_model_view_file.append('<field name="view_mode">%s</field>' % act_window.view_mode)

            if act_window.view_type != 'form':
                l_model_view_file.append('<field name="view_type">%s</field>' % act_window.view_type)

            if act_window.usage:
                l_model_view_file.append('<field name="usage" eval="True" />')

            if act_window.limit != 80:
                l_model_view_file.append('<field name="limit">%s</field>' % act_window.limit)

            if act_window.search_view_id:
                l_model_view_file.append(
                    '<field name="search_view_id" ref="%s" />' % self._get_view_data_name(act_window.search_view_id)
                )

            if act_window.filter:
                l_model_view_file.append('<field name="filter" eval="True" />')

            if not act_window.auto_search:
                l_model_view_file.append('<field name="auto_search" eval="False" />')

            if act_window.multi:
                l_model_view_file.append('<field name="multi" eval="True" />')

            if act_window.help:
                l_model_view_file.append('<field name="name" type="html">%s</field>' % act_window.help)

            if act_window.groups_id:
                l_model_view_file.append(self._get_m2m_groups(act_window.groups_id))

            l_model_view_file.append('</record>\n')

        #
        # Server Actions
        #
        for server_action in model.o2m_server_action:

            l_model_view_file.append('<record model="ir.actions.server" id="%s">' % self._get_action_data_name(
                server_action, server=True, creating=True
            ))

            l_model_view_file.append('<field name="name">%s</field>' % server_action.name)

            l_model_view_file.append(
                '<field name="model_id" ref="%s" />' % self._get_model_data_name(server_action.model_id)
            )

            l_model_view_file.append(
                '<field name="binding_model_id" ref="%s" />' % self._get_model_data_name(model))

            if server_action.state == 'code':

                l_model_view_file.append('<field name="state">code</field>')

                l_model_view_file.append('<field name="code">\n%s</field>' % server_action.code)

            else:
                l_model_view_file.append('<field name="state">multi</field>')

                if server_action.child_ids:
                    l_model_view_file.append(
                        '<field name="child_ids" eval="[(6,0, [%s])]" />' % ', '.join(
                            server_action.child_ids.mapped(lambda child: 'ref(%s)' % self._get_action_data_name(
                                child, server=True
                            ))
                        )
                    )

            l_model_view_file.append('</record>\n')

        l_model_view_file += XML_ODOO_CLOSING_TAG

        wizards_path = self.code_generator_data.wizards_path
        views_path = self.code_generator_data.views_path
        xml_file_path = os.path.join(wizards_path if model.transient else views_path, f'{model_model}.xml')
        self.code_generator_data.write_file_lst_content(xml_file_path, l_model_view_file, data_file=True)

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

            l_model_report_file.append('<template id="%s">' % report.report_name)

            l_model_report_file.append('<field name="arch" type="xml">%s</field>' % report.m2o_template.arch_db)

            l_model_report_file.append('</template>\n')

            l_model_report_file.append(
                '<record model="ir.actions.report" id="%s_actionreport">' % report.report_name)

            l_model_report_file.append('<field name="model">%s</field>' % report.model)

            l_model_report_file.append('<field name="name">%s</field>' % report.report_name)

            l_model_report_file.append('<field name="file">%s</field>' % report.report_name)

            l_model_report_file.append('<field name="string">%s</field>' % report.name)

            l_model_report_file.append('<field name="report_type">%s</field>' % report.report_type)

            if report.print_report_name:
                l_model_report_file.append('<field name="print_report_name">%s</field>' % report.print_report_name)

            if report.multi:
                l_model_report_file.append('<field name="multi">%s</field>' % report.multi)

            if report.attachment_use:
                l_model_report_file.append('<field name="attachment_use">%s</field>' % report.attachment_use)

            if report.attachment:
                l_model_report_file.append('<field name="attachment">%s</field>' % report.attachment)

            if report.binding_model_id:
                l_model_report_file.append(
                    '<field name="binding_model_id" ref="%s" />' % self._get_model_data_name(
                        report.binding_model_id)
                )

            if report.groups_id:
                l_model_report_file.append(self._get_m2m_groups(report.groups_id))

            l_model_report_file.append('</record>')

            l_model_report_file += XML_ODOO_CLOSING_TAG

        xmlreport_file_path = os.path.join(self.code_generator_data.reports_path, f'{model_model}.xml')
        self.code_generator_data.write_file_lst_content(xmlreport_file_path, l_model_report_file, data_file=True)

    def _set_model_py_file(self, model, model_model):
        """
        Function to set the model files
        :param model:
        :param model_model:
        :return:
        """

        cw = CodeWriter()
        for line in MODEL_HEAD:
            str_line = line.strip()
            cw.emit(str_line)

        if model.m2o_inherit_py_class.name and model.m2o_inherit_py_class.module:
            cw.emit(f'from {model.m2o_inherit_py_class.module} import {model.m2o_inherit_py_class.name}')

        cw.emit()
        cw.emit(f"class {self._get_class_name(model.model)}({self._get_python_class_4inherit(model)}):")

        with cw.indent():
            if model.m2o_inherit_model.model:
                cw.emit(f"_inherit = '{model.m2o_inherit_model.model}'")

            cw.emit(f"_name = '{model.model}'")
            cw.emit(f"_description = '{model.name}'")

            self._get_model_fields(cw, model)

            self._get_model_constrains(cw, model)

        if model.transient:
            pypath = self.code_generator_data.wizards_path
        elif model.o2m_reports and self.env[model.model]._abstract:
            pypath = self.code_generator_data.reports_path
        else:
            pypath = self.code_generator_data.models_path

        model_file_path = os.path.join(pypath, f'{model_model}.py')

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
        l_model_csv_access.insert(0, 'id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink')

        if module.o2m_groups or l_model_rules:
            l_module_security = ['<data>\n']

            for group in module.o2m_groups:

                l_module_security += ['<record model="res.groups" id="%s">' % self._get_group_data_name(group)]
                l_module_security += ['<field name="name">%s</field>' % group.name]

                if group.comment:
                    l_module_security += ['<field name="comment">%s</field>' % group.comment]

                if group.implied_ids:
                    l_module_security += [
                        '<field name="implied_ids" eval="[%s]"/>' % ', '.join(
                            group.implied_ids.mapped(lambda g: '(4, ref(\'%s\'))' % self._get_group_data_name(g))
                        )
                    ]

                l_module_security += ['</record>\n']

            l_module_security += l_model_rules

            l_module_security += ['</data>']

            module_name = module.name.lower().strip()
            security_file_path = os.path.join(self.code_generator_data.security_path, f'{module_name}.xml')
            self.code_generator_data.write_file_lst_content(security_file_path,
                                                            XML_HEAD + l_module_security + XML_ODOO_CLOSING_TAG,
                                                            data_file=True, insert_first=True)

        if len(l_model_csv_access) > 1:
            model_access_file_path = os.path.join(self.code_generator_data.security_path, 'ir.model.access.csv')
            self.code_generator_data.write_file_lst_content(model_access_file_path, l_model_csv_access, data_file=True,
                                                            insert_first=True)

    def _get_model_access(self, model):
        """
        Function to obtain the model access
        :param model:
        :return:
        """

        l_model_csv_access = []

        for access in model.access_ids:
            access_name = access.name

            access_model_data = self.env['ir.model.data'].search(
                [
                    ('module', '=', MODULE_NAME),
                    ('model', '=', 'ir.model.access'),
                    ('res_id', '=', access.id)
                ]
            )

            access_id = access_model_data[0].name if access_model_data else self._lower_replace(access_name)

            access_model = self._get_model_model(access.model_id.model)

            access_group = self._get_group_data_name(access.group_id) if access.group_id else ''

            access_read, access_create, access_write, access_unlink = \
                1 if access.perm_read else 0, \
                1 if access.perm_create else 0, \
                1 if access.perm_write else 0, \
                1 if access.perm_unlink else 0

            l_model_csv_access.append(
                '%s,%s,model_%s,%s,%s,%s,%s,%s' % (
                    access_id,
                    access_name,
                    access_model,
                    access_group,
                    access_read,
                    access_create,
                    access_write,
                    access_unlink
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
                l_model_rules.append('<record model="ir.rule" id="%s">' % self._lower_replace(rule.name))
                l_model_rules.append('<field name="name">%s</field>' % rule.name)

            else:
                l_model_rules.append('<record model="ir.rule" id="%s_rrule_%s">' % (
                    self._get_model_data_name(rule.model_id), rule.id
                ))

            l_model_rules.append('<field name="model_id" ref="%s"/>' % self._get_model_data_name(rule.model_id))

            if rule.domain_force:
                l_model_rules.append('<field name="domain_force">%s</field>' % rule.domain_force)

            if not rule.active:
                l_model_rules.append('<field name="active" eval="False" />')

            if rule.groups:
                l_model_rules.append(self._get_m2m_groups(rule.groups))

            if not rule.perm_read:
                l_model_rules.append('<field name="perm_read" eval="False" />')

            if not rule.perm_create:
                l_model_rules.append('<field name="perm_create" eval="False" />')

            if not rule.perm_write:
                l_model_rules.append('<field name="perm_write" eval="False" />')

            if not rule.perm_unlink:
                l_model_rules.append('<field name="perm_unlink" eval="False" />')

            l_model_rules.append('</record>\n')

        return l_model_rules

    def _get_m2m_groups(self, m2m_groups):
        """

        :param m2m_groups:
        :return:
        """

        return '<field name="groups_id" eval="[(6,0, [%s])]" />' % ', '.join(
            m2m_groups.mapped(lambda g: 'ref(%s)' % self._get_group_data_name(g))
        )

    def _get_model_fields(self, cw, model):
        """
        Function to obtain the model fields
        :param model:
        :return:
        """

        f2exports = model.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS)

        if model.m2o_inherit_model:
            father = self.env['ir.model'].browse(model.m2o_inherit_model.id)
            fatherfieldnames = father.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS).mapped('name')
            f2exports = f2exports.filtered(lambda field: field.name not in fatherfieldnames)

        for f2export in f2exports:
            cw.emit()
            dct_field_attribute = {
                "string": f2export.field_description,
            }

            if f2export.help:
                dct_field_attribute["help"] = f2export.help

            if f2export.ttype in ['many2one', 'one2many', 'many2many']:
                if f2export.relation:
                    dct_field_attribute["comodel_name"] = f2export.relation

                if f2export.ttype == 'one2many' and f2export.relation_field:
                    dct_field_attribute["inverse_name"] = f2export.relation_field

                if f2export.ttype == 'many2one' and f2export.on_delete and f2export.on_delete != "set null":
                    dct_field_attribute["ondelete"] = f2export.on_delete

                if f2export.domain and f2export.domain != '[]':
                    dct_field_attribute["domain"] = f2export.domain

                if f2export.ttype == 'many2many':
                    # A relation who begin with x_ is an automated relation, ignore it
                    ignored_relation = False if not f2export.relation_table else f2export.relation_table.startswith(
                        "x_")
                    if not ignored_relation:
                        if f2export.relation_table:
                            dct_field_attribute["relation"] = f2export.relation_table
                        if f2export.column1:
                            dct_field_attribute["column1"] = f2export.column1
                        if f2export.column2:
                            dct_field_attribute["column2"] = f2export.column2

            if (f2export.ttype == 'char' or f2export.ttype == 'reference') and f2export.size != 0:
                dct_field_attribute["size"] = f2export.size

            if (f2export.ttype == 'reference' or f2export.ttype == 'selection') and f2export.selection:
                # Transform selection
                # '[("point", "Point"), ("line", "Line"), ("area", "Polygon")]'
                # [('"point"', '_( "Point")'), ('"line"', '_( "Line")'), ('"area"', '_( "Polygon")')]
                if f2export.selection != '[]':
                    lst_selection = [a.split(",") for a in f2export.selection.strip('[]').strip('()').split('), (')]
                    lst_selection = [f"({a[0]}, _({a[1].strip()}))" for a in lst_selection]
                    dct_field_attribute["selection"] = lst_selection
                else:
                    dct_field_attribute["selection"] = []

            if f2export.default:
                if f2export.default == "True":
                    dct_field_attribute["default"] = True
                elif f2export.default == "False":
                    # Ignore False value
                    pass
                else:
                    dct_field_attribute["default"] = f2export.default

            if f2export.related:
                dct_field_attribute["related"] = f2export.related

            if f2export.required:
                dct_field_attribute["required"] = True

            if f2export.readonly:
                dct_field_attribute["readonly"] = True

            if f2export.index:
                dct_field_attribute["index"] = True

            if f2export.translate:
                dct_field_attribute["translate"] = True

            if not f2export.selectable:
                dct_field_attribute["selectable"] = False

            if f2export.groups:
                dct_field_attribute["groups"] = f2export.groups.mapped(lambda g: self._get_group_data_name(g))

            compute = f2export.compute and f2export.depends
            if compute:
                dct_field_attribute["compute"] = f'_compute_{f2export.name}'

            if (f2export.ttype == 'one2many' or f2export.related or compute) and f2export.copied:
                dct_field_attribute["copy"] = True

            # Ignore it, by default it's copy=False
            # elif f2export.ttype != 'one2many' and not f2export.related and not compute and not f2export.copied:
            #     dct_field_attribute["copy"] = False

            lst_field_attribute = []
            for key, value in dct_field_attribute.items():
                if type(value) is str:
                    # TODO find another solution than removing \n, this cause error with cw.CodeWriter
                    value = value.replace('\n', ' ')
                    lst_field_attribute.append(f"{key}='{value}'")
                elif type(value) is list:
                    # TODO find another solution than removing \n, this cause error with cw.CodeWriter
                    new_value = ', '.join(value)
                    new_value = new_value.replace('\n', ' ')
                    lst_field_attribute.append(f"{key}=[{new_value}]")
                else:
                    lst_field_attribute.append(f"{key}={value}")

            cw.emit_list(lst_field_attribute, ('(', ')'),
                         before=f'{f2export.name} = {self._get_odoo_ttype_class(f2export.ttype)}')

            if compute:
                cw.emit()
                l_depends = self._get_l_map(lambda e: e.strip(), f2export.depends.split(','))

                cw.emit(f"@api.depends({self._prepare_compute_constrained_fields(l_depends)})")
                cw.emit(f"def _compute_{f2export.name}(self):")

                l_compute = f2export.compute.split('\n')
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

        for model in module.o2m_models:

            model_model = self._get_model_model(model.model)

            if not module.nomenclator_only:
                # Wizard
                self._set_model_py_file(model, model_model)
                self._set_model_xmlview_file(model, model_model)

                # Report
                self._set_model_xmlreport_file(model, model_model)

            parameters = self.env['ir.config_parameter'].sudo()
            s_data2export = parameters.get_param('code_generator.s_data2export', default='nomenclator')
            if s_data2export != 'nomenclator' or (s_data2export == 'nomenclator' and model.nomenclator):
                self._set_model_xmldata_file(model, model_model)

            if not module.nomenclator_only:
                l_model_csv_access += self._get_model_access(model)

                l_model_rules += self._get_model_rules(model)

        if not module.nomenclator_only:
            application_icon = self._set_module_menus(module)

            self.set_xml_data_file(module)

            self.set_xml_views_file(module)

            self.set_module_python_file(module)

            self.set_module_css_file(module)

            self._set_module_security(module, l_model_rules, l_model_csv_access)

            self._set_static_description_file(module, application_icon)

        self.set_extra_get_lst_file_generate(module)

        self.code_generator_data.reorder_manifest_data_files()

        self._set_manifest_file(module)

        self.set_module_init_file_extra(module)

        self.code_generator_data.generate_python_init_file()

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
        modules = self.env['code.generator.module'].browse(vals.get("code_generator_ids"))

        # path = tempfile.gettempdir()
        path = tempfile.mkdtemp()
        morethanone = len(modules.ids) > 1
        if morethanone:
            # TODO validate it's working
            path += '/modules'
            CodeGeneratorData.os_make_dirs(path)

        os.chdir(path=path)

        basename = 'modules' if morethanone else modules[0].name.lower().strip()
        vals["basename"] = basename
        rootdir = path if morethanone else path + '/' + modules[0].name.lower().strip()
        vals["rootdir"] = rootdir

        for module in modules:
            # TODO refactor this to share variable in another class,
            #  like that, self.code_generator_data will be associate to a class of generation of module
            self.code_generator_data = CodeGeneratorData(module, path)
            self.get_lst_file_generate(module)

            if module.enable_sync_code:
                self.code_generator_data.sync_code(module.path_sync_code, module.name)

        vals["list_path_file"] = ";".join(self.code_generator_data.lst_path_file)

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
        self._models_path = "models"
        self._css_path = os.path.join("static", "src", "scss")
        self._security_path = "security"
        self._views_path = "views"
        self._wizards_path = "wizards"
        self._controllers_path = "controllers"
        self._reports_path = "reports"
        self._static_description_path = os.path.join('static', 'description')
        self._lst_manifest_data_files = []
        self._dct_import_dir = defaultdict(list)
        self._dct_extra_module_init_path = defaultdict(list)
        self._dct_view_id = {}

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

    def add_view_id(self, name, id):
        self._dct_view_id[name] = id

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
                print(f"ERROR cannot find key {meta}.")
        return list(set_files)

    def reorder_manifest_data_files(self):
        lst_manifest = []
        dct_depend = self.dct_data_depend
        dct_hold_file = {}
        for manifest_data in self._lst_manifest_data_files:
            if manifest_data in dct_depend.keys():
                # find depend and report until order is right
                lst_meta = dct_depend.get(manifest_data)
                lst_files_depends = self._get_lst_files_data_depends(lst_meta)
                dct_hold_file[manifest_data] = lst_files_depends
            else:
                lst_manifest.append(manifest_data)

            # Check holding file and add it if resolve
            lst_delete_dct_hold_file = []
            for file_name, lst_files_depends in dct_hold_file.items():
                # Make a copy before delete item for correct iteration
                for files_depends in lst_files_depends[:]:
                    # check if file exist in queue list or dependencies is internal
                    if files_depends in lst_manifest or files_depends == manifest_data:
                        lst_files_depends.remove(files_depends)
                if not lst_files_depends:
                    lst_manifest.append(file_name)
                    lst_delete_dct_hold_file.append(file_name)

            for delete_file in lst_delete_dct_hold_file:
                del dct_hold_file[delete_file]

        if dct_hold_file:
            print(f"ERROR, cannot order manifest files dependencies : {dct_hold_file}")
        self._lst_manifest_data_files = lst_manifest

    def copy_directory(self, source_directory_path, directory_path):
        """
        Copy only directory without manipulation
        :param source_directory_path:
        :param directory_path:
        :return:
        """
        absolute_path = os.path.join(self._path, self._module_name, directory_path)
        # self._check_mkdir_and_create(absolute_path, is_file=False)
        status = shutil.copytree(source_directory_path, absolute_path)

    def copy_file(self, source_file_path, file_path, search_and_replace=[]):
        with open(source_file_path, "rb") as file_source:
            content = file_source.read()

        if search_and_replace:
            # switch binary to string
            content = content.decode('utf-8')
            for search, replace in search_and_replace:
                content = content.replace(search, replace)
            self.write_file_str(file_path, content)
        else:
            self.write_file_binary(file_path, content)

    def write_file_lst_content(self, file_path, lst_content, data_file=False, insert_first=False):
        """
        Function to create a file with some content
        :param file_path:
        :param lst_content:
        :param data_file:
        :param insert_first:
        :return:
        """

        try:
            self.write_file_binary(file_path, '\n'.join(lst_content).encode("utf-8"), data_file=data_file,
                                   insert_first=insert_first)
        except Exception as e:
            print(e)
            raise e

    def write_file_str(self, file_path, content, mode='w', data_file=False, insert_first=False):
        """
        Function to create a file with some binary content
        :param file_path:
        :param content:
        :param mode:
        :param data_file:
        :param insert_first:
        :return:
        """
        self.write_file_binary(file_path, content, mode=mode, data_file=data_file, insert_first=insert_first)

    def write_file_binary(self, file_path, content, mode='wb', data_file=False, insert_first=False):
        """
        Function to create a file with some binary content
        :param file_path:
        :param content:
        :param mode:
        :param data_file:
        :param insert_first:
        :return:
        """

        # file_path suppose to be a relative path
        if file_path[0] == "/":
            print(f"WARNING, path {file_path} not suppose to start with '/'.")
            file_path = file_path[1:]

        absolute_path = os.path.join(self._path, self._module_name, file_path)
        self._lst_path_file.add(absolute_path)

        if data_file and file_path not in self._lst_manifest_data_files:
            if insert_first:
                self._lst_manifest_data_files.insert(0, file_path)
            else:
                self._lst_manifest_data_files.append(file_path)

        self._check_import_python_file(file_path)

        self._check_mkdir_and_create(absolute_path)

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
            if len(self._split_path_all(dir_name)) > 1:
                # This is a odoo limitation, but we can support it if need it
                print("WARNING, you add python file more depth of 1 directory.")
                return
            python_module_name = os.path.splitext(os.path.basename(file_path))[0]
            self._dct_import_dir[dir_name].append(python_module_name)

    def _check_mkdir_and_create(self, file_path, is_file=True):
        if is_file:
            path_dir = os.path.dirname(file_path)
        else:
            path_dir = file_path
        self.os_make_dirs(path_dir)

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
            print(e)

    def generate_python_init_file(self):
        for component, lst_module in self._dct_import_dir.items():
            init_path = os.path.join(component, '__init__.py')
            if not component:
                lst_module = [a for a in self._dct_import_dir.keys() if a]

            lst_module.sort()

            cw = CodeWriter()
            if component:
                for module in lst_module:
                    cw.emit(f"from . import {module}")
            elif lst_module:
                cw.emit(f"from . import {', '.join(lst_module)}")
            for extra_import in self._dct_extra_module_init_path.get(component, []):
                cw.emit(extra_import)
            self.write_file_str(init_path, cw.render())
