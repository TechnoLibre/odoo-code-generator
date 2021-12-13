from odoo import models, fields, api, modules, tools


class CodeGeneratorView(models.Model):
    _name = "code.generator.view"
    _description = "Code Generator View"

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    has_body_sheet = fields.Boolean(
        string="Sheet format",
        help="Use sheet presentation for body of form view.",
    )

    # TODO use ir.model.data instead if id_name
    id_name = fields.Char(
        string="View id",
        help="Specify id name of this view.",
    )

    inherit_view_name = fields.Char(
        help="Set inherit view name, use record id (ir.model.data)."
    )

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Code generator Model",
        help="Model related with this report",
    )

    view_item_ids = fields.Many2many(
        comodel_name="code.generator.view.item",
        string="View item",
        help="Item view to add in this view.",
    )

    view_name = fields.Char(string="View name")

    view_type = fields.Selection(
        [
            ("activity", "Activity"),
            ("calendar", "Calendar"),
            ("diagram", "Diagram"),
            ("form", "Form"),
            ("graph", "Graph"),
            ("kanban", "Kanban"),
            ("pivot", "Pivot"),
            ("search", "Search"),
            ("timeline", "Timeline"),
            ("tree", "Tree"),
        ],
        default="form",
        help="Choose view type to generate.",
    )
