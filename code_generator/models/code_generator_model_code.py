from odoo import api, fields, models, modules, tools


class CodeGeneratorModelCode(models.Model):
    _name = "code.generator.model.code"
    _description = "Code to display in model"

    name = fields.Char(
        string="Method name",
        required=True,
        help="Method name",
    )

    code = fields.Text(
        string="Code of pre_init_hook",
        default="""
return""",
    )

    decorator = fields.Char(
        help="Like @api.model. Use ; for multiple decorator."
    )

    is_templated = fields.Boolean(
        string="Templated",
        help="Code for code generator from template.",
    )

    is_wip = fields.Boolean(
        string="Work in progress",
        help="Temporary function to be fill later.",
    )

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        help="Model",
        ondelete="cascade",
    )

    m2o_module = fields.Many2one(
        comodel_name="code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    param = fields.Char(help="Like : name,color")

    returns = fields.Char(
        string="Return type",
        help="Annotation to return type value.",
    )

    sequence = fields.Integer(help="Order of sequence code.")
