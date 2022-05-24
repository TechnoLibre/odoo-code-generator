from odoo import _, api, fields, models, modules, tools


class CodeGeneratorSnippet(models.Model):
    """
    Documentation will show result depend on different case.
    Check cases in file code_generator_demo_website_multiple_snippet/hooks.py
    # TODO automatise this documentation
    """

    _name = "code.generator.snippet"
    _description = "Code Generator snippet generated"

    name = fields.Char(
        help="Snippet name",
    )

    debug_doc = fields.Char(
        help="String to help debugging documentation.",
    )

    model_name = fields.Char(
        help=(
            "Model to support. Separate model name by ';' to create a list."
            " Will generate field of all this model."
        ),
    )

    model_short_name = fields.Char(
        help=(
            "Associate to model_name, the short will be use to simplify code,"
            " use _ and not space or dot. Separate model name by ';' to create"
            " a list."
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
        """
        case 1: 'demo_website_multiple_snippet_helloworld_static_structure'
        case 2: 'demo_website_multiple_snippet_helloworld_structure'
        case 3: 'demo_website_multiple_snippet_individual_item_structure'
        case 4: 'demo_website_multiple_snippet_list_show_time_item_structure'
        case 5: 'demo_website_multiple_snippet_list_item_structure'
        case 6: 'demo_website_multiple_snippet_list_item_structure_generic'
        case 7: 'demo_website_multiple_snippet_list_item_structure_double'
        case 8: 'demo_website_multiple_snippet_helloworld_effect'
        case 9: 'demo_website_multiple_snippet_individual_item_effect'
        case 10: 'demo_website_multiple_snippet_helloworld_feature'
        case 11: 'demo_website_multiple_snippet_individual_item_feature'
        case 12: 'demo_website_multiple_snippet_helloworld_content'
        case 13: 'demo_website_multiple_snippet_individual_item_content'
        """
        for rec in self:
            module_snippet_name = ""
            if rec.code_generator_id:
                module_snippet_name += rec.code_generator_id.name
            if rec.name:
                if module_snippet_name:
                    module_snippet_name += "_"
                module_snippet_name += rec.name.replace(" ", "_")
            rec.module_snippet_name = module_snippet_name.lower()

    @api.model
    def get_model_list(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo.model.portal']
        case 4: ['demo.model.portal']
        case 5: ['demo.model.portal']
        case 6: ['demo.model.portal']
        case 7: ['demo.model.portal', 'demo.model_2.portal', 'demo.model_3.portal.diagram']
        case 8: []
        case 9: ['demo.model.portal']
        case 10: []
        case 11: ['demo.model.portal']
        case 12: []
        case 13: ['demo.model.portal']
        """
        if self.model_name:
            return self.model_name.split(";")
        return []

    @api.model
    def get_snippet_template_xml_id(self):
        """
        case 1: 's_demo_website_multiple_snippet_helloworld_static_structure'
        case 2: 's_demo_website_multiple_snippet_helloworld_structure'
        case 3: 's_demo_website_multiple_snippet_individual_item_structure'
        case 4: 's_demo_website_multiple_snippet_list_show_time_item_structure'
        case 5: 's_demo_website_multiple_snippet_list_item_structure'
        case 6: 's_demo_website_multiple_snippet_list_item_structure_generic'
        case 7: 's_demo_website_multiple_snippet_list_item_structure_double'
        case 8: 's_demo_website_multiple_snippet_helloworld_effect'
        case 9: 's_demo_website_multiple_snippet_individual_item_effect'
        case 10: 's_demo_website_multiple_snippet_helloworld_feature'
        case 11: 's_demo_website_multiple_snippet_individual_item_feature'
        case 12: 's_demo_website_multiple_snippet_helloworld_content'
        case 13: 's_demo_website_multiple_snippet_individual_item_content'
        """
        return f"s_{self.module_snippet_name}"

    @api.model
    def get_snippet_template_class(self):
        """
        case 1: 'o_demo_website_multiple_snippet_helloworld_static_structure'
        case 2: 'o_demo_website_multiple_snippet_helloworld_structure'
        case 3: 'o_demo_website_multiple_snippet_individual_item_structure'
        case 4: 'o_demo_website_multiple_snippet_list_show_time_item_structure'
        case 5: 'o_demo_website_multiple_snippet_list_item_structure'
        case 6: 'o_demo_website_multiple_snippet_list_item_structure_generic'
        case 7: 'o_demo_website_multiple_snippet_list_item_structure_double'
        case 8: 'o_demo_website_multiple_snippet_helloworld_effect'
        case 9: 'o_demo_website_multiple_snippet_individual_item_effect'
        case 10: 'o_demo_website_multiple_snippet_helloworld_feature'
        case 11: 'o_demo_website_multiple_snippet_individual_item_feature'
        case 12: 'o_demo_website_multiple_snippet_helloworld_content'
        case 13: 'o_demo_website_multiple_snippet_individual_item_content'
        """
        return f"o_{self.module_snippet_name}"

    @api.model
    def get_snippet_list_name(self):
        """
        case 1: '_list'
        case 2: '_list'
        case 3: 'demo_model_portal_list'
        case 4: 'portal_time_list'
        case 5: 'portal_list'
        case 6: 'demo_model_portal_list'
        case 7: 'double_portal_list'
        case 8: '_list'
        case 9: 'demo_model_portal_list'
        case 10: '_list'
        case 11: 'demo_model_portal_list'
        case 12: '_list'
        case 13: 'demo_model_portal_list'
        """
        if self.model_short_name:
            lst_model_short_name = self.model_short_name.split(";")
        else:
            lst_model_short_name = []
        lst_model_name = self.get_model_list()
        if lst_model_short_name:
            if len(lst_model_short_name) == 1:
                lst_model_name = lst_model_short_name
            else:
                lst_model_name = [
                    f"{a}_{lst_model_name[i]}"
                    for i, a in enumerate(lst_model_short_name)
                ]
        model_name_list_xml_name = (
            "_and_".join([a.replace(".", "_") for a in lst_model_name])
            + "_list"
        )
        return model_name_list_xml_name.replace(".", "_").lower()

    @api.model
    def get_snippet_xml_id_list_name(self):
        """
        case 1: '_list_helloworld_static_structure'
        case 2: '_list_helloworld_structure'
        case 3: 'demo_model_portal_list_individual_item_structure'
        case 4: 'demo_model_portal_list_list_show_time_item_structure'
        case 5: 'demo_model_portal_list_list_item_structure'
        case 6: 'demo_model_portal_list_list_item_structure_generic'
        case 7: 'demo_model_portal_and_demo_model_2_portal_and_demo_model_3_portal_diagram_list_list_item_structure_double'
        case 8: '_list_helloworld_effect'
        case 9: 'demo_model_portal_list_individual_item_effect'
        case 10: '_list_helloworld_feature'
        case 11: 'demo_model_portal_list_individual_item_feature'
        case 12: '_list_helloworld_content'
        case 13: 'demo_model_portal_list_individual_item_content'
        """
        # TODO support short name
        lst_model_name = self.get_model_list()
        model_name_list_xml_name = (
            "_and_".join([a.replace(".", "_") for a in lst_model_name])
            + "_list"
        )
        if self.name:
            model_name_list_xml_name += "_" + self.name.replace(" ", "_")
        return model_name_list_xml_name.replace(".", "_").lower()

    @api.model
    def get_snippet_url_list_section_name(self):
        """
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
        case 6:
        case 7: ['demo_model_portal', 'demo_model_2_portal', 'demo_model_3_portal_diagram']
        case 8:
        case 9:
        case 10:
        case 11:
        case 12:
        case 13:
        """
        lst_section = []
        lst_model_name = self.get_model_list()
        if len(lst_model_name) > 1:
            lst_section = lst_model_name
        if not lst_section and self.model_short_name:
            lst_model_short_name = self.model_short_name.split(";")
            if len(lst_model_short_name) == 1:
                lst_section = lst_model_short_name
        if not lst_section and len(lst_model_name) == 1:
            lst_section = lst_model_name
        return [a.replace(".", "_") for a in lst_section]

    @api.model
    def get_snippet_xml_id_unit_name(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal_unit_individual_item_structure']
        case 4: ['demo_model_portal_unit_list_show_time_item_structure']
        case 5: ['demo_model_portal_unit_list_item_structure']
        case 6: ['demo_model_portal_unit_list_item_structure_generic']
        case 7: ['demo_model_portal_unit_list_item_structure_double', 'demo_model_2_portal_unit_list_item_structure_double', 'demo_model_3_portal_diagram_unit_list_item_structure_double']
        case 8: []
        case 9: ['demo_model_portal_unit_individual_item_effect']
        case 10: []
        case 11: ['demo_model_portal_unit_individual_item_feature']
        case 12: []
        case 13: ['demo_model_portal_unit_individual_item_content']
        """
        suffix = ""
        if self.name:
            suffix = f"_{self.name.replace(' ', '_')}"
        lst_model_name = [a + "_unit" + suffix for a in self.get_model_list()]
        return [a.replace(".", "_").lower() for a in lst_model_name]

    @api.model
    def get_model_var_class_name(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal_cls']
        case 4: ['demo_model_portal_cls']
        case 5: ['demo_model_portal_cls']
        case 6: ['demo_model_portal_cls']
        case 7: ['demo_model_portal_cls', 'demo_model_2_portal_cls', 'demo_model_3_portal_diagram_cls']
        case 8: []
        case 9: ['demo_model_portal_cls']
        case 10: []
        case 11: ['demo_model_portal_cls']
        case 12: []
        case 13: ['demo_model_portal_cls']
        """
        return [a.replace(".", "_") + "_cls" for a in self.get_model_list()]

    @api.model
    def get_model_var_id(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal_id']
        case 4: ['demo_model_portal_id']
        case 5: ['demo_model_portal_id']
        case 6: ['demo_model_portal_id']
        case 7: ['demo_model_portal_id', 'demo_model_2_portal_id', 'demo_model_3_portal_diagram_id']
        case 8: []
        case 9: ['demo_model_portal_id']
        case 10: []
        case 11: ['demo_model_portal_id']
        case 12: []
        case 13: ['demo_model_portal_id']
        """
        return [a.replace(".", "_") + "_id" for a in self.get_model_list()]

    @api.model
    def get_model_var_ids(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal_ids']
        case 4: ['demo_model_portal_ids']
        case 5: ['demo_model_portal_ids']
        case 6: ['demo_model_portal_ids']
        case 7: ['demo_model_portal_ids', 'demo_model_2_portal_ids', 'demo_model_3_portal_diagram_ids']
        case 8: []
        case 9: ['demo_model_portal_ids']
        case 10: []
        case 11: ['demo_model_portal_ids']
        case 12: []
        case 13: ['demo_model_portal_ids']
        """
        return [a.replace(".", "_") + "_ids" for a in self.get_model_list()]

    @api.model
    def get_model_var_short(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal']
        case 4: ['portal_time']
        case 5: ['portal']
        case 6: ['demo_model_portal']
        case 7: ['double_portal_demo_model_portal', 'double_portal_demo_model_2_portal', 'double_portal_demo_model_3_portal_diagram']
        case 8: []
        case 9: ['demo_model_portal']
        case 10: []
        case 11: ['demo_model_portal']
        case 12: []
        case 13: ['demo_model_portal']
        """
        lst_model_name = self.get_model_list()
        if self.model_short_name:
            lst_model_short_name = self.model_short_name.split(";")
            if len(lst_model_short_name) == 1:
                if len(lst_model_name) == 1:
                    lst_value = [lst_model_short_name[0]]
                else:
                    lst_value = [
                        lst_model_short_name[0] + "_" + a
                        for a in lst_model_name
                    ]
            else:
                lst_value = [a for a in lst_model_short_name]
        else:
            lst_value = lst_model_name
        return [a.replace(".", "_") for a in lst_value]

    @api.model
    def get_snippet_xml_name_title(self):
        """
        case 1: []
        case 2: []
        case 3: ['Demo Model Portal']
        case 4: ['Portal Time']
        case 5: ['Portal']
        case 6: ['Demo Model Portal']
        case 7: ['Double Portal Demo Model Portal', 'Double Portal Demo Model 2 Portal', 'Double Portal Demo Model 3 Portal']
        case 8: []
        case 9: ['Demo Model Portal']
        case 10: []
        case 11: ['Demo Model Portal']
        case 12: []
        case 13: ['Demo Model Portal']
        """
        return [
            a.replace("_", " ").title() for a in self.get_model_var_short()
        ]

    @api.model
    def get_snippet_xml_name_title_list(self):
        """
        case 3: 'Demo Model Portal'
        case 4: 'Portal Time List'
        case 5: 'Portal List'
        case 6: 'Demo Model Portal List'
        case 7: 'Double Portal List'
        """
        return self.get_snippet_list_name().replace("_", " ").title()

    @api.model
    def get_model_var_s(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal_s']
        case 4: ['portal_times']
        case 5: ['portals']
        case 6: ['demo_model_portal_s']
        case 7: ['double_portal_demo_model_portal_s', 'double_portal_demo_model_2_portal_s', 'double_portal_demo_model_3_portal_diagram_s']
        case 8: []
        case 9: ['demo_model_portal_s']
        case 10: []
        case 11: ['demo_model_portal_s']
        case 12: []
        case 13: ['demo_model_portal_s']
        """
        suffix = "s"
        sep_suffix = f"_{suffix}"
        lst_model_name = self.get_model_list()
        if self.model_short_name:
            lst_model_short_name = self.model_short_name.split(";")
            if len(lst_model_short_name) == 1:
                if len(lst_model_name) == 1:
                    lst_value = [lst_model_short_name[0] + suffix]
                else:
                    lst_value = [
                        lst_model_short_name[0]
                        + "_"
                        + a.replace(".", "_")
                        + sep_suffix
                        for a in lst_model_name
                    ]
            else:
                lst_value = [a + suffix for a in lst_model_short_name]
        else:
            lst_value = [
                a.replace(".", "_") + sep_suffix for a in lst_model_name
            ]
        return lst_value

    @api.model
    def get_model_var(self):
        """
        case 1: []
        case 2: []
        case 3: ['demo_model_portal']
        case 4: ['portal_time']
        case 5: ['portal']
        case 6: ['demo_model_portal']
        case 7: ['double_portal_demo_model_portal', 'double_portal_demo_model_2_portal', 'double_portal_demo_model_3_portal_diagram']
        case 8: []
        case 9: ['demo_model_portal']
        case 10: []
        case 11: ['demo_model_portal']
        case 12: []
        case 13: ['demo_model_portal']
        """
        lst_model_name = self.get_model_list()
        if self.model_short_name:
            lst_model_short_name = self.model_short_name.split(";")
            if len(lst_model_short_name) == 1:
                if len(lst_model_name) == 1:
                    lst_value = [lst_model_short_name[0]]
                else:
                    lst_value = [
                        lst_model_short_name[0] + "_" + a.replace(".", "_")
                        for a in lst_model_name
                    ]
            else:
                lst_value = [a for a in lst_model_short_name]
        else:
            lst_value = [a.replace(".", "_") for a in lst_model_name]
        return lst_value

    @api.model
    def get_url_get_page(self):
        lst_section_name = self.get_snippet_url_list_section_name()
        return [
            f"/{self.code_generator_id.name}/{a}/" for a in lst_section_name
        ]

    @api.model
    def get_url_get_list(self):
        model_short_name_list = self.get_snippet_list_name()
        return f"/{self.code_generator_id.name}/{model_short_name_list}"

    @api.model
    def get_model_var_prefix_associate_var(self):
        """
        case 1: []
        case 2: []
        case 3: ['']
        case 4: ['']
        case 5: ['']
        case 6: ['']
        case 7: ['_demo_model_portal', '_demo_model_2_portal', '_demo_model_3_portal_diagram']
        case 8: []
        case 9: ['']
        case 10: []
        case 11: ['']
        case 12: []
        case 13: ['']
        """
        # When a variable referred to a model, use this prefix
        lst_model_name = self.get_model_list()
        if len(lst_model_name) <= 1:
            lst_value = ["" for _ in lst_model_name]
        else:
            if self.model_short_name:
                lst_model_short_name = self.model_short_name.split(";")
                if len(lst_model_short_name) == 1:
                    if len(lst_model_name) == 1:
                        lst_value = ["_" + lst_model_short_name[0]]
                    else:
                        lst_value = [
                            "_" + a.replace(".", "_") for a in lst_model_name
                        ]
                else:
                    lst_value = ["_" + a for a in lst_model_short_name]
            else:
                lst_value = ["_" + a.replace(".", "_") for a in lst_model_name]
        return lst_value
