from odoo import models, fields, api, modules, tools


class CodeGenerator(models.Model):
    _inherit = "code.generator.module"

    enable_generate_website_leaflet = fields.Boolean(
        string="Enable website leaflet feature",
        default=False,
        help="This variable need to be True to generate website leaflet if enable_generate_all is False",
    )
