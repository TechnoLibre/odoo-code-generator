from odoo import _, api, models, fields


class DemoModel2Portal(models.Model):
    _inherit = 'portal.mixin'
    _name = 'demo.model_2.portal'
    _description = 'demo_model_2_portal'

    model_1 = fields.Many2one(
        string='Model 1',
        comodel_name='demo.model.portal',
        on_delete='set null',
    )

    name = fields.Char(string='Name')
