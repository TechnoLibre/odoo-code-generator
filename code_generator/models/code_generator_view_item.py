from odoo import models, fields, api, modules, tools


class CodeGeneratorViewItem(models.Model):
    _name = "code.generator.view.item"
    _description = "Code Generator View Item"

    action_name = fields.Char(string="Action name")

    sequence = fields.Integer(string="Sequence", default=1)

    # TODO create HTML for specific label
    label = fields.Char(string="Label")

    item_type = fields.Selection(
        [
            ("field", "Field"),
            ("button", "Button"),
            ("html", "HTML"),
            ("filter", "Filter"),
            ("div", "Division"),
            ("group", "Group"),
            ("templates", "Templates"),
            ("t", "T"),
            ("ul", "UL"),
            ("li", "LI"),
            ("i", "I"),
            ("strong", "Strong"),
        ],
        default="field",
        help="Choose item type to generate.",
    )

    button_type = fields.Selection(
        [
            ("", ""),  # Default
            ("btn-default", "Default"),  # Default
            ("btn-primary", "Primary"),
            ("btn-secondary", "Secondary"),  # Default
            ("btn-link", "Link"),  # URL
            ("btn-success", "Success"),  # Green
            ("btn-warning", "Warning"),  # Yellow
            ("btn-danger", "Danger"),  # Red
            ("oe_highlight", "Highlight"),  # Primary
            ("oe_stat_button", "Statistic"),  # Default
        ],
        default="",
        help="Choose item type to generate.",
    )

    background_type = fields.Selection(
        [
            ("", ""),  # Default
            ("bg-success", "Success"),  # Default
            # ("bg-success-light", "Success light"),
            ("bg-success-full", "Success full"),
            ("bg-warning", "Warning"),
            # ("bg-warning-light", "Warning light"),
            ("bg-warning-full", "Warning full"),
            ("bg-info", "Info"),
            # ("bg-info-light", "Info light"),
            ("bg-info-full", "Info full"),
            ("bg-danger", "Danger"),
            # ("bg-danger-light", "Danger light"),
            ("bg-danger-full", "Danger full"),
            ("bg-light", "Light"),
            ("bg-dark", "Dark"),
        ],
        default="",
        help="Choose background color of HTML.",
    )

    section_type = fields.Selection(
        [
            ("header", "Header"),
            ("title", "Title"),
            ("body", "Body"),
            ("footer", "Footer"),
        ],
        default="body",
        help="Choose item type to generate.",
    )

    colspan = fields.Integer(
        string="Colspan",
        default=1,
        help="Use this to fill more column, check HTML table.",
    )

    placeholder = fields.Char(string="Placeholder")

    password = fields.Boolean(string="Password", help="Hide character.")

    icon = fields.Char(
        string="Icon",
        help="Example fa-television. Only supported with button.",
    )

    attrs = fields.Char(
        string="Attributes",
        help="Specific condition, search attrs for more information.",
    )

    is_required = fields.Boolean(string="Required")

    is_invisible = fields.Boolean(string="Invisible")

    is_readonly = fields.Boolean(string="Readonly")

    is_help = fields.Boolean(string="Help")

    has_label = fields.Boolean(string="Labeled", help="Label for title.")

    parent_id = fields.Many2one(comodel_name="code.generator.view.item")

    child_id = fields.One2many(
        comodel_name="code.generator.view.item",
        inverse_name="parent_id",
    )

    edit_only = fields.Boolean(string="Edit only")
