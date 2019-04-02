# -*- coding: utf-8 -*-

import io
import os
import shutil
import tempfile
import uuid
from zipfile import ZipFile, ZIP_DEFLATED

import jinja2
from odoo import http
from odoo.http import request, content_disposition
from odoo.models import MAGIC_COLUMNS

UNDEFINEDMESSAGE = 'Restriction message not yet define.'
MAGIC_FIELDS = MAGIC_COLUMNS + ['display_name', '__last_update']
MODULE_NAME = 'code_generator'
ENCODING = ['# -*- coding: utf-8 -*-']
BLANCK_LINE = ['']
BREAK_LINE = ['\n']
BLANCK_HEAD = ENCODING + BLANCK_LINE
BREAK_HEAD = ENCODING + BREAK_LINE
XML_VERSION = ['<?xml version= "1.0" encoding="utf-8"?>']
XML_ODOO_OPENING_TAG = ['<odoo>']
XML_HEAD = XML_VERSION + XML_ODOO_OPENING_TAG
XML_ODOO_CLOSING_TAG = ['</odoo>']
FROM_ODOO_IMPORTS = ['from odoo import api, models, fields']
MODEL_HEAD = BLANCK_HEAD + FROM_ODOO_IMPORTS + BREAK_LINE
TAB4 = ' ' * 4
TAB8 = ' ' * 8


class CodeGeneratorZipFile(ZipFile):
    """
    Code Generator ZipFile class
    """

    def write_end_record_without_closing(self):
        """
        Util function to write the 'end records' of a  Zip file without call the close method
        :return:
        """

        with self._lock:
            if self._seekable:
                self.fp.seek(self.start_dir)
            self._write_end_record()


def _osmakedirs(path, exist_ok=True):
    """
    Util function to wrap the makedirs method
    :param path:
    :param exist_ok:
    :return:
    """
    os.makedirs(path, exist_ok=exist_ok)


def _get_l_map(fn, collection):
    """
    Util function to get a list of a map operation
    :param fn:
    :param collection:
    :return:
    """

    return list(map(fn, collection))


def _get_class_name(model):
    """
    Util function to get a model class name representation from a model name (code.generator -> CodeGenerator)
    :param model:
    :return:
    """

    result = []
    bypoint = model.split('.')
    for byp in bypoint:
        result += byp.split('_')
    return ''.join(_get_l_map(lambda e: e.capitalize(), result))


def _lower_replace(string, replacee=' ', replacer='_'):
    """
    Util function to replace and get the lower content of a string
    :param string:
    :return:
    """

    return str(string).lower().replace(replacee, replacer)


def _get_model_model(model_model, replacee='.'):
    """
    Util function to get a model res_id-like representation (code.generator -> code_generator)
    :param model_model:
    :param replacee:
    :return:
    """
    return _lower_replace(model_model, replacee=replacee)


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


def _get_odoo_ttype_class(ttype):
    """
    Util function to get a field class name from a field type (char -> Char, many2one -> Many2one)
    :param ttype:
    :return:
    """

    return 'fields.%s' % ttype.capitalize()


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


def _set_limit_4xmlid(xmlid):
    """
    Util function to truncate (to 64 characters) an xml_id
    :param xmlid:
    :return:
    """

    return '%s...' % xmlid[:61 - len(xmlid)] if (64 - len(xmlid)) < 0 else xmlid


def _get_ir_model_data(record, give_a_default=False):
    """
    Function to obtain the model data from a record
    :param record:
    :param give_a_default:
    :return:
    """

    ir_model_data = request.env['ir.model.data'].search([
        # TODO: Opción por valorar
        # ('module', '!=', '__export__'),
        ('model', '=', record._name),
        ('res_id', '=', record.id)
    ])
    return '%s.%s' % (ir_model_data[0].module, ir_model_data[0].name) if ir_model_data else \
        (_set_limit_4xmlid('%s_%s' % (
            _get_model_model(record._name), _lower_replace(getattr(record, record._rec_name) if record._rec_name else '')
        ))) if give_a_default else False


