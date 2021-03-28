from odoo import models, fields, api, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = "code.generator.module"

    enable_cron_template = fields.Boolean(
        string="Cron template", help="Add cron template to code generator."
    )

    o2m_model_cron = fields.One2many(
        comodel_name="ir.cron",
        inverse_name="m2o_module",
        string="Cron",
        help="Relative ir.cron"
        # compute='_get_models_info'
    )

    # def _get_models_info(self):
    #     super(CodeGeneratorModule, self)._get_models_info()
    #     for module in self:
    #         module.o2m_model_cron = module.o2m_models.mapped('access_ids')
