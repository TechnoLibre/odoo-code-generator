from odoo import _, api, models, fields


class DemoWebsiteLeafletMap(models.Model):
    _name = 'demo.website_leaflet.map'
    _description = 'Map'

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    category_id = fields.Many2one(
        string='Category',
        comodel_name='demo.website_leaflet.category',
        ondelete='restrict',
    )

    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
    )

    description = fields.Char(string='Description')

    feature_id = fields.Many2many(
        string='Features',
        comodel_name='demo.website_leaflet.map.feature',
    )

    name = fields.Char(
        string='Name',
        required=True,
    )