def _get_group_data_name(group):
    """
    Function to obtain the res_id-like group name (Code Generator / Manager -> code_generator_manager)
    :param group:
    :return:
    """

    return _get_ir_model_data(group) if _get_ir_model_data(group) else _lower_replace(group.name.replace(' /', ''))


def _get_model_data_name(model):
    """
    Function to obtain the res_id-like model name (code.generator.module -> code_generator_module)
    :param model:
    :return:
    """

    return _get_ir_model_data(model) if _get_ir_model_data(model) else 'model_%s' % _get_model_model(model.model)


def _get_view_data_name(view):
    """
    Function to obtain the res_id-like view name
    :param view:
    :return:
    """

    return _get_ir_model_data(view) if _get_ir_model_data(view) else \
        '%s_%sview>' % (_get_model_model(view.model), view.type)


def _get_action_data_name(action, server=False, creating=False):
    """
    Function to obtain the res_id-like action name
    :param action:
    :param server:
    :param creating:
    :return:
    """

    if not creating and _get_ir_model_data(action):
        return _get_ir_model_data(action)

    else:
        model = getattr(action, 'res_model') if not server else getattr(action, 'model_id').model
        model_model = _get_model_model(model)
        actiontype = 'actionwindow' if not server else 'serveraction'

        actionname = _set_limit_4xmlid('%s' % action.name[:64 - len(model_model) - len(actiontype)])

        return '%s_%s_%s' % (model_model, _lower_replace(actionname), actiontype)


def _get_menu_data_name(menu):
    """
    Function to obtain the res_id-like menu name
    :param menu:
    :return:
    """

    return _get_ir_model_data(menu) if _get_ir_model_data(menu) else _lower_replace(menu.name)


jinjaenv = jinja2.Environment()


def _jinjateate(file_path, content, mode='wb'):
    """
    Function to create a file with some content
    :param file_path:
    :param content:
    :param mode:
    :return:
    """

    with open(file_path, mode) as file:
        jinjaenv.from_string('\n'.join(content)).stream({}).dump(file, encoding='utf-8')


