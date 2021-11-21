from odoo import models, fields, api, modules, tools


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    m2o_res_model = fields.Many2one(
        "ir.model", string="Res Model", help="Res Model", ondelete="cascade"
    )

    @api.onchange("m2o_res_model")
    def _onchange_m2o_res_model(self):
        if self.m2o_res_model:
            return dict(value=dict(res_model=self.m2o_res_model.model))

    m2o_src_model = fields.Many2one(
        "ir.model", string="Src Model", help="Src Model", ondelete="cascade"
    )

    @api.onchange("m2o_src_model")
    def _onchange_m2o_src_model(self):
        if self.m2o_src_model:
            return dict(value=dict(src_model=self.m2o_src_model.model))
