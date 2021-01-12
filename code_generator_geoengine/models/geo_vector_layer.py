# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class GeoVectorLayer(models.Model):
    _inherit = 'geoengine.vector.layer'

    m2o_code_generator = fields.Many2one(
        'code.generator.module',
        string='Code Generator',
        help='Code Generator relation',
        ondelete='cascade'
    )
