from odoo import models, fields, api, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = 'code.generator.module'

    o2m_geoengine_vector_layer = fields.One2many(
        comodel_name='geoengine.vector.layer',
        inverse_name='m2o_code_generator'
    )

    o2m_geoengine_raster_layer = fields.One2many(
        comodel_name='geoengine.raster.layer',
        inverse_name='m2o_code_generator'
    )

    enable_generate_geoengine = fields.Boolean(
        string="Enable geoengine feature",
        default=False,
        help="This variable need to be True to generate geoengine if enable_generate_all is False")

    @api.multi
    def unlink(self):
        # Need to unlink geo before view_ids, because they are linked together
        self.o2m_geoengine_vector_layer.unlink()
        self.o2m_geoengine_raster_layer.unlink()
        return super(CodeGeneratorModule, self).unlink()