def _get_model_fields(model):
    """
    Function to obtain the model fields
    :param model:
    :return:
    """

    l_model_fields = []
    f2exports = model.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS)

    if model.m2o_inherit_model:
        father = request.env['ir.model'].browse(model.m2o_inherit_model.id)
        fatherfieldnames = father.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS).mapped('name')
        f2exports = f2exports.filtered(lambda field: field.name not in fatherfieldnames)

    for f2export in f2exports:

        l_model_fields += BLANCK_LINE

        l_model_fields.append('%s%s = %s(' % (TAB4, f2export.name, _get_odoo_ttype_class(f2export.ttype)))

        l_model_fields.append('%sstring=\'%s\',' % (TAB8, f2export.field_description))

        if f2export.help:
            l_model_fields.append('%shelp=\'%s\',' % (TAB8, f2export.help))

        if f2export.ttype in ['many2one', 'one2many', 'many2many']:
            if f2export.relation:
                l_model_fields.append('%scomodel_name=\'%s\',' % (TAB8, f2export.relation))

            if f2export.ttype == 'one2many' and f2export.relation_field:
                l_model_fields.append('%sinverse_name=\'%s\',' % (TAB8, f2export.relation_field))

            if f2export.ttype == 'many2one' and f2export.on_delete:
                l_model_fields.append('%son_delete=\'%s\',' % (TAB8, f2export.on_delete))

            if f2export.domain and f2export.domain != '[]':
                l_model_fields.append('%sdomain="%s",' % (TAB8, f2export.domain))

            if f2export.ttype == 'many2many':
                if f2export.relation_table:
                    l_model_fields.append('%srelation=\'%s\',' % (TAB8, f2export.relation_table))
                if f2export.column1:
                    l_model_fields.append('%scolumn1=\'%s\',' % (TAB8, f2export.column1))
                if f2export.column2:
                    l_model_fields.append('%scolumn2=\'%s\',' % (TAB8, f2export.column2))

        if (f2export.ttype == 'char' or f2export.ttype == 'reference') and f2export.size != 0:
            l_model_fields.append('%ssize=%s,' % (TAB8, f2export.size))

        if (f2export.ttype == 'reference' or f2export.ttype == 'selection') and f2export.selection:
            l_model_fields.append('%sselection=%s,' % (TAB8, f2export.selection))

        if f2export.related:
            l_model_fields.append('%srelated=\'%s\',' % (TAB8, f2export.related))

        if f2export.required:
            l_model_fields.append('%srequired=True,' % TAB8)

        if f2export.readonly:
            l_model_fields.append('%sreadonly=True,' % TAB8)

        if f2export.index:
            l_model_fields.append('%sindex=True,' % TAB8)

        if f2export.translate:
            l_model_fields.append('%stranslate=True,' % TAB8)

        if not f2export.selectable:
            l_model_fields.append('%sselectable=False,' % TAB8)

        if f2export.groups:
            l_model_fields.append('%sgroups=\'%s\',' % (
                TAB8, ','.join(f2export.groups.mapped(lambda g: _get_group_data_name(g)))
            ))

        compute = f2export.compute and f2export.depends
        if compute:
            l_model_fields.append('%scompute=\'_compute_%s\',' % (TAB8, f2export.name))

        if (f2export.ttype == 'one2many' or f2export.related or compute) and f2export.copied:
            l_model_fields.append('%scopy=True,' % TAB8)

        elif f2export.ttype != 'one2many' and not f2export.related and not compute and not f2export.copied:
            l_model_fields.append('%scopy=False,' % TAB8)

        l_model_fields.append('%s)' % TAB4)

        if compute:
            l_model_fields += BLANCK_LINE

            l_depends = _get_l_map(lambda e: e.strip(), f2export.depends.split(','))
            depends_counter = 1
            depends = ''
            for depend in l_depends:
                depends += '\'%s\'%s' % (depend, ', ' if depends_counter < len(l_depends) else '')
                depends_counter += 1

            l_model_fields.append('%s@api.depends(%s)' % (TAB4, depends))
            l_model_fields.append('%sdef _compute_%s(self):' % (TAB4, f2export.name))

            l_compute = f2export.compute.split('\n')
            starting_spaces = 2
            for line in l_compute:
                if _get_starting_spaces(line) == 2:
                    starting_spaces += 1
                l_model_fields.append('%s%s' % (TAB4 * starting_spaces, line.strip()))

    return l_model_fields


def _get_model_constraints(model):
    """
    Function to obtain the model constraints
    :param model:
    :return:
    """

    if model.o2m_constraints:

        l_model_sql_constraints = ['%s_sql_constraints = [' % TAB4]

        constraint_counter = 0
        for constraint in model.o2m_constraints:
            constraint_name = constraint.name.replace('%s_' % _get_model_model(model.model), '')
            constraint_definition = constraint.definition
            constraint_message = constraint.message if constraint.message else UNDEFINEDMESSAGE
            constraint_counter += 1
            constraint_separator = ',' if constraint_counter < len(model.o2m_constraints) else ''

            l_model_sql_constraints.append(
                '%s(\'%s\', \'%s\', \'%s\')%s' % (
                    TAB8, constraint_name, constraint_definition, constraint_message, constraint_separator
                )
            )

        l_model_sql_constraints.append('%s]' % TAB4)

        return BLANCK_LINE + l_model_sql_constraints + BREAK_LINE

    else:
        return BREAK_LINE


