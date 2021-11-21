from odoo import models, fields, api, modules, tools


class CodeGeneratorCode(models.Model):
    _name = "code.generator.model.code"
    _description = "Code to display in model"

    name = fields.Char(string="Method name", help="Method name", required=True)

    sequence = fields.Integer(
        string="Sequence", help="Order of sequence code."
    )

    code = fields.Text(
        string="Code of pre_init_hook",
        default="""
return""",
    )

    decorator = fields.Char(
        string="Decorator",
        help="Like @api.model. Use ; for multiple decorator.",
    )

    param = fields.Char(string="Param", help="Like : name,color")

    returns = fields.Char(
        string="Return type", help="Annotation to return type value."
    )

    m2o_module = fields.Many2one(
        "code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    m2o_model = fields.Many2one(
        "ir.model", string="Model", help="Model", ondelete="cascade"
    )

    is_wip = fields.Boolean(
        string="Work in progress", help="Temporary function to be fill later."
    )

    is_templated = fields.Boolean(
        string="Templated", help="Code for code generator from template."
    )
