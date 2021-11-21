from odoo import models, fields, api, modules, tools


class CodeGeneratorIrModelFields(models.Model):
    _name = "code.generator.ir.model.fields"
    _description = "Code Generator Fields"

    name = fields.Char(
        string="Name",
        help="Name of selected field.",
        compute="_change_m2o_fields",
    )

    m2o_fields = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Fields",
    )

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    nomenclature_blacklist = fields.Boolean(string="Ignore from nomenclature.")

    nomenclature_whitelist = fields.Boolean(string="Force to nomenclature.")

    @api.onchange("m2o_fields")
    def _change_m2o_fields(self):
        for ir_field in self:
            if ir_field.m2o_fields:
                ir_field.name = ir_field.m2o_fields.name
            else:
                self.name = False
