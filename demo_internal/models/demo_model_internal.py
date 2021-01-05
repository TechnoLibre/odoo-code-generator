from odoo import _, api, models, fields


class DemoModelInternal(models.Model):
    _name = 'demo.model.internal'
    _description = 'demo_model_internal'

    banana = fields.Boolean(string='Banana demo')

    name = fields.Char(string='Name')
