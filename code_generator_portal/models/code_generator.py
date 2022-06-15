from odoo import api, fields, models, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = "code.generator.module"

    selected_model_portal_ids = fields.Many2many(comodel_name="ir.model")
