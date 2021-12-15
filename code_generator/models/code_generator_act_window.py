from odoo import api, fields, models, modules, tools


class CodeGeneratorActWindow(models.Model):
    _name = "code.generator.act_window"
    _description = "Code Generator Act Window"

    name = fields.Char(string="name")

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    # TODO use ir.model.data instead if id_name
    id_name = fields.Char(
        string="Action id",
        help="Specify id name of this action window.",
    )