def _get_model_access(model):
    """
    Function to obtain the model access
    :param model:
    :return:
    """

    l_model_csv_access = []

    for access in model.access_ids:
        access_name = access.name

        access_model_data = request.env['ir.model.data'].search(
            [
                ('module', '=', MODULE_NAME),
                ('model', '=', 'ir.model.access'),
                ('res_id', '=', access.id)
            ]
        )

        access_id = access_model_data[0].name if access_model_data else _lower_replace(access_name)

        access_model = _get_model_model(access.model_id.model)

        access_group = _get_group_data_name(access.group_id) if access.group_id else ''

        access_read, access_create, access_write, access_unlink = \
            1 if access.perm_read else 0, \
            1 if access.perm_create else 0, \
            1 if access.perm_write else 0, \
            1 if access.perm_unlink else 0, \

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


def _get_model_rules(model):
    """
    Function to obtain the model rules
    :param model:
    :return:
    """

    l_model_rules = []

    for rule in model.rule_ids:

        if rule.name:
            l_model_rules.append('<record model="ir.rule" id="%s">' % _lower_replace(rule.name))
            l_model_rules.append('<field name="name">%s</field>' % rule.name)

        else:
            l_model_rules.append('<record model="ir.rule" id="%s_rrule_%s">' % (
                _get_model_data_name(rule.model_id), rule.id
            ))

        l_model_rules.append('<field name="model_id" ref="%s"/>' % _get_model_data_name(rule.model_id))

        if rule.domain_force:
            l_model_rules.append('<field name="domain_force">%s</field>' % rule.domain_force)

        if not rule.active:
            l_model_rules.append('<field name="active" eval="False" />')

        if rule.groups:
            l_model_rules.append('<field name="groups" eval="[%s]"/>' % ', '.join(
                rule.groups.mapped(lambda g: '(4, ref(\'%s\'))' % _get_group_data_name(g))
            ))

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


def _set_module_folders(path, module_name):
    """
    Function to set the module folders
    :param path:
    :param module_name:
    :return:
    """

    #
    #
    #
    module_path = '%s/%s' % (path, module_name)
    _osmakedirs(module_path)

    #
    #
    #
    data_path = '%s/%s' % (module_path, 'data')
    _osmakedirs(data_path)

    #
    #
    #
    models_path = '%s/%s' % (module_path, 'models')
    _osmakedirs(models_path)

    #
    #
    #
    security_path = '%s/%s' % (module_path, 'security')
    _osmakedirs(security_path)

    #
    #
    #
    views_path = '%s/%s' % (module_path, 'views')
    _osmakedirs(views_path)

    #
    #
    #
    wizards_path = '%s/%s' % (module_path, 'wizards')
    _osmakedirs(wizards_path)

    return module_path, data_path, models_path, security_path, views_path, wizards_path


def _set_module_security(security_path, module, l_model_rules, l_model_csv_access):
    """
    Function to set the module security file
    :param security_path:
    :param module:
    :param l_model_rules:
    :param l_model_csv_access:
    :return:
    """

    l_security_files = []
    security_file_path = None
    if module.o2m_groups or l_model_rules:
        l_module_security = ['<data>\n']

        for group in module.o2m_groups:

            l_module_security += ['<record model="res.groups" id="%s">' % _get_group_data_name(group)]
            l_module_security += ['<field name="name">%s</field>' % group.name]

            if group.comment:
                l_module_security += ['<field name="comment">%s</field>' % group.comment]

            if group.implied_ids:
                l_module_security += [
                    '<field name="implied_ids" eval="[%s]"/>' % ', '.join(
                        group.implied_ids.mapped(lambda g: '(4, ref(\'%s\'))' % _get_group_data_name(g))
                    )
                ]

            l_module_security += ['</record>\n']

        l_module_security += l_model_rules

        l_module_security += ['</data>']

        security_file_path = '%s/%s.xml' % (security_path, module.name)
        _jinjateate(security_file_path, XML_HEAD + l_module_security + XML_ODOO_CLOSING_TAG)

        l_security_files.append('security/%s.xml' % module.name)

    model_access_file_path = '%s/ir.model.access.csv' % security_path
    _jinjateate(model_access_file_path, l_model_csv_access)

    l_security_files.append('security/ir.model.access.csv')

    return security_file_path, model_access_file_path, l_security_files


