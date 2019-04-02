# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    m2o_res_model = fields.Many2one(
        'ir.model',
        string='Res Model',
        help='Res Model',
        ondelete='cascade'
    )

    @api.onchange('m2o_res_model')
    def _onchange_m2o_res_model(self):
        if self.m2o_res_model:
            return dict(
                value=dict(
                    res_model=self.m2o_res_model.model
                )
            )

    m2o_src_model = fields.Many2one(
        'ir.model',
        string='Src Model',
        help='Src Model',
        ondelete='cascade'
    )

    @api.onchange('m2o_src_model')
    def _onchange_m2o_src_model(self):
        if self.m2o_src_model:
            return dict(
                value=dict(
                    src_model=self.m2o_src_model.model
                )
            )


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    @api.onchange('model_id', 'state')
    def _onchange_model_id_state(self):
        if self.model_id.m2o_module and (self.state == 'code' or self.state == 'multi'):
            result = dict()

            if self.state == 'code':
                result.update(dict(
                    value=dict(
                        code='raise Warning(\'Not implemented yet\')'
                    )
                ))

            if not self.binding_model_id:
                result.update(dict(
                    warning=dict(
                        title='Contextual action',
                        message='Remember to create the contextual action...'
                    )
                ))

            return result

        elif self.model_id and self.state == 'code':
            return dict(
                value=dict(
                    code=self.DEFAULT_PYTHON_CODE
                )
            )
