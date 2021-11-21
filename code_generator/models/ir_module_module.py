from odoo import models, fields, api, modules, tools


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    header_manifest = fields.Text(
        string="Header", help="Header comment in __manifest__.py file."
    )