def _set_model_py_file(model, model_model, wizards_path, models_path):
    """
    Function to set the model files
    :param model:
    :param model_model:
    :param wizards_path:
    :param models_path:
    :return:
    """

    l_model = MODEL_HEAD

    l_model = l_model[:4:]

    if model.m2o_inherit_py_class.name and model.m2o_inherit_py_class.module:
        l_model += \
            ['from %s import %s' % (model.m2o_inherit_py_class.module, model.m2o_inherit_py_class.name)] + BREAK_LINE

    l_model += ['class %s(%s):' % (_get_class_name(model.model), _get_python_class_4inherit(model))]

    if model.m2o_inherit_model.model:
        l_model += ['%s_inherit = \'%s\'' % (TAB4, model.m2o_inherit_model.model)]

    l_model += ['%s_name = \'%s\'' % (TAB4, model.model)]
    l_model += ['%s_description = \'%s\'' % (TAB4, model.name)]

    l_model += _get_model_fields(model)

    l_model += _get_model_constraints(model)

    model_file_path = '%s/%s.py' % (wizards_path if model.transient else models_path, model_model)

    _jinjateate(model_file_path, l_model)

    return model_file_path


def _set_model_xmlview_file(model, model_model, wizards_path, views_path):
    """
    Function to set the model xml files
    :param model:
    :param model_model:
    :param wizards_path:
    :param views_path:
    :return:
    """

    if model.view_ids or model.o2m_act_window or model.o2m_server_action:

        l_model_view_file = XML_HEAD + BLANCK_LINE

        #
        # Views
        #
        for view in model.view_ids:

            view_type = view.type

            l_model_view_file.append('<record model="ir.ui.view" id="%s_%sview">' % (model_model, view_type))

            if view.name:
                l_model_view_file.append('<field name="name">%s</field>' % view.name)

            l_model_view_file.append('<field name="model">%s</field>' % view.model)

            if view.key:
                l_model_view_file.append('<field name="key">%s</field>' % view.key)

            if view.priority != 16:
                l_model_view_file.append('<field name="priority">%s</field>' % view.priority)

            if view.inherit_id:
                l_model_view_file.append('<field name="inherit_id" ref="%s"/>' % _get_view_data_name(view))

                if view.mode == 'primary':
                    l_model_view_file.append('<field name="mode">primary</field>')

            if not view.active:
                l_model_view_file.append('<field name="active" eval="False" />')

            if view.arch_db:
                l_model_view_file.append('<field name="arch" type="xml">%s</field>' % view.arch_db)

            l_model_view_file.append('</record>\n')

        #
        # Action Windows
        #
        for act_window in model.o2m_act_window:

            l_model_view_file.append(
                '<record model="ir.actions.act_window" id="%s">' % _get_action_data_name(act_window, creating=True)
            )

            if act_window.name:
                l_model_view_file.append('<field name="name">%s</field>' % act_window.name)

            if act_window.res_model or act_window.m2o_res_model:
                l_model_view_file.append(
                    '<field name="res_model">%s</field>' % act_window.res_model or act_window.m2o_res_model.model
                )

            if act_window.binding_model_id:
                l_model_view_file.append(
                    '<field name="binding_model_id" ref="%s" />' % _get_model_data_name(act_window.binding_model_id)
                )

            if act_window.view_id:
                l_model_view_file.append('<field name="view_id" ref="%s" />' % _get_view_data_name(act_window.view_id))

            if act_window.domain != '[]':
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
                    '<field name="search_view_id" ref="%s" />' % _get_view_data_name(act_window.search_view_id)
                )

            if act_window.filter:
                l_model_view_file.append('<field name="filter" eval="True" />')

            if not act_window.auto_search:
                l_model_view_file.append('<field name="auto_search" eval="False" />')

            if act_window.multi:
                l_model_view_file.append('<field name="multi" eval="True" />')

            if act_window.help:
                l_model_view_file.append('<field name="name" type="html">%s</field>' % act_window.help)

            l_model_view_file.append('</record>\n')

        #
        # Server Actions
        #
        for server_action in model.o2m_server_action:

            l_model_view_file.append('<record model="ir.actions.server" id="%s">' % _get_action_data_name(
                server_action, server=True, creating=True
            ))

            l_model_view_file.append('<field name="name">%s</field>' % server_action.name)

            l_model_view_file.append(
                '<field name="model_id" ref="%s" />' % _get_model_data_name(server_action.model_id)
            )

            l_model_view_file.append('<field name="binding_model_id" ref="%s" />' % _get_model_data_name(model))

            if server_action.code == 'code':

                l_model_view_file.append('<field name="state">code</field>')

                l_model_view_file.append('<field name="code">\n%s</field>' % server_action.code)

            else:
                l_model_view_file.append('<field name="state">multi</field>')

                if server_action.child_ids:
                    l_model_view_file.append(
                        '<field name="child_ids" eval="[(6,0, [%s])]" />' % ', '.join(
                            server_action.child_ids.mapped(lambda child: 'ref(%s)' % _get_action_data_name(
                                child, server=True
                            ))
                        )
                    )

            l_model_view_file.append('</record>\n')

        l_model_view_file += XML_ODOO_CLOSING_TAG

        xml_file_path = '%s/%s.xml' % (wizards_path if model.transient else views_path, model_model)
        _jinjateate(xml_file_path, l_model_view_file)

        return xml_file_path, ['views/%s.xml' % model_model]

    else:
        return None, []


