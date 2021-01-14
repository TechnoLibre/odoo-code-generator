from odoo import _, api, models, fields


class DemoWebsiteLeafletCategory(models.Model):
    _name = 'demo.website_leaflet.category'
    _description = 'Map Feature Category'

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
    )

    description = fields.Char(string='Description')

    name = fields.Char(
        string='Name',
        required=True,
    )

    parent = fields.Many2one(
        string='Parent',
        comodel_name='demo.website_leaflet.category',
        ondelete='restrict',
    )
