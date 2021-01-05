# -*- coding: utf-8 -*-

import importlib
import logging
import re

from odoo import models, fields, api, _, tools
from odoo.addons.base.models.ir_model import SAFE_EVAL_BASE
from odoo.exceptions import ValidationError, UserError, MissingError
from odoo.tools.safe_eval import safe_eval
from psycopg2._psycopg import ProgrammingError
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

MAGIC_FIELDS = MAGIC_COLUMNS + ['display_name', '__last_update', 'access_url', 'access_token', 'access_warning']
CONSCREATEUNABLE = _('Unable to create the constraint.')
CONSDELETECREATEUNABLE = _(
    'Since you modify the sql constraint definition we must delete it and create a new one, and we were unable to do it.')
CONSMODIFYUNABLE = _('Unable to modify the constraint.')
CONSDELETEUNABLE = _('Unable to delete the constraint.')
SYNTAXERRORMSG = _('There is a syntax error in your %scode definition.')
SERVERCONSTRAIN = _('%s Server constrain ')
PREDEFINEDVARS = _(
    'You specified a non predefined variable. The predefined variables are self, datetime, dateutil, time, re, ValidationError and the ones accessible through self, like self.env.')
CONSTRAINEDLS = _(
    'The field Constrained lists the fields that the server constrain will check. It is a comma-separated list of field names, like name, size.')

SAFE_EVAL_BASE['re'] = re
SAFE_EVAL_BASE['ValidationError'] = ValidationError

SAFE_EVAL_4FUNCTION = SAFE_EVAL_BASE
SAFE_EVAL_4FUNCTION['api'] = api
SAFE_EVAL_4FUNCTION['models'] = models
SAFE_EVAL_4FUNCTION['fields'] = fields
SAFE_EVAL_4FUNCTION['_'] = _


def common_4constrains(el_self, code, message=SYNTAXERRORMSG):
    """

    :param el_self:
    :param code:
    :param message:
    :return:
    """

    try:
        safe_eval(code, SAFE_EVAL_4FUNCTION, {'self': el_self}, mode='exec')

    except ValueError:
        raise ValidationError(PREDEFINEDVARS)

    except SyntaxError:
        raise ValidationError(message)


def add_constraint(cr, tablename, constraintname, definition):
    """ Add a constraint on the given table. """
    query1 = 'ALTER TABLE "{}" ADD CONSTRAINT "{}" {}'.format(tablename, constraintname, definition)
    query2 = 'COMMENT ON CONSTRAINT "{}" ON "{}" IS %s'.format(constraintname, tablename)
    try:
        with cr.savepoint():
            cr.execute(query1)
            cr.execute(query2, (definition,))
            _logger.debug("Table %r: added constraint %r as %s", tablename, constraintname, definition)
            return True
    except Exception:
        msg = "Table %r: unable to add constraint %r!\n" \
              "If you want to have it, you should update the records and execute manually:\n%s"
        _logger.warning(msg, tablename, constraintname, query1, exc_info=True)
        return False


def drop_constraint(cr, tablename, constraintname):
    """ drop the given constraint. """
    try:
        with cr.savepoint():
            cr.execute('ALTER TABLE "{}" DROP CONSTRAINT "{}"'.format(tablename, constraintname))
            _logger.debug("Table %r: dropped constraint %r", tablename, constraintname)
            return True
    except ProgrammingError as proerror:
        return proerror.pgerror.count('does not exist') or False

    except Exception:
        _logger.warning("Table %r: unable to drop constraint %r!", tablename, constraintname)
        return False


def sql_constraint(el_self, constraints):
    cr = el_self._cr
    foreign_key_re = re.compile(r'\s*foreign\s+key\b.*', re.I)

    def process(key, definition):
        conname = '%s_%s' % (el_self._table, key)
        current_definition = tools.constraint_definition(cr, el_self._table, conname)
        if not current_definition:
            # constraint does not exists
            return add_constraint(cr, el_self._table, conname, definition)
        elif current_definition != definition:
            # constraint exists but its definition may have changed
            drop_constraint(cr, el_self._table, conname)
            return add_constraint(cr, el_self._table, conname, definition)

        else:
            return True

    result = False
    for (sql_key, sql_definition, _) in constraints:
        if foreign_key_re.match(sql_definition):
            el_self.pool.post_init(process, sql_key, sql_definition)
        else:
            result = process(sql_key, sql_definition)

        if not result:
            break

    return result


