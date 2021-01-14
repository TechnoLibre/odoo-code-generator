from odoo import _, models, fields, api
from odoo.models import MAGIC_COLUMNS
from lxml.builder import E
from lxml import etree as ET

MAGIC_FIELDS = MAGIC_COLUMNS + ['display_name', '__last_update', 'access_url', 'access_token', 'access_warning']


class CodeGeneratorGenerateViewsWizard(models.TransientModel):
    _name = "code.generator.generate.views.wizard"
    _description = "Code Generator Generate Views Wizard"

    # @api.model
    # def default_get(self, fields):
    #     result = super(CodeGeneratorGenerateViewsWizard, self).default_get(fields)
    #     code_generator_id = self.env["code.generator.module"].browse(result.get("code_generator_id"))
    #     lst_model_id = [a.id for a in code_generator_id.o2m_models]
    # Don't need that solution
    #     result["selected_model_list_view_ids"] = [(6, 0, lst_model_id)]
    #     result["selected_model_form_view_ids"] = [(6, 0, lst_model_id)]
    #     return result

    code_generator_id = fields.Many2one(comodel_name="code.generator.module", string="Code Generator", required=True,
                                        ondelete='cascade')

    enable_generate_all = fields.Boolean(string="Enable all feature",
                                         default=True,
                                         help="Generate with all feature.")

    date = fields.Date(
        string="Date", required=True, default=fields.Date.context_today,
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda s: s.env.user.id,
    )

    name = fields.Char(
        string="Name",
    )

    clear_all_view = fields.Boolean(
        string="Clear views",
        default=True,
        help="Clear all views before execute."
    )

    clear_all_access = fields.Boolean(
        string="Clear access",
        default=True,
        help="Clear all access/permission before execute."
    )

    clear_all_menu = fields.Boolean(
        string="Clear menus",
        default=True,
        help="Clear all menus before execute."
    )

    clear_all_act_window = fields.Boolean(
        string="Clear actions windows",
        default=True,
        help="Clear all actions windows before execute."
    )

    all_model = fields.Boolean(
        string="All models",
        default=True,
        help="Generate with all existing model, or select manually."
    )

    selected_model_list_view_ids = fields.Many2many(comodel_name="ir.model",
                                                    relation="selected_model_list_view_ids_ir_model")

    selected_model_form_view_ids = fields.Many2many(comodel_name="ir.model",
                                                    relation="selected_model_form_view_ids_ir_model")

    generated_root_menu = None
    generated_parent_menu = None
    nb_sub_menu = 0

    def clear_all(self):
        if self.clear_all_view and self.code_generator_id.o2m_model_views:
            self.code_generator_id.o2m_model_views.unlink()
        if self.clear_all_access and self.code_generator_id.o2m_model_access:
            self.code_generator_id.o2m_model_access.unlink()
        if self.clear_all_menu and self.code_generator_id.o2m_menus:
            self.code_generator_id.o2m_menus.unlink()
        if self.clear_all_act_window:
            if self.code_generator_id.o2m_model_act_window:
                self.code_generator_id.o2m_model_act_window.unlink()
            if self.code_generator_id.o2m_model_act_todo:
                self.code_generator_id.o2m_model_act_todo.unlink()
            if self.code_generator_id.o2m_model_act_url:
                self.code_generator_id.o2m_model_act_url.unlink()

    @api.multi
    def button_generate_views(self):
        self.ensure_one()

        # Add dependencies
        self._add_dependencies()

        self.clear_all()

        o2m_models_view_list = self.code_generator_id.o2m_models if self.all_model else self.selected_model_list_view_ids
        o2m_models_view_form = self.code_generator_id.o2m_models if self.all_model else self.selected_model_form_view_ids
        lst_model = sorted(set(o2m_models_view_list + o2m_models_view_form), key=lambda model: model.name)

        for model_id in lst_model:
            lst_view_generated = []

            # Different view
            if model_id in o2m_models_view_list:
                is_whitelist = bool(model_id.field_id.filtered(lambda field: field.is_show_whitelist_list_view))
                model_created_fields_list = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS and not field.is_hide_blacklist_list_view and (
                            not is_whitelist or (is_whitelist and field.is_show_whitelist_list_view)))
                self._generate_list_views_models(model_id, model_created_fields_list, model_id.m2o_module)
                lst_view_generated.append("list")
            if model_id in o2m_models_view_form:
                is_whitelist = bool(model_id.field_id.filtered(lambda field: field.is_show_whitelist_form_view))
                model_created_fields_form = model_id.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS and not field.is_hide_blacklist_form_view and (
                            not is_whitelist or (is_whitelist and field.is_show_whitelist_form_view)))
                self._generate_form_views_models(model_id, model_created_fields_form, model_id.m2o_module)
                lst_view_generated.append("form")

            # Menu and action_windows
            if lst_view_generated:
                self._generate_menu(model_id, model_id.m2o_module, lst_view_generated)

        # for model_id in o2m_models_view_form:
        #     print(model_id)
        # model_created_fields = model_id.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS).mapped(
        #     'name')
        #
        # self._generate_list_views_models(model_id, model_created_fields, model_id.m2o_module)
        # self._generate_menu(model_id, model_id.m2o_module)

        for model_id in self.code_generator_id.o2m_models:
            self._generate_model_access(model_id)

        return True

    def _add_dependencies(self):
        pass

    def _generate_list_views_models(self, model_created, model_created_fields, module):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        lst_field = [
            E.field({"name": a.name}) for a in model_created_fields
        ]
        arch_xml = E.tree({
            # TODO enable this when missing form
            # "editable": "top",
        },
            *lst_field
        )
        str_arch = ET.tostring(arch_xml, pretty_print=True)
        view_value = self.env['ir.ui.view'].create({
            'name': f"{model_name_str}_tree",
            'type': 'tree',
            'model': model_name,
            'arch': str_arch,
            'm2o_model': model_created.id,
        })

        return view_value

    def _generate_form_views_models(self, model_created, model_created_fields, module):
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        lst_field = []
        lst_group = []
        for model in model_created_fields:
            lst_value = []
            value = {
                "name": model.name
            }
            lst_value.append(value)

            key = "geo_"
            if key in model.ttype:
                value["widget"] = "geo_edit_map"
                # value["attrs"] = "{'invisible': [('type', '!=', '"f"{model[len(key):]}')]""}"
            # lst_field.append(value)
            lst_group.append(E.group({},
                                     E.field(value)))
        form_xml = E.form({
            "string": "Titre",
        },
            E.sheet({},
                    *lst_group)
        )
        str_arch = ET.tostring(form_xml, pretty_print=True)
        view_value = self.env['ir.ui.view'].create({
            'name': f"{model_name_str}_form",
            'type': 'form',
            'model': model_name,
            'arch': str_arch,
            'm2o_model': model_created.id,
        })

        return view_value

    def _generate_model_access(self, model_created):
        # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
        # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
        lang = "en_US"
        group_id = self.env.ref('base.group_user').with_context(lang=lang)
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        v = {
            'name': '%s Access %s' % (model_name_str, group_id.full_name),
            'model_id': model_created.id,
            'group_id': group_id.id,
            'perm_read': True,
            'perm_create': True,
            'perm_write': True,
            'perm_unlink': True,
        }

        access_value = self.env['ir.model.access'].create(v)

    def _generate_menu(self, model_created, module, lst_view_generated):
        # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
        # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
        group_id = self.env.ref('base.group_user')
        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")
        module_name = module.name
        # Create root if not exist
        if not self.generated_root_menu:
            v = {
                'name': f"root_{module_name}",
                'sequence': 20,
                'web_icon': f'code_generator,static/description/icon_new_application.png',
                # 'group_id': group_id.id,
                'm2o_module': module.id,
            }
            self.generated_root_menu = self.env['ir.ui.menu'].create(v)
        if not self.generated_parent_menu:
            v = {
                'name': _("Models"),
                'sequence': 1,
                'parent_id': self.generated_root_menu.id,
                # 'group_id': group_id.id,
                'm2o_module': module.id,
            }
            self.generated_parent_menu = self.env['ir.ui.menu'].create(v)

        help_str = f"""<p class="o_view_nocontent_empty_folder">
        Add a new {model_name_str}
      </p>
      <p>
        Databases whose tables could be imported to Odoo and then be exported into code
      </p>"""

        view_mode = ",".join(sorted(set(lst_view_generated), reverse=True))
        view_type = "form" if "form" in lst_view_generated else lst_view_generated[0]

        # Create action
        v = {
            'name': f"{model_name_str}_action_view",
            'res_model': model_name,
            'type': 'ir.actions.act_window',
            'view_mode': view_mode,
            'view_type': view_type,
            # 'help': help_str,
            # 'search_view_id': self.search_view_id.id,
            'context': {},
            'm2o_res_model': model_created.id,
        }
        action_id = self.env['ir.actions.act_window'].create(v)

        # Create menu

        self.nb_sub_menu += 1

        v = {
            'name': model_name_str,
            'sequence': self.nb_sub_menu,
            'parent_id': self.generated_parent_menu.id,
            'action': 'ir.actions.act_window,%s' % action_id.id,
            # 'group_id': group_id.id,
            'm2o_module': module.id,
        }

        access_value = self.env['ir.ui.menu'].create(v)
