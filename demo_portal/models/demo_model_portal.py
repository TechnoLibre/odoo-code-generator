from odoo import _, api, models, fields


class DemoModelPortal(models.Model):
    _inherit = 'portal.mixin'
    _name = 'demo.model.portal'
    _description = 'demo_model_portal'

    banana = fields.Boolean(string='Banana demo')

    name = fields.Char(string='Name')