class IrModelServerConstrain(models.Model):
    _name = 'ir.model.server_constrain'
    _description = 'Code Generator Model Server Constrains'
    _rec_name = 'constrained'

    constrained = fields.Char(
        string='Constrained',
        help='Constrained fields, ej: name, age',
        required=True
    )

    @api.onchange('constrained')
    @api.constrains('constrained')
    def _check_constrained(self):
        if self.constrained:
            splitted = self.constrained.split(',')
            if list(filter(lambda e: e.strip() not in self.env[self.m2o_ir_model.model]._fields.keys(), splitted)):
                raise ValidationError(CONSTRAINEDLS)

    txt_code = fields.Text(
        string='Code',
        help='Code to execute',
        required=True
    )

    @api.onchange('txt_code')
    @api.constrains('txt_code')
    def _check_txt_code(self):
        if self.txt_code:
            constrain_detail = SERVERCONSTRAIN % self.constrained
            common_4constrains(self.env[self.m2o_ir_model.model], self.txt_code, SYNTAXERRORMSG % constrain_detail)

    m2o_ir_model = fields.Many2one(
        comodel_name='ir.model',
        string='Code generator Model',
        help='Model that will hold this server constrain',
        required=True,
        domain=[('transient', '=', False)],
        ondelete='cascade'
    )


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    m2o_model = fields.Many2one(
        comodel_name='ir.model',
        string='Code generator Model',
        help='Model related with this report',
        compute='_compute_m2os'
    )

    m2o_template = fields.Many2one(
        comodel_name='ir.ui.view',
        string='Template',
        help='Template related with this report',
        compute='_compute_m2os'
    )

    @api.depends('model', 'report_name')
    def _compute_m2os(self):
        for report in self:
            searched = self.env['ir.model'].search([('model', '=', report.model.strip())])
            if searched:
                report.m2o_model = searched[0].id

            stripped = report.report_name.strip()
            splitted = stripped.split('.')
            searched = self.env['ir.ui.view'].search(
                [('type', '=', 'qweb'), ('name', '=', splitted[len(splitted) - 1])])
            if searched:
                report.m2o_template = searched[0].id


