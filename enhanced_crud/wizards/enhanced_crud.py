# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

ALL = _('ECrudAll')
SYSTEM = _('System Window Actions (from base., res., ir., web., etc.)')
NOSYSTEM = _('Excluding System Window Actions (not from base., res., ir., web., etc.)')
ACTIONSBELONGING = _('Window Actions belonging to %s')
CURRENTTARGETDOMAIN = [('target', '=', 'current'), ('view_mode', 'not in', ['form', 'tree', 'tree,kanban'])]


def current_target_lambda(ir_act_window):
    """

    :param ir_act_window:
    :return:
    """

    return ir_act_window.target == 'current' and ir_act_window.view_mode not in ['form', 'tree', 'tree,kanban']


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    @api.model
    def ecrud_get_data(self, app, model='ir.actions.act_window'):
        """
        Function to obtain the ir.model.data from a specific app and model
        :param app:
        :param model:
        :return:
        """

        return self.search([('module', '=', app), ('model', '=', model)])


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    @staticmethod
    def _ecrud_check_name(system_option=True):
        """
        Function to check the window action name
        :param system_option:
        :return:
        """

        l_pattern = ['base_', 'bus_', 'ir_', 'change_', 'iap_', 'res_', 'web_', 'wizard_', 'rel_', 'report_', 'rule_']

        def _checker(act_window):
            """

            :param act_window:
            :return:
            """

            is_from_system = False
            for pattern in l_pattern:
                if act_window.res_model.replace('.', '_').startswith(pattern):
                    is_from_system = True
                    break

            return system_option and is_from_system if (system_option or is_from_system) else True

        return _checker

    @api.model
    def ecrud_almost_everyone(self, do_a_filter=False, system_option=True):
        """
        Function to get window actions
        :param do_a_filter:
        :param system_option:
        :return:
        """

        window_actions = self.search(CURRENTTARGETDOMAIN)
        return window_actions.filtered(self._ecrud_check_name(system_option)) if do_a_filter else window_actions

    @api.model
    def ecrud_get_from_app_data(self, app, do_a_filter=False, system_option=True):
        """
        Function to get window actions
        :param app:
        :param do_a_filter:
        :param system_option:
        :return:
        """

        window_actions = \
            self.browse(self.env['ir.model.data'].ecrud_get_data(app).mapped('res_id')).filtered(current_target_lambda)
        return window_actions.filtered(self._ecrud_check_name(system_option)) if do_a_filter else window_actions


class EnhancedCrudActWindowGroups(models.Model):
    _name = 'enhanced.crud.act_window.groups'
    _description = 'Table for the Window Action Groups'
    _rec_name = 'description'

    name = fields.Char(
        string='Window Action group',
        help='Window Action group',
        required=True
    )

    description = fields.Char(
        string='Window Action group description',
        help='Window Action group description',
        required=True,
        translate=True
    )

    @api.model
    def create_act_window_groups(self):
        self.create([
            dict(name='all', description=ALL),
            dict(name='system', description=SYSTEM),
            dict(name='nosystem', description=NOSYSTEM)
        ])

        apps = self.env['ir.module.module'].search([('state', '=', 'installed'), ('application', '=', True)])
        for app in apps:
            self.create([dict(name=app.name, description='Window Actions belonging to %s' % app.shortdesc)])


class EnhancedCrudActWindowLink(models.TransientModel):
    _name = 'enhanced.crud.act_window.link'
    _description = 'Wizard to associate the window actions belonging to the selected apps with the Enhanced CRUD module'

    m2o_act_window_group = fields.Many2one(
        comodel_name='enhanced.crud.act_window.groups',
        string='Window Action group',
        help='Window Action group',
        required=True,
        ondelete='cascade'
    )

    @api.multi
    def link_window_actions(self):
        opcion = self.m2o_act_window_group.name
        ir_act_window = self.env['ir.actions.act_window']

        if opcion not in ('all', 'system', 'nosystem'):
            window_actions = ir_act_window.ecrud_get_from_app_data(opcion, do_a_filter=True, system_option=False)

        else:
            window_actions = \
                ir_act_window.ecrud_almost_everyone(do_a_filter=opcion != 'all', system_option=opcion == 'system')

        if not window_actions:
            raise ValidationError('There are no window actions that satisfy the established criteria.')

        enhanced_crud_act_window = self.env['enhanced.crud.act_window']
        for waction in window_actions:
            enhanced_crud_act_window.create([dict(m2o_act_window=waction.id)])

        return dict(
            type='ir.actions.client',
            tag='reload',
            params=dict(
                menu_id=self.env.ref('enhanced_crud.enhanced_crud_act_window_associated_menu').id
            )
        )
