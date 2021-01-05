from odoo import models, fields, api, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = 'code.generator.module'

    theme_website = fields.Boolean(string="Website theme", default=False,
                                   help="Create website theme module.")

    theme_website_primary_color = fields.Char(string="Primary Color", default="#38B44A",
                                              help="Choose your primary color")
    theme_website_secondary_color = fields.Char(string="Secondary Color", default="#AEA79F",
                                                help="Choose your secondary color")
    theme_website_extra_1_color = fields.Char(string="Extra 1 Color", default="#ffbd92",
                                              help="Choose your extra 1 color")
    theme_website_extra_2_color = fields.Char(string="Extra 2 Color", default="#ffbd92",
                                              help="Choose your extra 2 color")
    theme_website_extra_3_color = fields.Char(string="Extra 3 Color", default="#ffbd92",
                                              help="Choose your extra 3 color")

    theme_website_body_color = fields.Char(string="Body Color", default="#fff",
                                           help="Choose your body color")
    theme_website_menu_color = fields.Char(string="Menu Color", default="#fff",
                                           help="Choose your menu color")
    theme_website_footer_color = fields.Char(string="Footer Color", default="#fff",
                                             help="Choose your footer color")
    theme_website_text_color = fields.Char(string="Text Color", default="#000",
                                           help="Choose your text color")