def _get_from_rec_name(record, model):
    """
    Util function to handle the _rec_name / rec_name access
    :param record:
    :param model:
    :return:
    """

    return getattr(record, model._rec_name) if getattr(record, model._rec_name) else getattr(record, model.rec_name)


def _set_model_xmldata_file(model, model_model, data_path):
    """
    Function to set the module data file
    :param model:
    :param model_model:
    :param data_path:
    :return:
    """

    nomenclador_data = request.env[model.model].sudo().search([])
    if nomenclador_data:

        l_model_data_file = XML_HEAD + BLANCK_LINE

        for record in nomenclador_data:

            l_model_data_file.append('<record model="%s" id="%s">' % (
                model.model, _set_limit_4xmlid('%s_%s' % (
                    model_model,
                    _lower_replace(_get_from_rec_name(record, model)) if _get_from_rec_name(record, model)
                    else uuid.uuid1().int
                ))
            ))

            f2exports = model.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS)
            for rfield in f2exports:

                record_value = getattr(record, rfield.name)
                if record_value:

                    if rfield.ttype == 'many2one':
                        l_model_data_file.append(
                            '<field name="%s" ref="%s" />' % (
                                rfield.name, _get_ir_model_data(record_value, give_a_default=True)
                            )
                        )

                    elif rfield.ttype == 'one2many':
                        l_model_data_file.append(
                            '<field name="%s" eval="[%s]"/>' % (rfield.name, ', '.join(
                                record_value.mapped(lambda rvalue: '(4, ref(\'%s\'))' % _get_ir_model_data(
                                    rvalue, give_a_default=True
                                ))
                            ))
                        )

                    elif rfield.ttype == 'many2many':
                        l_model_data_file.append(
                            '<field name="%s" eval="[(6,0, [%s])]" />' % (rfield.name, ', '.join(
                                record_value.mapped(lambda rvalue: 'ref(%s)' % _get_ir_model_data(
                                    rvalue, give_a_default=True
                                ))
                            ))
                        )

                    else:
                        l_model_data_file.append('<field name="%s">%s</field>' % (rfield.name, record_value))

            l_model_data_file.append('</record>\n')

        l_model_data_file += XML_ODOO_CLOSING_TAG

        data_file_path = '%s/%s.xml' % (data_path, model_model)
        _jinjateate(data_file_path, l_model_data_file)

        return data_file_path, ['data/%s.xml' % model_model]

    else:
        return None, []


