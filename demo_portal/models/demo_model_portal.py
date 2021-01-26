from odoo import _, api, models, fields


class DemoModelPortal(models.Model):
    _inherit = 'portal.mixin'
    _name = 'demo.model.portal'
    _description = 'demo_model_portal'

    demo_binary = fields.Binary(string='Binary demo')

    demo_boolean = fields.Boolean(string='Boolean demo')

    demo_char = fields.Char(string='Char demo')

    demo_date = fields.Date(string='Date demo')

    demo_date_time = fields.Datetime(string='Datetime demo')

    demo_float = fields.Float(string='Float demo')

    demo_html = fields.Html(string='HTML demo')

    demo_integer = fields.Integer(string='Integer demo')

    demo_many2many = fields.Many2many(
        string='Many2many demo',
        comodel_name='demo.model_2.portal',
    )

    demo_one2many = fields.One2many(
        string='One2Many demo',
        comodel_name='demo.model_2.portal',
        inverse_name='demo_many2one',
    )

    demo_selection = fields.Selection(
        string='Selection demo',
        selection=[],
    )

    name = fields.Char(string='Name')