class IrModel(models.Model):
    _inherit = 'ir.model'

    @api.constrains('model')
    def _check_model_name(self):
        for model in self:
            if model.state == 'manual':
                if not model.m2o_module and not model.model.startswith('x_'):
                    raise ValidationError(_("The model name must start with 'x_'."))
            if not models.check_object_name(model.model):
                raise ValidationError(
                    _("The model name can only contain lowercase characters, digits, underscores and dots.")
                )

    rec_name = fields.Char(
        default='name'
    )

    m2o_module = fields.Many2one(
        'code.generator.module',
        string='Module',
        help="Module",
        ondelete='cascade'
    )

    @api.onchange('m2o_module')
    def _onchange_m2o_module(self):
        if self.m2o_module:

            name4filter = 'x_name'
            name4newfield = 'name'

        else:

            name4filter = 'xname'
            name4newfield = 'x_name'

        remain = self.field_id.filtered(lambda field: field.name != name4filter)

        return dict(
            value=dict(
                field_id=[
                    (6, False, remain.ids),
                    (0, False, dict(name=name4newfield, field_description='Name', ttype='char'))
                ]
            )
        )

    o2m_constraints = fields.One2many(
        'ir.model.constraint',
        'model',
        domain=[('type', '=', 'u'), ('message', '!=', None)]
    )

    m2o_inherit_py_class = fields.Many2one(
        'code.generator.pyclass',
        string='Python Class',
        help="Python Class",
        ondelete='cascade'
    )

    m2o_inherit_model = fields.Many2one(
        'ir.model',
        string='Inherit Model',
        help="Inherit Model",
        ondelete='cascade'
    )

    o2m_act_window = fields.One2many(
        'ir.actions.act_window',
        'm2o_res_model'
    )

    o2m_server_action = fields.One2many(
        'ir.actions.server',
        'binding_model_id',
        domain=[
            ('binding_type', '=', 'action'),
            '|', ('state', '=', 'code'), ('state', '=', 'multi'),
            ('usage', '=', 'ir_actions_server')
        ]
    )

    nomenclator = fields.Boolean(
        string='Nomenclator?',
        help='Set this if you want this model as a nomenclator'
    )

    @api.model
    def _instanciate(self, model_data):
        custommodelclass = super(IrModel, self)._instanciate(model_data)

        try:
            if 'rec_name' in model_data and model_data['rec_name']:
                # TODO this was commented because it caused stack overflow when running with pydev
                # model_fields = self.field_id.search([('model_id', '=', model_data['id'])]). \
                #     filtered(lambda f: f.name not in MAGIC_FIELDS)
                #
                # if model_fields and not model_fields.filtered(lambda f: f.name == model_data['rec_name']):
                #     raise ValidationError(_('The Record Label value must exist within the model fields name.'))

                custommodelclass._rec_name = model_data['rec_name']

            if 'm2o_inherit_model' in model_data and model_data['m2o_inherit_model']:
                custommodelclass._inherit = self.browse(model_data['m2o_inherit_model']).model

            if 'm2o_inherit_py_class' in model_data and model_data['m2o_inherit_py_class']:

                try:
                    py_class = self.env['code.generator.pyclass'].browse(model_data['m2o_inherit_py_class'])
                    m2o_inherit_py_class_module = importlib.import_module(py_class.module)
                    m2o_inherit_py_class = getattr(m2o_inherit_py_class_module, py_class.name)

                    class CustomModelInheritedPyClass(custommodelclass, m2o_inherit_py_class):
                        pass

                    return CustomModelInheritedPyClass

                except AttributeError:
                    pass

        except RecursionError:
            pass

        return custommodelclass

    o2m_server_constrains = fields.One2many(
        comodel_name='ir.model.server_constrain',
        inverse_name='m2o_ir_model',
        string='Server Constrains',
        help='Server Constrains attach to this model'
    )

    o2m_reports = fields.One2many(
        comodel_name='ir.actions.report',
        inverse_name='m2o_model',
        string='Reports',
        help='Reports associated with this model'
    )


class CodeGeneratorBase(models.AbstractModel):
    _inherit = 'base'

    def _run_safe_eval(self, created=None):
        """

        :param created:
        :return:
        """

        records = created or self
        for r in records:
            target_model = self.env['ir.model'].search([('model', '=', r._name)])
            if target_model and hasattr(self.env, target_model[0]._name) and hasattr(target_model[0],
                                                                                     'o2m_server_constrains'):
                codes = target_model.mapped('o2m_server_constrains').mapped('txt_code')
                for code in codes:
                    safe_eval(code, SAFE_EVAL_BASE, {'self': r}, mode="exec")

    @api.model_create_multi
    def create(self, vals_list):
        result = super(CodeGeneratorBase, self).create(vals_list)

        self._run_safe_eval(result)

        return result

    @api.multi
    def write(self, vals):
        result = super(CodeGeneratorBase, self).write(vals)

        self._run_safe_eval()

        return result


