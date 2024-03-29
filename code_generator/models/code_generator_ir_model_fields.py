from odoo import api, fields, models, modules, tools


class CodeGeneratorIrModelFields(models.Model):
    _name = "code.generator.ir.model.fields"
    _description = "Code Generator Fields"

    name = fields.Char(
        compute="_change_m2o_fields",
        help="Name of selected field.",
    )

    code_generator_compute = fields.Char(
        string="Compute Code Generator",
        help="Compute method to code_generator_writer.",
    )

    comment_after = fields.Char(
        string="Comment after field",
        help=(
            "Will show comment after writing field in python. Support"
            " multiline. The comment is after if at the end of file."
        ),
    )

    comment_before = fields.Char(
        string="Comment before field",
        help=(
            "Will show comment before writing field in python. Support"
            " multiline."
        ),
    )

    default_lambda = fields.Char(string="Default lambda value")

    field_context = fields.Char()

    filter_field_attribute = fields.Char(
        help=(
            "Separate by ; to enumerate your attribute to filter, like a"
            " whitelist of attributes field."
        )
    )

    is_show_whitelist_model_inherit = fields.Boolean(
        string="Show in whitelist model inherit",
        help=(
            "If a field in model is in whitelist, will be show in generated"
            " model."
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

    selection = fields.Char(
        string="Selection Options",
        help=(
            "List of options for a selection field, specified as a Python"
            " expression defining a list of (key, label) pairs. For example:"
            " [('blue','Blue'),('yellow','Yellow')]"
        ),
    )

    @api.onchange("m2o_fields")
    def _change_m2o_fields(self):
        for ir_field in self:
            if ir_field.m2o_fields:
                ir_field.name = ir_field.m2o_fields.name
            else:
                self.name = False
