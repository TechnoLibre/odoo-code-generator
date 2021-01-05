from odoo import _, models, fields, api
from odoo.models import MAGIC_COLUMNS
from lxml.builder import E
from lxml import etree as ET

MAGIC_FIELDS = MAGIC_COLUMNS + ['display_name', '__last_update', 'access_url', 'access_token', 'access_warning']


def _fmt_underscores(word):
    return word.lower().replace(".", "_")


def _fmt_camel(word):
    return word.replace(".", "_").title().replace("_", "")


def _fmt_title(word):
    return word.replace(".", " ").title()


def _get_field_by_user(model):
    lst_field = []
    lst_magic_fields = MAGIC_FIELDS + ['name']
    for field in model.field_id:
        if field.name not in lst_magic_fields:
            lst_field.append(field)
    return lst_field


class CodeGeneratorGeneratePortalWizard(models.TransientModel):
    _inherit = "code.generator.generate.views.wizard"

    selected_model_portal_ids = fields.Many2many(comodel_name="ir.model")

    enable_generate_portal = fields.Boolean(
        string="Enable portal feature",
        default=False,
        help="This variable need to be True to generate portal if enable_generate_all is False")

    @api.multi
    def button_generate_views(self):
        status = super(CodeGeneratorGeneratePortalWizard, self).button_generate_views()
        if not status or (not self.enable_generate_all and not self.enable_generate_portal):
            self.code_generator_id.enable_generate_portal = False
            return status

        self.code_generator_id.enable_generate_portal = True

        model_portal_mixin = self.env["ir.model"].search([("model", "=", "portal.mixin")])

        o2m_models = self.code_generator_id.o2m_models if self.all_model else self.selected_model_ids
        self.generate_portal_menu_entry(o2m_models, self.code_generator_id.name)
        self.generate_portal_home_entry(o2m_models, self.code_generator_id.name)
        self.generate_portal_list_model(o2m_models, self.code_generator_id.name)
        self.generate_portal_form_model(o2m_models, self.code_generator_id.name)

        for model_id in o2m_models:
            model_created_fields = model_id.field_id.filtered(lambda field: field.name not in MAGIC_FIELDS).mapped(
                'name')

            if model_portal_mixin:
                # TODO update it instead of overwrite it
                model_id.m2o_inherit_model = model_portal_mixin.id

            # self._generate_model_access(model_id, model_created_fields, model_id.m2o_module)

        return True

    def _add_dependencies(self):
        super(CodeGeneratorGeneratePortalWizard, self)._add_dependencies()
        if not self.enable_generate_portal:
            return

        for code_generator in self.code_generator_id:
            lst_dependency = ["portal"]
            lst_actual_dependency = [a.depend_id.name for a in code_generator.dependencies_id]
            for depend in lst_dependency:
                # check duplicate
                if depend in lst_actual_dependency:
                    continue
                module = self.env["ir.module.module"].search([("name", "=", depend)])
                if len(module) > 1:
                    raise Exception(f"Duplicated dependencies: {depend}")
                elif not len(module):
                    raise Exception(f"Cannot found dependency: {depend}")

                value = {
                    "module_id": code_generator.id,
                    "depend_id": module.id,
                    "name": module.display_name,
                }
                self.env["code.generator.module.dependency"].create(value)

    def generate_portal_menu_entry(self, o2m_models, module_name):
        # TODO need to find another solution than linked with the model, need to link on portal
        model_created = o2m_models[0]

        """
        <template id="portal_layout" name="Portal layout: project menu entry" inherit_id="portal.portal_breadcrumbs"
            priority="40">
            <xpath expr="//ol[hasclass('o_portal_submenu')]" position="inside">
              <li t-if="page_name == 'project' or project" t-attf-class="breadcrumb-item #{'active ' if not project else ''}">
                <a t-if="project" t-attf-href="/my/projects?{{ keep_query() }}">Projects</a>
                <t t-else="">Projects</t>
              </li>
              <li t-if="project" class="breadcrumb-item active">
                <t t-esc="project.name"/>
              </li>
              <li t-if="page_name == 'task' or task" t-attf-class="breadcrumb-item #{'active ' if not task else ''}">
                <a t-if="task" t-attf-href="/my/tasks?{{ keep_query() }}">Tasks</a>
                <t t-else="">Tasks</t>
              </li>
              <li t-if="task" class="breadcrumb-item active">
                <span t-field="task.name"/>
              </li>
            </xpath>
        </template>
        """
        qweb_name = f"Portal layout: {_fmt_title(module_name)} menu entry"
        key = f"{module_name}.portal_layout"
        priority = "40"
        inherit_id = self.env.ref("portal.portal_breadcrumbs").id
        template_id = "portal_layout"
        position = "inside"
        expr = "//ol[hasclass('o_portal_submenu')]"

        lst_menu_xml = []
        for model in o2m_models:
            # <li t-if="page_name == 'project' or project" t-attf-class="breadcrumb-item
            # #{'active ' if not project else ''}">
            menu_xml = E.li({"t-if": f"page_name == '{_fmt_underscores(model.model)}' or "
                                     f"{_fmt_underscores(model.model)}",
                             "t-attf-class": "breadcrumb-item #{'active ' if not "f"{_fmt_underscores(model.model)}"
                                             " else ''}"},
                            # <a t-if="project" t-attf-href="/my/projects?{{ keep_query() }}">Projects</a>
                            E.a({"t-if": _fmt_underscores(model.model),
                                 "t-attf-href": f"/my/{_fmt_underscores(model.model)}s?""{{ keep_query() }}"},
                                f"{_fmt_title(model.model)}s"),
                            # <t t-else="">Projects</t>
                            E.t({"t-else": ""}, f"{_fmt_title(model.model)}s")
                            )
            lst_menu_xml.append(menu_xml)
            # <li t-if="project" class="breadcrumb-item active">
            menu_xml = E.li({"t-if": _fmt_underscores(model.model), "class": "breadcrumb-item active"},
                            # <t t-esc="project.name"/>
                            E.t({"t-esc": f"{_fmt_underscores(model.model)}.name"}))
            lst_menu_xml.append(menu_xml)

        content = ET.tostring(
            # <xpath expr="//ol[hasclass('o_portal_submenu')]" position="inside">
            E.xpath({"expr": expr, "position": position}, *lst_menu_xml), pretty_print=True)

        view_value = self._create_ui_view(content, template_id, key, qweb_name, priority, inherit_id, model_created)

        return view_value

    def generate_portal_home_entry(self, o2m_models, module_name):
        model_created = o2m_models[0]

        """
      <template id="portal_my_home" name="Portal My Home: project entries" inherit_id="portal.portal_my_home" priority="40">
        <xpath expr="//div[hasclass('o_portal_docs')]" position="inside">
          <t t-if="test_model_count" t-call="portal.portal_docs_entry">
            <t t-set="title">Projects</t>
            <t t-set="url" t-value=""/>
            <t t-set="count" t-value="test_model_count"/>
          </t>
          <t t-if="test_model_2_count" t-call="portal.portal_docs_entry">
            <t t-set="title">Tasks</t>
            <t t-set="url" t-value="'/my/tasks'"/>
            <t t-set="count" t-value="test_model_2_count"/>
          </t>
        </xpath>
      </template>"""

        qweb_name = f"Portal My Home: {_fmt_title(module_name)} entries"
        key = f"{module_name}.portal_my_home"
        priority = "40"
        inherit_id = self.env.ref("portal.portal_my_home").id
        template_id = "portal_my_home"
        position = "inside"
        lst_menu_xml = []
        for model in o2m_models:
            # <t t-if="test_model_count" t-call="portal.portal_docs_entry">
            menu_xml = E.t({"t-if": f"{_fmt_underscores(model.model)}_count", "t-call": "portal.portal_docs_entry"},
                           # <t t-set="title">Projects</t>
                           E.t({"t-set": "title"}, f"{_fmt_title(model.model)}s"),
                           # <t t-set="url" t-value=""/>
                           E.t({"t-set": "url", "t-value": f"'/my/{_fmt_underscores(model.model)}s'"}),
                           # <t t-set="count" t-value="test_model_count"/>
                           E.t({"t-set": "count", "t-value": f"{_fmt_underscores(model.model)}_count"})
                           )
            lst_menu_xml.append(menu_xml)
        expr = "//div[hasclass('o_portal_docs')]"
        content = ET.tostring(
            # <xpath expr="//div[hasclass('o_portal_docs')]" position="inside">
            E.xpath({"expr": expr, "position": position}, *lst_menu_xml), pretty_print=True)

        view_value = self._create_ui_view(content, template_id, key, qweb_name, priority, inherit_id, model_created)

        return view_value

    def generate_portal_list_model(self, o2m_models, module_name):
        model_created = o2m_models[0]

        """
        <template id="portal_my_projects" name="My Projects">
            <t t-call="portal.portal_layout">
                <t t-set="breadcrumbs_searchbar" t-value="True"/>
                <t t-call="portal.portal_searchbar">
                    <t t-set="title">Projects</t>
                </t>
                <t t-if="not projects">
                    <div class="alert alert-warning mt8" role="alert">
                            There are no projects.
                        </div>
                </t>
                <t t-call="portal.portal_table" t-if="projects">
                    <tbody>
                        <tr t-as="project" t-foreach="projects">
                            <td>
                                <a t-attf-href="/my/project/#{project.id}?{{ keep_query() }}">
                                    <span t-field="project.name"/>
                                </a>
                            </td>
                            <td class="text-right">
                                <a t-attf-href="/my/tasks?{{keep_query('debug', filterby=project.id)}}">
                                    <t t-esc="project.task_count"/>
                                    <t t-esc="project.label_tasks"/>
                                </a>
                            </td>
                        </tr>
                    </tbody>
                </t>
            </t>
        </template>
        """
        lst_views = []
        for model in o2m_models:
            qweb_name = f"My {_fmt_title(model.model)}s"
            key = f"{module_name}.portal_my_{_fmt_underscores(model.model)}s"
            priority = "40"
            # inherit_id = self.env.ref("portal.portal_my_home").id

            # <t t-call="portal.portal_layout">
            root = E.t(
                {'t-call': 'portal.portal_layout'},
                # <t t-set="breadcrumbs_searchbar" t-value="True"/>
                E.t({'t-set': 'breadcrumbs_searchbar', 't-value': 'True'}),
                # <t t-call="portal.portal_searchbar">
                E.t({'t-call': 'portal.portal_searchbar'},
                    # <t t-set="title">Projects</t>
                    E.t({'t-set': 'title'}, f'{_fmt_title(model.model)}s')),
                # <t t-if="not projects">
                E.t({'t-if': f'not {_fmt_underscores(model.model)}s'},
                    # <div class="alert alert-warning mt8" role="alert">
                    E.div({'class': 'alert alert-warning mt8', 'role': 'alert'},
                          f'There are no {_fmt_underscores(model.model)}s.')),
                # <t t-call="portal.portal_table" t-if="projects">
                E.t({'t-if': f'{_fmt_underscores(model.model)}s', 't-call': 'portal.portal_table'},
                    # <tbody>
                    E.tbody({},
                            # <tr t-as="project" t-foreach="projects">
                            E.tr({'t-foreach': f'{_fmt_underscores(model.model)}s',
                                  't-as': _fmt_underscores(model.model)},
                                 # <td>
                                 E.td({},
                                      # <a t-attf-href="/my/project/#{project.id}?{{ keep_query() }}">
                                      E.a({'t-attf-href': f'/my/{_fmt_underscores(model.model)}/#''{'
                                                          f'{_fmt_underscores(model.model)}'
                                                          '.id}?{{ keep_query() }}'},
                                          # <span t-field="project.name"/>
                                          E.span({'t-field': f'{_fmt_underscores(model.model)}.name'}))),
                                 # <td class="text-right">
                                 E.td({'class': 'text-right'},
                                      # TODO DISABLE NEED BINDING BETWEEN MODELS
                                      # # <a t-attf-href="/my/tasks?{{keep_query('debug', filterby=project.id)}}">
                                      # E.a({
                                      #     't-attf-href': "/my/tasks?{{keep_query('debug', filterby="f"{_fmt_underscores(model.model)}"".id)}}"},
                                      #     # <t t-esc="project.task_count"/>
                                      #     E.t({'t-esc': 'project.task_count'}),
                                      #     # <t t-esc="project.label_tasks"/>
                                      #     E.t({'t-esc': 'project.label_tasks'}))
                                      )))))

            content = ET.tostring(root, pretty_print=True)

            view_value = self._create_ui_view(content, None, key, qweb_name, priority, None, model_created)
            lst_views.append(view_value)

        return lst_views

    def generate_portal_form_model(self, o2m_models, module_name):
        model_created = o2m_models[0]

        """
        <template id="portal_my_project" name="My Project">
            <t t-call="portal.portal_layout">
                <t groups="project.group_project_user" t-set="o_portal_fullwidth_alert">
                    <t t-call="portal.portal_back_in_edit_mode">
                        <t t-set="backend_url" t-value="'/web#return_label=Website&amp;model=project.project&amp;id=%s&amp;view_type=form' % (project.id)"/>
                    </t>
                </t>
                <t t-call="portal.portal_record_layout">
                    <t t-set="card_header">
                        <h5 class="mb-0">
                            <small class="text-muted">Project - </small>
                            <span t-field="project.name"/>
                            <span class="float-right">
                                <a class="btn btn-sm btn-secondary" role="button" t-attf-href="/my/tasks?filterby=#{project.id}">
                                    <span aria-label="Tasks" class="fa fa-tasks" role="img" title="Tasks"/>
                                    <span t-esc="project.task_count"/>
                                    <span t-field="project.label_tasks"/>
                                </a>
                            </span>
                        </h5>
                    </t>
                    <t t-set="card_body">
                        <div class="row">
                            <div class="col-12 col-md-6 mb-2 mb-md-0" t-if="project.partner_id">
                                <h6>Customer</h6>
                                <div class="row">
                                    <div class="col flex-grow-0 pr-3">
                                        <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" t-att-src="image_data_uri(project.partner_id.image)" t-if="project.partner_id.image"/>
                                        <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" src="/web/static/src/img/user_menu_avatar.png" t-else=""/>
                                    </div>
                                    <div class="col pl-sm-0">
                                        <address t-field="project.partner_id" t-options="{&quot;widget&quot;: &quot;contact&quot;, &quot;fields&quot;: [&quot;name&quot;, &quot;email&quot;, &quot;phone&quot;]}"/>
                                    </div>
                                </div>
                            </div>
                            <div class="col-12 col-md-6" t-if="project.user_id">
                                <h6>Project Manager</h6>
                                <div class="row">
                                    <div class="col flex-grow-0 pr-3">
                                        <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" t-att-src="image_data_uri(project.user_id.image)" t-if="project.user_id.image"/>
                                        <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" src="/web/static/src/img/user_menu_avatar.png" t-else=""/>
                                    </div>
                                    <div class="col pl-sm-0">
                                        <address t-field="project.user_id" t-options="{&quot;widget&quot;: &quot;contact&quot;, &quot;fields&quot;: [&quot;name&quot;, &quot;email&quot;, &quot;phone&quot;]}"/>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </t>
                </t>
            </t>
        </template>
        """
        lst_views = []
        for model in o2m_models:
            qweb_name = f"My {_fmt_title(model.model)}"
            key = f"{module_name}.portal_my_{_fmt_underscores(model.model)}"
            # priority = "40"
            # inherit_id = self.env.ref("portal.portal_my_home").id

            lst_field = _get_field_by_user(model)
            lst_card_body = []
            for field in lst_field:
                # E.div({'t-if': 'project.partner_id', 'class': 'col-12 col-md-6 mb-2 mb-md-0'},
                card_body = E.div({'class': 'col-12 col-md-6 mb-2 mb-md-0'},
                                  f"{field.field_description}-",
                                  E.span({'t-field': f"{_fmt_underscores(model.model)}.{field.name}"})
                                  )
                lst_card_body.append(card_body)

            # <t t-call="portal.portal_layout">
            root = E.t({'t-call': 'portal.portal_layout'},
                       # <t groups="project.group_project_user" t-set="o_portal_fullwidth_alert">
                       # TODO how associate group_project_user?
                       # E.t({'t-set': 'o_portal_fullwidth_alert', 'groups': 'project.group_project_user'},
                       E.t({'t-set': 'o_portal_fullwidth_alert'},
                           # <t t-call="portal.portal_back_in_edit_mode">
                           E.t({'t-call': 'portal.portal_back_in_edit_mode'},
                               # <t t-set="backend_url" t-value="'/web#return_label=Website&amp;model=project.project&amp;id=%s&amp;view_type=form' % (project.id)"/>
                               E.t({'t-set': 'backend_url',
                                    't-value': f"'/web#return_label=Website&model={module_name}.{model.model}"
                                               f"&id=%s&view_type=form' % ({_fmt_underscores(model.model)}.id)"}))),
                       # <t t-call="portal.portal_record_layout">
                       E.t({'t-call': 'portal.portal_record_layout'},
                           # <t t-set="card_header">
                           E.t({'t-set': 'card_header'},
                               # <h5 class="mb-0">
                               E.h5({'class': 'mb-0'},
                                    # <small class="text-muted">Project - </small>
                                    E.small({'class': 'text-muted'}, f'{_fmt_title(model.model)} -'),
                                    # <span t-field="project.name"/>
                                    E.span({'t-field': f'{_fmt_underscores(model.model)}.name'})
                                    # TODO need binding variable
                                    # ,
                                    # # <span class="float-right">
                                    # E.span({'class': 'float-right'},
                                    #        # <a class="btn btn-sm btn-secondary" role="button" t-attf-href="/my/tasks?filterby=#{project.id}">
                                    #        E.a({'role': 'button', 't-attf-href': '/my/tasks?filterby=#{'f'{_fmt_underscores(model.model)}''.id}',
                                    #             'class': 'btn btn-sm btn-secondary'},
                                    #            # <span aria-label="Tasks" class="fa fa-tasks" role="img" title="Tasks"/>
                                    #            E.span({'class': 'fa fa-tasks', 'role': 'img', 'aria-label': 'Tasks',
                                    #                    'title': 'Tasks'}),
                                    #            # <span t-esc="project.task_count"/>
                                    #            E.span({'t-esc': f'{_fmt_underscores(model.model)}.task_count'}),
                                    #            # <span t-field="project.label_tasks"/>
                                    #            E.span({'t-field': f'{_fmt_underscores(model.model)}.label_tasks'})))
                                    )),
                           # TODO added mathben
                           E.t({'t-set': 'card_body'},
                               E.div({'class': 'row'},
                                     *lst_card_body
                                     )
                               )
                           # TODO support card_body later
                           # # <t t-set="card_body">
                           # E.t({'t-set': 'card_body'},
                           #     # <div class="row">
                           #     E.div({'class': 'row'},
                           #           # <div class="col-12 col-md-6 mb-2 mb-md-0" t-if="project.partner_id">
                           #           E.div({'t-if': 'project.partner_id', 'class': 'col-12 col-md-6 mb-2 mb-md-0'},
                           #                 # <h6>Customer</h6>
                           #                 E.h6({}, 'Customer'),
                           #                 # <div class="row">
                           #                 E.div({'class': 'row'},
                           #                       # <div class="col flex-grow-0 pr-3">
                           #                       E.div({'class': 'col flex-grow-0 pr-3'},
                           #                             # <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" t-att-src="image_data_uri(project.partner_id.image)" t-if="project.partner_id.image"/>
                           #                             E.img({'t-if': 'project.partner_id.image',
                           #                                    'class': 'rounded-circle mt-1 o_portal_contact_img',
                           #                                    't-att-src': 'image_data_uri(project.partner_id.image)',
                           #                                    'alt': 'Contact'}),
                           #                             # <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" src="/web/static/src/img/user_menu_avatar.png" t-else=""/>
                           #                             E.img({'t-else': '',
                           #                                    'class': 'rounded-circle mt-1 o_portal_contact_img',
                           #                                    'src': '/web/static/src/img/user_menu_avatar.png',
                           #                                    'alt': 'Contact'})),
                           #                       # <div class="col pl-sm-0">
                           #                       E.div({'class': 'col pl-sm-0'},
                           #                             # <address t-field="project.partner_id" t-options="{&quot;widget&quot;: &quot;contact&quot;, &quot;fields&quot;: [&quot;name&quot;, &quot;email&quot;, &quot;phone&quot;]}"/>
                           #                             E.address({'t-field': 'project.partner_id',
                           #                                        't-options': '{"widget": "contact", "fields": ["name", "email", "phone"]}'})))),
                           #           # <div class="col-12 col-md-6" t-if="project.user_id">
                           #           E.div({'t-if': 'project.user_id', 'class': 'col-12 col-md-6'},
                           #                 # <h6>Project Manager</h6>
                           #                 E.h6({}, 'Project Manager'),
                           #                 # <div class="row">
                           #                 E.div({'class': 'row'},
                           #                       # <div class="col flex-grow-0 pr-3">
                           #                       E.div({'class': 'col flex-grow-0 pr-3'},
                           #                             # <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" t-att-src="image_data_uri(project.user_id.image)" t-if="project.user_id.image"/>
                           #                             E.img({'t-if': 'project.user_id.image',
                           #                                    'class': 'rounded-circle mt-1 o_portal_contact_img',
                           #                                    't-att-src': 'image_data_uri(project.user_id.image)',
                           #                                    'alt': 'Contact'}),
                           #                             # <img alt="Contact" class="rounded-circle mt-1 o_portal_contact_img" src="/web/static/src/img/user_menu_avatar.png" t-else=""/>
                           #                             E.img({'t-else': '',
                           #                                    'class': 'rounded-circle mt-1 o_portal_contact_img',
                           #                                    'src': '/web/static/src/img/user_menu_avatar.png',
                           #                                    'alt': 'Contact'})),
                           #                       # <div class="col pl-sm-0">
                           #                       E.div({'class': 'col pl-sm-0'},
                           #                             # <address t-field="project.user_id" t-options="{&quot;widget&quot;: &quot;contact&quot;, &quot;fields&quot;: [&quot;name&quot;, &quot;email&quot;, &quot;phone&quot;]}"/>
                           #                             E.address({'t-field': 'project.user_id',
                           #                                        't-options': '{"widget": "contact", "fields": ["name", "email", "phone"]}'}))))))
                           ))

            content = ET.tostring(root, pretty_print=True)

            view_value = self._create_ui_view(content, None, key, qweb_name, None, None, model_created)
            lst_views.append(view_value)

        return lst_views

    def _create_ui_view(self, content, template_id, key, qweb_name, priority, inherit_id, model_created):
        content = content.strip()
        value = {
            # 'id': template_id,
            'key': key,
            'name': qweb_name,
            'type': 'qweb',
            'arch': content,
            # TODO model and m2o_model are not suppose to here, only to link with code_generator
            # TODO find a new way to implement it without using 'model', else _get_models_info of code_generator
            # TODO cannot detect it
            'model': model_created.model,
            'm2o_model': model_created.id,
        }
        if priority:
            value['priority'] = priority
        if inherit_id:
            value['inherit_id'] = inherit_id

        view_value = self.env['ir.ui.view'].create(value)
        return view_value

    def _generate_model_access(self, model_created, model_created_fields, module):
        if self.enable_generate_all or self.enable_generate_portal:
            # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
            # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
            lang = "en_US"
            group_id = self.env.ref('base.group_portal').with_context(lang=lang)
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

        super(CodeGeneratorGeneratePortalWizard, self)._generate_model_access(model_created, model_created_fields,
                                                                              module)
