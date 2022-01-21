from odoo import api, fields, models, modules, tools


class CodeGeneratorViewItem(models.Model):
    _name = "code.generator.view.item"
    _description = "Code Generator View Item"

    name = fields.Char(help="name attribute")

    action_name = fields.Char(string="Action name")

    aria_label = fields.Char(help="aria-label attribute")

    attrs = fields.Char(
        string="Attributes",
        help="Specific condition, search attrs for more information.",
    )

    background_type = fields.Selection(
        selection=[
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

    button_type = fields.Selection(
        selection=[
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

    child_id = fields.One2many(
        comodel_name="code.generator.view.item",
        inverse_name="parent_id",
        string="Child",
    )

    class_attr = fields.Char(help="Update class attribute")

    colspan = fields.Integer(
        default=1, help="Use this to fill more column, check HTML table."
    )

    context = fields.Char(help="context attribute")

    domain = fields.Char(help="domain attribute")

    edit_only = fields.Boolean(string="Edit only")

    expr = fields.Char(help="Example: //field[@name='name']")

    has_label = fields.Boolean(
        string="Labeled",
        help="Label for title.",
    )

    icon = fields.Char(
        help="Example fa-television. Only supported with button."
    )

    is_help = fields.Boolean(string="Help")

    is_invisible = fields.Boolean(string="Invisible")

    is_readonly = fields.Boolean(string="Readonly")

    is_required = fields.Boolean(string="Required")

    item_type = fields.Selection(
        selection=[
            ("field", "Field"),
            ("button", "Button"),
            ("html", "HTML"),
            ("filter", "Filter"),
            ("div", "Division"),
            ("group", "Group"),
            ("xpath", "Xpath"),
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

    # TODO create HTML for specific label
    label = fields.Char()

    parent_id = fields.Many2one(
        comodel_name="code.generator.view.item",
        string="Parent",
    )

    password = fields.Boolean(help="Hide character.")

    placeholder = fields.Char()

    position = fields.Selection(
        selection=[
            ("inside", "Inside"),
            ("replace", "Replace"),
            ("after", "After"),
            ("before", "Before"),
            ("attributes", "Attributes"),
            ("move", "Move"),
        ]
    )

    role = fields.Char(help="role attribute")

    section_type = fields.Selection(
        selection=[
            ("header", "Header"),
            ("title", "Title"),
            ("body", "Body"),
            ("footer", "Footer"),
        ],
        default="body",
        help="Choose item type to generate.",
    )

    sequence = fields.Integer(default=1)

    t_attf_class = fields.Char(help="t-attf-class attribute")

    t_if = fields.Char(help="t-if attribute")

    t_name = fields.Char(help="t_name attribute")

    title = fields.Char(help="title attribute")

    type = fields.Selection(
        selection=[
            ("row", "Row"),
            ("col", "Col"),
            ("measure", "Measure"),
        ],
        help="Statistique type.",
    )

    widget = fields.Char(help="widget attribute")
