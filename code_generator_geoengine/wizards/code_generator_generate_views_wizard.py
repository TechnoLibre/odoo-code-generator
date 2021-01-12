from odoo import _, models, fields, api


class CodeGeneratorGenerateViewsWizard(models.TransientModel):
    _inherit = "code.generator.generate.views.wizard"

    clear_all_geoengine = fields.Boolean(
        string="Clear geoengine",
        default=True,
        help="Clear all geoengine data before execute."
    )

    enable_generate_geoengine = fields.Boolean(
        string="Enable geoengine feature",
        default=False,
        help="This variable need to be True to generate geoengine if enable_generate_all is False")

    def clear_all(self):
        if self.clear_all_geoengine:
            if self.code_generator_id.sudo().o2m_geoengine_vector_layer:
                self.code_generator_id.sudo().o2m_geoengine_vector_layer.unlink()
            if self.code_generator_id.sudo().o2m_geoengine_raster_layer:
                self.code_generator_id.sudo().o2m_geoengine_raster_layer.unlink()
        # Need to clear geoengine vector and raster before clear views
        super(CodeGeneratorGenerateViewsWizard, self).clear_all()

    @api.multi
    def button_generate_views(self):
        status = super(CodeGeneratorGenerateViewsWizard, self).button_generate_views()
        if not status or (not self.enable_generate_all and not self.enable_generate_geoengine):
            self.code_generator_id.enable_generate_geoengine = False
            return status

        self.code_generator_id.enable_generate_geoengine = True
        return status