def _set_module_menues(module, views_path):
    """
    Function to set the module menues file
    :param module:
    :param views_path:
    :return:
    """

    menues = module.with_context({'ir.ui.menu.full_list': True}).o2m_menus
    if menues:

        l_module_menues_file = XML_HEAD + BLANCK_LINE

        for menu in menues:

            l_module_menues_file.append('<record model="ir.ui.menu" id="%s">' % _get_menu_data_name(menu))

            l_module_menues_file.append('<field name="name">%s</field>' % menu.name)

            if menu.action:
                l_module_menues_file.append('<field name="action" ref="%s" />' % _get_action_data_name(menu.action))

            if not menu.active:
                l_module_menues_file.append('<field name="active" eval="False" />')

            if menu.sequence != 10:
                l_module_menues_file.append('<field name="sequence">%s</field>' % menu.sequence)

            if menu.parent_id:
                l_module_menues_file.append('<field name="parent_id" ref="%s" />' % _get_menu_data_name(menu.parent_id))

            if menu.groups_id:
                l_module_menues_file.append(
                    '<field name="groups_id" eval="[(6,0, [%s])]" />' % ', '.join(
                        menu.groups_id.mapped(lambda g: 'ref(%s)' % _get_group_data_name(g))
                    )
                )

            l_module_menues_file.append('</record>\n')

        l_module_menues_file += XML_ODOO_CLOSING_TAG

        menu_file_path = '%s/menues.xml' % views_path
        _jinjateate(menu_file_path, l_module_menues_file)

        return menu_file_path, ['views/menues.xml']

    else:
        return None, []


def _set_manifest_file(module, module_path, l_manifest_data_files):
    """
    Function to set the module manifest file
    :param module:
    :param module_path:
    :param l_manifest_data_files:
    :return:
    """

    l_manifest_file = ['{', '%s\'name\': \'%s\',' % (TAB4, module.shortdesc)]

    if module.category_id:
        l_manifest_file.append('%s\'category\': \'%s\',' % (TAB4, module.category_id.name))

    if module.summary and module.summary != 'false':
        l_manifest_file.append('%s\'summary\': \'%s\',' % (TAB4, module.summary))

    if module.description:
        l_manifest_file.append('%s\'description\': \'%s\',' % (TAB4, module.description))

    if module.author:
        l_manifest_file.append('%s\'author\': \'%s\',' % (TAB4, module.author))

    if module.website:
        l_manifest_file.append('%s\'website\': \'%s\',' % (TAB4, module.website))

    if module.auto_install:
        l_manifest_file.append('%s\'auto_install\': \'%s\',' % (TAB4, True))

    if module.demo:
        l_manifest_file.append('%s\'demo\': \'%s\',' % (TAB4, True))

    if module.license != 'LGPL-3':
        l_manifest_file.append('%s\'license\': \'%s\',' % (TAB4, module.license))

    if module.application:
        l_manifest_file.append('%s\'application\': \'%s\',' % (TAB4, True))

    if module.dependencies_id:
        l_manifest_file.append('%s\'depends\': [\n%s\n],' % (
            TAB4, ', \n'.join(module.dependencies_id.mapped(lambda did: '\'%s\'' % did.depend_id.name))
        ))

    l_manifest_file.append('%s\'data\': [\n%s\n%s],' % (
        TAB4, ', \n'.join(_get_l_map(lambda dfile: '%s\'%s\'' % (TAB8, dfile), l_manifest_data_files)), TAB4
    ))

    l_manifest_file.append('%s\'installable\': %s,' % (TAB4, True))

    l_manifest_file.append('}')

    manifest_file_path = '%s/__manifest__.py' % module_path
    _jinjateate(manifest_file_path, BLANCK_HEAD + l_manifest_file + BREAK_LINE)

    return manifest_file_path


