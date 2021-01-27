from odoo import _, api, models, fields


class DemoModel2Internal(models.Model):
    _name = 'demo.model_2.internal'
    _description = 'demo_model_2_internal'

    model_1 = fields.Many2one(
        string='Model 1',
        comodel_name='demo.model.internal',
    )

    name = fields.Char(string='Name')
