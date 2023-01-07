from odoo import api, fields, models, modules, tools


class CodeGeneratorMenu(models.Model):
    _name = "code.generator.menu"
    _description = "Code Generator Menu"

    name = fields.Char(help="Menu name")

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

    ignore_act_window = fields.Boolean(
        help="Set True to force no act_window, like a parent menu."
    )

    m2o_act_window = fields.Many2one(
        comodel_name="code.generator.act_window",
        string="Action Windows",
        help="Act window to open when click on this menu.",
    )

    # TODO use ir.model.data instead if parent_id_name
    # parent_id_name is fill in cg hook, but need parent_id instead to find ir.model.data associate
    # Or do refactoring where preprocessing metadata
    # But parent_id_name is a good way to try to know the parent from template, because we cannot use id
    parent_id_name = fields.Char(
        string="Menu parent id",
        help="Specify id name of parent menu, optional.",
    )

    sequence = fields.Integer()

    web_icon = fields.Char(help="Icon menu")