class CodeGeneratorController(http.Controller):

    @http.route('/code_generator/<string:module_ids>', auth='user', type='http')
    def code_generator(self, module_ids, **kwargs):
        """
        Function to export into code
        :param module_ids:
        :param kwargs:
        :return:
        """

        modules = request.env['code.generator.module'].browse(_get_l_map(lambda pk: int(pk), module_ids.split(',')))

        bytesio = io.BytesIO()
        zipy = CodeGeneratorZipFile(bytesio, mode='w', compression=ZIP_DEFLATED)

        path = tempfile.gettempdir()
        morethanone = len(modules.ids) > 1
        if morethanone:
            path += '/modules'
            _osmakedirs(path)

        os.chdir(path=path)

        parameters = request.env['ir.config_parameter'].sudo()

        for module in modules:

            module_path, data_path, models_path, security_path, views_path, wizards_path = \
                _set_module_folders(path, module.name)

            models_init_imports = []
            wizards_init_imports = []

            l_model_csv_access = ['id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink']
            l_model_rules = []

            l_manifest_data_files = []

            for model in module.o2m_models:

                model_model = _get_model_model(model.model)

                zipy.write(_set_model_py_file(model, model_model, wizards_path, models_path))

                xml_file_path, l_manifest_data_file = \
                    _set_model_xmlview_file(model, model_model, wizards_path, views_path)

                l_manifest_data_files += l_manifest_data_file
                if xml_file_path:
                    zipy.write(xml_file_path)

                s_data2export = parameters.get_param('code_generator.s_data2export', default='nomenclator')
                if s_data2export != 'nomenclator' or (s_data2export == 'nomenclator' and model.nomenclator):
                    data_file_path, l_manifest_data_file = _set_model_xmldata_file(model, model_model, data_path)

                    l_manifest_data_files += l_manifest_data_file
                    if data_file_path:
                        zipy.write(data_file_path)

                if model.transient:
                    wizards_init_imports.append('from . import %s' % model_model)

                else:
                    models_init_imports.append('from . import %s' % model_model)

                l_model_csv_access += _get_model_access(model)

                l_model_rules += _get_model_rules(model)

            menu_file_path, l_manifest_data_file = _set_module_menues(module, views_path)

            l_manifest_data_files += l_manifest_data_file
            if menu_file_path:
                zipy.write(menu_file_path)

            models_init_path = '%s/__init__.py' % models_path
            _jinjateate(models_init_path, BLANCK_HEAD + models_init_imports + BREAK_LINE)
            zipy.write(models_init_path)

            wizards_init_path = '%s/__init__.py' % wizards_path
            _jinjateate(wizards_init_path, BLANCK_HEAD + wizards_init_imports + BREAK_LINE)
            zipy.write(wizards_init_path)

            security_file_path, model_access_file_path, set_module_security_result = \
                _set_module_security(security_path, module, l_model_rules, l_model_csv_access)
            zipy.write(model_access_file_path)
            if security_file_path:
                zipy.write(security_file_path)

            security_file_insert_pos = 0
            for security_file in set_module_security_result:
                l_manifest_data_files.insert(security_file_insert_pos, security_file)
                security_file_insert_pos += 1

            zipy.write(_set_manifest_file(module, module_path, l_manifest_data_files))

            module_init_path = '%s/__init__.py' % module_path
            _jinjateate(module_init_path, BLANCK_HEAD + ['from . import models, wizards'] + BREAK_LINE)
            zipy.write(module_init_path)

        assert zipy.testzip() is None

        bytesio.seek(0)

        basename = 'modules' if morethanone else modules[0].name
        rootdir = path if morethanone else path + '/' + modules[0].name

        zipy.write_end_record_without_closing()

        response = request.make_response(
            zipy.fp.getvalue(),
            headers=[
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET'),
                ('Content-Disposition', content_disposition('%s.zip' % basename)),
                ('Content-Type', 'application/zip')
            ]
        )

        zipy.close()

        shutil.rmtree(rootdir, ignore_errors=True)

        return response
