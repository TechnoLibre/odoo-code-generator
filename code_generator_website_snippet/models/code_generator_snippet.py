from odoo import _, api, fields, models, modules, tools


class CodeGeneratorSnippet(models.Model):
    _name = "code.generator.snippet"
    _description = "Code Generator snippet generated"

    name = fields.Char(
        help="Snippet name",
    )

    model_name = fields.Char(
        help=(
            "Model to support. Separate model name by ';' to create a list."
            " Will generate field of all this model."
        ),
    )

    model_short_name = fields.Char(
        help=(
            "Associate to model_name, the short will be use to simplify code."
            " Separate model name by ';' to create a list."
        ),
    )

    # TODO module_snippet_name need to be unique per code_generator_id
    module_snippet_name = fields.Char(
        compute="_compute_module_snippet_name", store=True
    )

    enable_javascript = fields.Boolean(
        help="Add Javascript code into snippet."
    )

    controller_feature = fields.Selection(
        selection=[
            ("helloworld", "Helloworld"),
            ("model_show_item_individual", "Model show item individual"),
            ("model_show_item_list", "Model show item list"),
        ],
        default="model_show_item_individual",
    )

    limitation_item = fields.Integer(
        help="Limit item show, support only with model_show_item_list."
    )

    show_diff_time = fields.Boolean(
        help=(
            "Show diff time from creation, support only with"
            " model_show_item_list."
        )
    )

    show_recent_item = fields.Boolean(
        help=(
            "Order item by desc create_date, support only with"
            " model_show_item_list."
        )
    )

    snippet_type = fields.Selection(
        selection=[
            ("structure", "Structure"),
            ("content", "Content"),
            ("feature", "Feature"),
            ("effect", "Effect"),
        ],
        default="structure",
    )

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "module_snippet_name_uniq",
            "unique (module_snippet_name)",
            _("Module snippet name already exists!"),
        ),
    ]

    @api.depends("code_generator_id", "name")
    def _compute_module_snippet_name(self):
        for rec in self:
            module_snippet_name = ""
            if rec.code_generator_id:
                module_snippet_name += rec.code_generator_id.name
            if rec.name:
                if module_snippet_name:
                    module_snippet_name += "_"
                module_snippet_name += rec.name.replace(" ", "_")
            rec.module_snippet_name = module_snippet_name
