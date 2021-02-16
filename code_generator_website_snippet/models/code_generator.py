from odoo import models, fields, api, modules, tools


class CodeGenerator(models.Model):
    _inherit = 'code.generator.module'

    enable_generate_website_snippet = fields.Boolean(
        string="Enable website snippet feature",
        default=False,
        help="This variable need to be True to generate website snippet if enable_generate_all is False")

    enable_generate_website_snippet_javascript = fields.Boolean(
        string="Enable website snippet Javascript",
        default=False,
        help="Add Javascript into snippet.")

    generate_website_snippet_list = fields.Char(
        string="Number of snippet to generate.",
        default="",
        help="Separate item by ';' to create a list.")

    generate_website_snippet_type = fields.Selection(
        selection=[
            ('structure', 'Structure'),
            ('content', 'Content'),
            ('feature', 'Feature'),
            ('effect', 'Effect'),
        ],
        string='Snippet type', default='structure')
