# -*- coding: utf-8 -*-

import importlib

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

from code_generator.controllers.main import MAGIC_FIELDS


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

                model_fields = self.field_id.search([('model_id', '=', model_data['id'])]). \
                    filtered(lambda f: f.name not in MAGIC_FIELDS)

                if model_fields and not model_fields.filtered(lambda f: f.name == model_data['rec_name']):
                    raise ValidationError(_('The Record Label value must exist within the model fields name.'))

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
