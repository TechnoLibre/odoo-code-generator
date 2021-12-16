from odoo import api, fields, models, modules, tools


class CodeGeneratorIrModelFields(models.Model):
    _name = "code.generator.ir.model.fields"
    _description = "Code Generator Fields"

    name = fields.Char(
        string="Name",
        help="Name of selected field.",
        compute="_change_m2o_fields",
    )

    is_show_whitelist_model_inherit = fields.Boolean(
        string="Show in whitelist model inherit",
        help=(
            "If a field in model is in whitelist, will be show in generated"
            " model."
        ),
    )

    selection = fields.Char(
        string="Selection Options",
        default="",
        help=(
            "List of options for a selection field, specified as a Python"
            " expression defining a list of (key, label) pairs. For example:"
            " [('blue','Blue'),('yellow','Yellow')]"
        ),
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
