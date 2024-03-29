from odoo import api, fields, models, modules, tools


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    m2o_res_model = fields.Many2one(
        comodel_name="ir.model",
        string="Res Model",
        store=True,
        help="Res Model",
        ondelete="cascade",
    )

    m2o_src_model = fields.Many2one(
        comodel_name="ir.model",
        string="Src Model",
        store=True,
        help="Src Model",
        ondelete="cascade",
    )

    @api.onchange("m2o_res_model")
    def _onchange_m2o_res_model(self):
        if self.m2o_res_model:
            return dict(value=dict(res_model=self.m2o_res_model.model))

    @api.onchange("m2o_src_model")
    def _onchange_m2o_src_model(self):
        if self.m2o_src_model:
            return dict(value=dict(src_model=self.m2o_src_model.model))
