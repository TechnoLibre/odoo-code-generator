from odoo import models, fields, api, modules, tools


class CodeGeneratorMenu(models.Model):
    _name = "code.generator.menu"
    _description = "Code Generator Menu"

    # TODO missing groups_id and active and web_icon or web_icon_data
    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    # TODO use ir.model.data instead if id_name
    id_name = fields.Char(
        string="Menu id",
        help="Specify id name of this menu.",
    )

    m2o_act_window = fields.Many2one(
        comodel_name="code.generator.act_window",
        string="Action Windows",
        help="Act window to open when click on this menu.",
    )

    # TODO use ir.model.data instead if parent_id_name
    parent_id_name = fields.Char(
        string="Menu parent id",
        help="Specify id name of parent menu, optional.",
    )

    sequence = fields.Integer(default=10)
