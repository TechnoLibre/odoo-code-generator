from odoo import _, api, models, fields


class DemoModel2Portal(models.Model):
    _inherit = 'portal.mixin'
    _name = 'demo.model_2.portal'
    _description = 'demo_model_2_portal'

    demo_many2one = fields.Many2one(
        string='Many2one',
        comodel_name='demo.model.portal',
    )

    name = fields.Char(string='Name')