class IrModelUpdatedFields(models.Model):
    _name = 'code.generator.ir.model.fields'
    _description = 'Code Generator Fields'

    m2o_module = fields.Many2one(
        'code.generator.module',
        string='Module',
        help="Module",
        ondelete='cascade'
    )

    m2o_fields = fields.Many2one(
        'ir.model.fields',
        string="Fields"
    )

    nomenclature_blacklist = fields.Boolean(string="Ignore from nomenclature.", default=False)

    nomenclature_whitelist = fields.Boolean(string="Force to nomenclature.", default=False)

    name = fields.Char(string="Name", help="Name of selected field.", compute="_change_m2o_fields")

    @api.onchange('m2o_fields')
    def _change_m2o_fields(self):
        for ir_field in self:
            if ir_field.m2o_fields:
                ir_field.name = ir_field.m2o_fields.name
            else:
                self.name = False


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.constrains('name', 'state')
    def _check_name(self):
        for field in self:
            if field.state == 'manual':
                if not field.model_id.m2o_module and not field.name.startswith('x_'):
                    raise ValidationError(_("Custom fields must have a name that starts with 'x_' !"))
            try:
                models.check_pg_name(field.name)
            except ValidationError:
                msg = _("Field names can only contain characters, digits and underscores (up to 63).")
                raise ValidationError(msg)

    @api.model
    def create(self, vals):
        if 'model_id' in vals:
            model_data = self.env['ir.model'].browse(vals['model_id'])
            vals['model'] = model_data.model
        if vals.get('ttype') == 'selection':
            if not vals.get('selection'):
                raise UserError(_('For selection fields, the Selection Options must be given!'))
            self._check_selection(vals['selection'])

        res = super(models.Model, self).create(vals)

        if vals.get('state', 'manual') == 'manual':

            check_relation = True
            if vals.get('relation') and vals.get('model_id'):
                check_relation = not model_data.m2o_module

            if vals.get('relation') and not self.env['ir.model'].search([('model', '=', vals['relation'])]) and \
                    check_relation:
                raise UserError(_("Model %s does not exist!") % vals['relation'])

            if vals.get('ttype') == 'one2many':
                if not self.search([('model_id', '=', vals['relation']), ('name', '=', vals['relation_field']),
                                    ('ttype', '=', 'many2one')]):
                    raise UserError(
                        _("Many2one %s on model %s does not exist!") % (vals['relation_field'], vals['relation']))

            self.clear_caches()  # for _existing_field_data()

            if vals['model'] in self.pool:
                # setup models; this re-initializes model in registry
                self.pool.setup_models(self._cr)
                # update database schema of model and its descendant models
                descendants = self.pool.descendants([vals['model']], '_inherits')
                self.pool.init_models(self._cr, descendants, dict(self._context, update_custom_fields=True))

        return res


class IrModelConstraint(models.Model):
    _inherit = 'ir.model.constraint'

    module = fields.Many2one(
        default=lambda self: self.env['ir.module.module'].search([('name', '=', 'base')])[0].id
    )

    model_state = fields.Selection(
        related='model.state'
    )

    message = fields.Char(
        string='Message',
        help='Message'
    )

    @api.model_create_multi
    def create(self, vals_list):
        imcs = super(IrModelConstraint, self).create(vals_list)

        for imc in imcs:
            m_target = self.env[imc.model.model]
            t_constrain = (imc.name, imc.definition, imc.message)
            if not sql_constraint(m_target, m_target._sql_constraints + [t_constrain]):
                raise ValidationError(CONSCREATEUNABLE)

        return imcs

    @api.multi
    def write(self, vals):

        if 'definition' in vals:
            for imc in self:
                tablename = self.env[imc.model.model]._table
                if not drop_constraint(self._cr, tablename, '%s_%s' % (tablename, imc.name)):
                    raise ValidationError(CONSDELETECREATEUNABLE)

        result = super(IrModelConstraint, self).write(vals)

        for imc in self:
            m_target = self.env[imc.model.model]
            t_constrain = (imc.name, imc.definition, imc.message)
            if not sql_constraint(m_target, [t_constrain]):
                raise ValidationError(CONSMODIFYUNABLE)

        return result

    @api.multi
    def unlink(self):

        for imc in self:
            try:
                tablename = self.env[imc.model.model]._table
                if not drop_constraint(self._cr, tablename, '%s_%s' % (tablename, imc.name)):
                    raise ValidationError(CONSDELETEUNABLE)

            except MissingError:
                _logger.warning('The registry entry associated with %s no longer exists' % imc.model.model)

        return super(IrModelConstraint, self).unlink()
