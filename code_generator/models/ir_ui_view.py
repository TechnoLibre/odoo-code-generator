from odoo import api, fields, models, modules, tools


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    # TODO this is wrong, use instead link to code_generator. Check _get_models_info from code_generator_module.py
    is_code_generator = fields.Boolean(
        compute="_compute_is_code_generator",
        store=True,
        help="Do a link with code generator to show associate ir.ui.view",
    )

    is_hide_blacklist_write_view = fields.Boolean(
        string="Hide in blacklist when writing code view",
        help="Hide from view when field is blacklisted.",
    )

    is_show_whitelist_write_view = fields.Boolean(
        string="Show in whitelist when writing code view",
        help="If a field in model is in whitelist, all is not will be hide. ",
    )

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Code generator Model",
        help="Model",
        ondelete="cascade",
    )

    @api.depends("m2o_model")
    def _compute_is_code_generator(self):
        for rec in self:
            # TODO this is wrong, because it will show if multiple code.generator.module
            cgs = self.env["code.generator.module"].search([])
            if cgs:
                for cg in cgs:
                    model_ids = cg.o2m_models
                    if rec.m2o_model.id in model_ids.ids:
                        rec.is_code_generator = True
