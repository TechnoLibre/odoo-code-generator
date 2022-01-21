from odoo import _, api, fields, models


class CodeGeneratorGenerateViewsWizard(models.TransientModel):
    _inherit = "code.generator.generate.views.wizard"

    clear_all_geoengine = fields.Boolean(
        string="Clear geoengine",
        default=True,
        help="Clear all geoengine data before execute.",
    )

    enable_generate_geoengine = fields.Boolean(
        string="Enable geoengine feature",
        default=False,
        help=(
            "This variable need to be True to generate geoengine if"
            " enable_generate_all is False"
        ),
    )

    def _update_model_field_tree_view(self, model_created_fields_list):
        model_created_fields_list = super(
            CodeGeneratorGenerateViewsWizard, self
        )._update_model_field_tree_view(model_created_fields_list)
        if not self.enable_generate_all and not self.enable_generate_geoengine:
            return model_created_fields_list

        # TODO remove this patch when geo_* will be accepted in tree view
        # Remove ttype geo_ in tree view
        return model_created_fields_list.filtered(
            lambda x: not x.ttype.startswith("geo_")
        )

    def clear_all(self):
        if self.clear_all_geoengine:
            if self.code_generator_id.sudo().o2m_geoengine_vector_layer:
                self.code_generator_id.sudo().o2m_geoengine_vector_layer.unlink()
            if self.code_generator_id.sudo().o2m_geoengine_raster_layer:
                self.code_generator_id.sudo().o2m_geoengine_raster_layer.unlink()
        # Need to clear geoengine vector and raster before clear views
        super(CodeGeneratorGenerateViewsWizard, self).clear_all()

    def _add_dependencies(self):
        super(CodeGeneratorGenerateViewsWizard, self)._add_dependencies()
        if not self.enable_generate_all and not self.enable_generate_geoengine:
            return

        for code_generator in self.code_generator_id:
            code_generator.add_module_dependency(["base_geoengine", "website"])

    @api.multi
    def button_generate_views(self):
        status = super(
            CodeGeneratorGenerateViewsWizard, self
        ).button_generate_views()
        if not status or (
            not self.enable_generate_all and not self.enable_generate_geoengine
        ):
            self.code_generator_id.enable_generate_geoengine = False
            return status

        self.code_generator_id.enable_generate_geoengine = True
        return status
