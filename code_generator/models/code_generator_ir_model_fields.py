from odoo import models, fields, api, modules, tools


class IrModelUpdatedFields(models.Model):
    _name = "code.generator.ir.model.fields"
    _description = "Code Generator Fields"

    m2o_module = fields.Many2one(
        "code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    m2o_fields = fields.Many2one("ir.model.fields", string="Fields")

    nomenclature_blacklist = fields.Boolean(
        string="Ignore from nomenclature.", default=False
    )

    nomenclature_whitelist = fields.Boolean(
        string="Force to nomenclature.", default=False
    )

    name = fields.Char(
        string="Name",
        help="Name of selected field.",
        compute="_change_m2o_fields",
    )

    @api.onchange("m2o_fields")
    def _change_m2o_fields(self):
        for ir_field in self:
            if ir_field.m2o_fields:
                ir_field.name = ir_field.m2o_fields.name
            else:
                self.name = False
