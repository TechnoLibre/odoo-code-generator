import logging
import uuid

from lxml import etree as ET
from lxml.builder import E

from odoo import _, api, fields, models
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]


def _fmt_underscores(word):
    return word.lower().replace(".", "_")


def _fmt_camel(word):
    return word.replace(".", "_").title().replace("_", "")


def _fmt_title(word):
    return word.replace(".", " ").title()


def _get_field_by_user(model_id, keep_name=False):
    lst_field = []
    lst_first_field = []
    lst_second_field = []
    if keep_name:
        lst_magic_fields = MAGIC_FIELDS
    else:
        lst_magic_fields = MAGIC_FIELDS + ["name"]
    for field_id in model_id.field_id:
        if field_id.name not in lst_magic_fields:
            if field_id.name == "name":
                lst_first_field.append(field_id)
            elif field_id.name == "email":
                lst_second_field.append(field_id)
            else:
                lst_field.append(field_id)
    return lst_first_field + lst_second_field + lst_field


class CodeGeneratorGeneratePortalWizard(models.TransientModel):
    _inherit = "code.generator.generate.views.wizard"

    selected_model_portal_ids = fields.Many2many(comodel_name="ir.model")

    enable_generate_portal = fields.Boolean(
        string="Enable portal feature",
        default=False,
        help=(
            "This variable need to be True to generate portal if"
            " enable_generate_all is False"
        ),
    )

    portal_enable_create = fields.Boolean(
        string="Enable portal creation",
        default=False,
        help="This will activate create form for all model.",
    )

    @api.multi
    def button_generate_views(self):
        status = super(
            CodeGeneratorGeneratePortalWizard, self
        ).button_generate_views()
        if not status or (
            not self.enable_generate_all and not self.enable_generate_portal
        ):
            self.code_generator_id.enable_generate_portal = False
            return status

        if self.portal_enable_create:
            self.code_generator_id.portal_enable_create = True

        self.code_generator_id.enable_generate_portal = True

        o2m_models = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_ids
        )
        self.generate_portal_menu_entry(
            o2m_models, self.code_generator_id.name
        )
        self.generate_portal_home_entry(
            o2m_models, self.code_generator_id.name
        )
        self.generate_portal_list_model(
            o2m_models, self.code_generator_id.name
        )
        self.generate_portal_form_model(
            o2m_models, self.code_generator_id.name
        )
        if self.portal_enable_create:
            self.generate_portal_create_model(
                o2m_models, self.code_generator_id.name
            )

        o2m_models.add_model_inherit("portal.mixin")

        # Add portal code
        self._add_portal_python_code(o2m_models)

        return True

    def _add_dependencies(self):
        super(CodeGeneratorGeneratePortalWizard, self)._add_dependencies()
        if not self.enable_generate_all and not self.enable_generate_portal:
            return

        self.code_generator_id.add_module_dependency("portal")

    @staticmethod
    def _get_l_map(fn, collection):
        """
        Util function to get a list of a map operation
        :param fn:
        :param collection:
        :return:
        """

        return list(map(fn, collection))

    def _get_class_name(self, model):
        """
        Util function to get a model class name representation from a model name (code.generator -> CodeGenerator)
        :param model:
        :return:
        """

        # TODO move this method in ir.model
        result = []
        bypoint = model.split(".")
        for byp in bypoint:
            result += byp.split("_")
        return "".join(self._get_l_map(lambda e: e.capitalize(), result))

    def _add_portal_python_code(self, o2m_models):
        lst_code = []
        for model_id in o2m_models:
            method_name = "_compute_access_url"
            actual_code = self.env["code.generator.model.code"].search(
                [
                    ("m2o_module", "=", self.code_generator_id.id),
                    ("m2o_model", "=", model_id.id),
                    ("name", "=", method_name),
                ]
            )
            if actual_code:
                continue
            var_name = model_id.model.replace(".", "_")
            str_code = f"""super({self._get_class_name(model_id.model)}, self)._compute_access_url()
for {var_name} in self:
    {var_name}.access_url = '/my/{var_name}/%s' % {var_name}.id
            """
            dct_code = {
                "code": str_code,
                "name": method_name,
                "param": "self",
                # "sequence": 1,
                "m2o_module": self.code_generator_id.id,
                "m2o_model": model_id.id,
            }
            lst_code.append(dct_code)
        self.env["code.generator.model.code"].create(lst_code)

    def generate_portal_menu_entry(self, o2m_models, module_name):
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
        position = "inside"
        expr = "//ol[hasclass('o_portal_submenu')]"

        lst_menu_xml = []
        for model in o2m_models:
            # <li t-if="page_name == 'project' or project" t-attf-class="breadcrumb-item
            # #{'active ' if not project else ''}">
            t_if_condition = _fmt_underscores(model.model)
            if self.portal_enable_create:
                page_name_condition = (
                    f"page_name in ('{_fmt_underscores(model.model)}',"
                    f" 'create_{_fmt_underscores(model.model)}') or"
                    f" {_fmt_underscores(model.model)}"
                )
                t_if_condition += (
                    " or page_name =="
                    f" 'create_{_fmt_underscores(model.model)}'"
                )
            else:
                page_name_condition = (
                    f"page_name == '{_fmt_underscores(model.model)}' or "
                    f"{_fmt_underscores(model.model)}"
                )

            menu_xml = E.li(
                {
                    "t-if": page_name_condition,
                    "t-attf-class": (
                        "breadcrumb-item #{'active ' if not "
                        f"{_fmt_underscores(model.model)}"
                        " else ''}"
                    ),
                },
                # <a t-if="project" t-attf-href="/my/projects?{{ keep_query() }}">Projects</a>
                E.a(
                    {
                        "t-if": t_if_condition,
                        "t-attf-href": (
                            f"/my/{_fmt_underscores(model.model)}s?"
                            "{{ keep_query() }}"
                        ),
                    },
                    f"{_fmt_title(model.model)}s",
                ),
                # <t t-else="">Projects</t>
                E.t({"t-else": ""}, f"{_fmt_title(model.model)}s"),
            )
            lst_menu_xml.append(menu_xml)
            # <li t-if="project" class="breadcrumb-item active">

            menu_xml = E.li(
                {
                    "t-if": _fmt_underscores(model.model),
                    "class": "breadcrumb-item active",
                },
                # <t t-esc="project.name"/>
                E.t(
                    {
                        "t-esc": (
                            f"{_fmt_underscores(model.model)}.{model.rec_name}"
                        )
                    }
                ),
            )
            lst_menu_xml.append(menu_xml)

        content = ET.tostring(
            # <xpath expr="//ol[hasclass('o_portal_submenu')]" position="inside">
            E.xpath({"expr": expr, "position": position}, *lst_menu_xml),
            pretty_print=True,
        )

        view_value = self._create_ui_view(
            content,
            key,
            qweb_name,
            priority,
            inherit_id,
            model_created,
        )

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
        position = "inside"
        lst_menu_xml = []
        for model in o2m_models:
            # <t t-if="test_model_count" t-call="portal.portal_docs_entry">
            menu_xml = E.t(
                {
                    "t-if": f"{_fmt_underscores(model.model)}_count",
                    "t-call": "portal.portal_docs_entry",
                },
                # <t t-set="title">Projects</t>
                E.t({"t-set": "title"}, f"{_fmt_title(model.model)}s"),
                # <t t-set="url" t-value=""/>
                E.t(
                    {
                        "t-set": "url",
                        "t-value": f"'/my/{_fmt_underscores(model.model)}s'",
                    }
                ),
                # <t t-set="count" t-value="test_model_count"/>
                E.t(
                    {
                        "t-set": "count",
                        "t-value": f"{_fmt_underscores(model.model)}_count",
                    }
                ),
            )
            lst_menu_xml.append(menu_xml)
            if self.portal_enable_create:
                button_menu_xml = E.a(
                    {
                        "t-if": f"not {_fmt_underscores(model.model)}_count",
                        "role": "button",
                        "class": "btn btn-primary btn-block mb8",
                        "href": f"/new/{_fmt_underscores(model.model)}",
                    },
                    E.i({"class": "fa fa-plus-circle"}),
                    _fmt_title(model.model),
                )
                lst_menu_xml.append(button_menu_xml)
        expr = "//div[hasclass('o_portal_docs')]"
        content = ET.tostring(
            # <xpath expr="//div[hasclass('o_portal_docs')]" position="inside">
            E.xpath({"expr": expr, "position": position}, *lst_menu_xml),
            pretty_print=True,
        )

        view_value = self._create_ui_view(
            content,
            key,
            qweb_name,
            priority,
            inherit_id,
            model_created,
        )

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

            lst_item_portal = []

            # <t t-set="breadcrumbs_searchbar" t-value="True"/>
            lst_item_portal.append(
                E.t({"t-set": "breadcrumbs_searchbar", "t-value": "True"})
            )
            # <t t-call="portal.portal_searchbar">
            lst_item_portal.append(
                E.t(
                    {"t-call": "portal.portal_searchbar"},
                    # <t t-set="title">Projects</t>
                    E.t({"t-set": "title"}, f"{_fmt_title(model.model)}s"),
                )
            )

            if self.portal_enable_create:
                # <form method="POST" t-attf-action="/new/ticket">
                lst_item_portal.append(
                    E.form(
                        {
                            "method": "POST",
                            "t-attf-action": (
                                f"/new/{_fmt_underscores(model.model)}"
                            ),
                        },
                        # <button name="create_new_ticket" type="action" class="btn btn-primary" groups="base.group_portal" style="float: right; margin-right: 5px;">New Ticket</button>
                        E.button(
                            {
                                "name": f"create_new_{_fmt_underscores(model.model)}",
                                "type": "action",
                                "class": "btn btn-primary",
                                # "groups": "base.group_portal",
                                "style": "float: right; margin-right: 5px;",
                            },
                            f"New {_fmt_title(model.model)}",
                        ),
                        # <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                        E.input(
                            {
                                "type": "hidden",
                                "name": "csrf_token",
                                "t-att-value": "request.csrf_token()",
                            }
                        ),
                    )
                )

            # <t t-if="not projects">
            lst_item_portal.append(
                E.t(
                    {"t-if": f"not {_fmt_underscores(model.model)}s"},
                    # <div class="alert alert-warning mt8" role="alert">
                    E.div(
                        {"class": "alert alert-warning mt8", "role": "alert"},
                        f"There are no {_fmt_underscores(model.model)}s.",
                    ),
                )
            )
            # <t t-call="portal.portal_table" t-if="projects">
            lst_item_portal.append(
                E.t(
                    {
                        "t-if": f"{_fmt_underscores(model.model)}s",
                        "t-call": "portal.portal_table",
                    },
                    # <tbody>
                    E.tbody(
                        {},
                        # <tr t-as="project" t-foreach="projects">
                        E.tr(
                            {
                                "t-foreach": (
                                    f"{_fmt_underscores(model.model)}s"
                                ),
                                "t-as": _fmt_underscores(model.model),
                            },
                            # <td>
                            E.td(
                                {},
                                # <a t-attf-href="/my/project/#{project.id}?{{ keep_query() }}">
                                E.a(
                                    {
                                        "t-attf-href": (
                                            f"/my/{_fmt_underscores(model.model)}/#{{{_fmt_underscores(model.model)}.id}}?{{{{"
                                            " keep_query() }}"
                                        )
                                    },
                                    # <span t-field="project.name"/>
                                    E.span(
                                        {
                                            "t-field": f"{_fmt_underscores(model.model)}.{model.rec_name}"
                                        }
                                    ),
                                ),
                            ),
                            # <td class="text-right">
                            E.td(
                                {"class": "text-right"},
                                # TODO DISABLE NEED BINDING BETWEEN MODELS
                                # # <a t-attf-href="/my/tasks?{{keep_query('debug', filterby=project.id)}}">
                                # E.a({
                                #     't-attf-href': "/my/tasks?{{keep_query('debug', filterby="f"{_fmt_underscores(model.model)}"".id)}}"},
                                #     # <t t-esc="project.task_count"/>
                                #     E.t({'t-esc': 'project.task_count'}),
                                #     # <t t-esc="project.label_tasks"/>
                                #     E.t({'t-esc': 'project.label_tasks'}))
                            ),
                        ),
                    ),
                )
            )

            # <t t-call="portal.portal_layout">
            root = E.t({"t-call": "portal.portal_layout"}, *lst_item_portal)

            content = ET.tostring(root, pretty_print=True)

            view_value = self._create_ui_view(
                content, key, qweb_name, priority, None, model_created
            )
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
            lst_card_body_begin = []
            lst_card_body_end = []
            for field in lst_field:
                if field.ignore_on_code_generator_writer:
                    continue
                # E.div({'t-if': 'project.partner_id', 'class': 'col-12 col-md-6 mb-2 mb-md-0'},

                # TODO this fix missing association relation and relation_id (to create) to replace related_field_data_model
                # if field.relation and not field.relation_table:
                if field.relation:
                    related_field_data_model = self.env["ir.model"].search(
                        [("model", "=", field.relation)]
                    )
                else:
                    related_field_data_model = None

                # TODO this fix missing association relation_field with relation_field_id
                if field.relation_field and not field.relation_field_id:
                    if not field.relation:
                        _logger.error(
                            "Missing in a record for ir.model.fields the"
                            " field relation, but relation_field contains"
                            f" '{field.relation_field}' ."
                        )
                    else:
                        field.relation_field_id = (
                            self.env["ir.model.fields"]
                            .search(
                                [
                                    ("model", "=", field.relation),
                                    ("name", "=", field.relation_field),
                                ]
                            )
                            .id
                        )

                str_field_data = (
                    f"{_fmt_underscores(model.model)}.{field.name}"
                )
                if field.ttype == "one2many":
                    if field.force_widget:
                        _logger.warning(
                            "Cannot support `force_widget` in portal from"
                            f" one2many for field {field.name}."
                        )

                    lst_field_name_xml = []
                    lst_field_variable_xml = []
                    lst_field_to_compute = _get_field_by_user(
                        field.relation_field_id.model_id, keep_name=True
                    )
                    for no_id, field_id in enumerate(lst_field_to_compute):
                        if field_id.relation:
                            related_field_id_data_model = self.env[
                                "ir.model"
                            ].search([("model", "=", field_id.relation)])
                        else:
                            related_field_id_data_model = None

                        if field_id.ignore_on_code_generator_writer:
                            continue

                        # TODO add class="text-right" when force_widget with time

                        field_id_value_name = f"{field.name}.{field_id.name}"

                        if field_id.ttype == "html":
                            t_field_id_show_data = "t-raw"
                        else:
                            t_field_id_show_data = "t-esc"

                        field_id_value_xml = None

                        if field_id.ttype == "many2one":
                            # TODO ignore link when it's the same page? field_id.relation == field.model_id.model
                            #  and same id... No, need some Javascript, cannot do that here
                            field_id_value_xml = E.a(
                                {
                                    "t-attf-href": f"/my/{_fmt_underscores(field_id.relation)}/#{{{field_id_value_name}.id}}",
                                    "t-field": f"{field_id_value_name}.{related_field_id_data_model.rec_name}",
                                }
                            )
                        elif field_id.ttype in ("many2many", "one2many"):
                            var_rec_name = self.env[
                                field_id.relation
                            ]._rec_name
                            # TODO can be in conflict, if a field_id.name is item, or field_id.name[3:] exist
                            sub_name_var = (
                                field_id.name[:3]
                                if len(field_id.name) > 3
                                else "item"
                            )

                            field_id_value_xml = E.t(
                                {
                                    "t-foreach": f"{field_id_value_name}",
                                    "t-as": sub_name_var,
                                },
                                E.a(
                                    {
                                        "t-attf-href": f"/my/{_fmt_underscores(field_id.relation)}/#{{{sub_name_var}.id}}",
                                        "t-field": (
                                            f"{sub_name_var}.{var_rec_name}"
                                        ),
                                    },
                                ),
                                E.br({"t-if": f"not {sub_name_var}_last"}),
                            )
                        elif field_id.name == "name":
                            field_id_value_xml = E.a(
                                {
                                    "t-attf-href": f"/my/{_fmt_underscores(field_id.model_id.model)}/#{{{field.name}.id}}",
                                    "t-field": f"{field_id_value_name}",
                                }
                            )
                        elif field_id.force_widget:
                            if field_id.force_widget == "image":
                                field_id_value_xml = E.img(
                                    {
                                        "t-if": field_id_value_name,
                                        "t-att-src": f"image_data_uri({field_id_value_name})",
                                        "alt": field_id.name,
                                        "class": (
                                            "img img-fluid d-block mx-auto"
                                        ),
                                    }
                                )
                            elif field_id.force_widget == "link_button":
                                field_id_value_xml = E.a(
                                    {
                                        "target": "_blank",
                                        "t-attf-href": (
                                            f"{{{{{field_id_value_name}}}}}"
                                        ),
                                        "t-field": field_id_value_name,
                                    }
                                )
                            elif field_id.force_widget == "float_time":
                                field_id_value_xml = E.span(
                                    {
                                        "t-field": field_id_value_name,
                                        "t-options": (
                                            '{"widget": "duration", "unit":'
                                            ' "hour", "round": "minute"}'
                                        ),
                                    }
                                )
                            else:
                                _logger.warning(
                                    "Cannot support `force_widget`"
                                    f" {field_id.force_widget} in portal"
                                    " inside one2many for field"
                                    f" {field_id.name}."
                                )
                        else:
                            field_id_value_xml = E.t(
                                {t_field_id_show_data: field_id_value_name}
                            )

                        if field_id_value_xml is None:
                            _logger.warning(
                                f"Not supported, field {field_id.name}"
                            )
                        else:
                            column_xml = E.th({}, field_id.field_description)
                            lst_field_name_xml.append(column_xml)
                            data_column_xml = E.td({}, field_id_value_xml)
                            lst_field_variable_xml.append(data_column_xml)

                    card_body = E.div(
                        {"class": "container", "t-if": str_field_data},
                        # <hr class="mt-4 mb-1"/>
                        E.hr({"class": "mt-4 mb-1"}),
                        # <h5 class="mt-2 mb-2">Timesheets</h5>
                        E.h5(
                            {"class": "mt-2 mb-2"},
                            field.field_description,
                        ),
                        # <table class="table table-sm">
                        E.table(
                            {"class": "table table-sm"},
                            # <thead>
                            E.thead(
                                {},
                                # <tr>
                                E.tr(
                                    {},
                                    *lst_field_name_xml,
                                    # <tr t-as="timesheet" t-foreach="task.timesheet_ids">
                                ),
                            ),
                            E.tr(
                                {
                                    "t-foreach": f"{_fmt_underscores(model.model)}.{field.name}",
                                    "t-as": field.name,
                                },
                                *lst_field_variable_xml,
                            ),
                        ),
                    )
                    lst_card_body_end.append(card_body)
                elif field.ttype == "many2many":
                    var_rec_name = self.env[field.relation]._rec_name
                    # TODO can be in conflict, if a field.name is item, or field.name[3:] exist
                    sub_name_var = (
                        field.name[:3] if len(field.name) > 3 else "item"
                    )

                    xml_field_data = E.t(
                        {
                            "t-foreach": str_field_data,
                            "t-as": sub_name_var,
                        },
                        E.a(
                            {
                                "t-attf-href": f"/my/{_fmt_underscores(field.relation)}/#{{{sub_name_var}.id}}",
                                "t-field": f"{sub_name_var}.{var_rec_name}",
                            },
                        ),
                        E.t({"t-if": f"not {sub_name_var}_last"}, ","),
                    )
                    if xml_field_data is not None:
                        card_body = E.div(
                            {"class": "col-12 col-md-6 mb-2 mb-md-0"},
                            E.b({}, f"{field.field_description}:"),
                            xml_field_data,
                        )
                        lst_card_body_begin.append(card_body)
                else:
                    xml_field_data = None
                    if field.ttype in ("many2one",):
                        xml_field_data = E.a(
                            {
                                "t-attf-href": f"/my/{_fmt_underscores(field.relation)}/#{{{str_field_data}.id}}",
                                "t-field": f"{str_field_data}.{related_field_data_model.rec_name}",
                            }
                        )
                    elif field.force_widget:
                        if field.force_widget == "image":
                            xml_field_data = E.img(
                                {
                                    "t-if": str_field_data,
                                    "t-att-src": (
                                        f"image_data_uri({str_field_data})"
                                    ),
                                    "alt": field.name,
                                    "class": "img img-fluid d-block mx-auto",
                                }
                            )
                        elif field.force_widget == "link_button":
                            xml_field_data = E.a(
                                {
                                    "target": "_blank",
                                    "t-attf-href": f"{{{{{str_field_data}}}}}",
                                    "t-field": str_field_data,
                                }
                            )
                        elif field.force_widget == "float_time":
                            xml_field_data = E.span(
                                {
                                    "t-field": str_field_data,
                                    "t-options": (
                                        '{"widget": "duration", "unit":'
                                        ' "hour", "round": "minute"}'
                                    ),
                                }
                            )
                        else:
                            _logger.warning(
                                "Cannot support `force_widget`"
                                f" {field.force_widget} in portal for field"
                                f" {field.name}."
                            )
                    else:
                        if field.ttype == "html":
                            t_show_data = "t-raw"
                        else:
                            t_show_data = "t-field"
                        xml_field_data = E.span({t_show_data: str_field_data})

                    if xml_field_data is not None:
                        card_body = E.div(
                            {"class": "col-12 col-md-6 mb-2 mb-md-0"},
                            E.b({}, f"{field.field_description}:"),
                            xml_field_data,
                        )
                        lst_card_body_begin.append(card_body)

            lst_card_body = lst_card_body_begin + lst_card_body_end
            lst_message_xml = []
            if model.enable_activity:
                msg_xml = E.div(
                    {"class": "mt32"},
                    E.h4(
                        {}, E.strong({}, "Message and communication history")
                    ),
                    E.t(
                        {"t-call": "portal.message_thread"},
                        E.t(
                            {
                                "t-set": "object",
                                "t-value": _fmt_underscores(model.model),
                            }
                        ),
                        E.t(
                            {
                                "t-set": "token",
                                "t-value": f"{_fmt_underscores(model.model)}.access_token",
                            }
                        ),
                        E.t({"t-set": "pid", "t-value": "pid"}),
                        E.t({"t-set": "hask", "t-value": "hash"}),
                    ),
                )
                lst_message_xml.append(msg_xml)
            # <t t-call="portal.portal_layout">
            root = E.t(
                {"t-call": "portal.portal_layout"},
                # <t groups="project.group_project_user" t-set="o_portal_fullwidth_alert">
                # TODO how associate group_project_user?
                # E.t({'t-set': 'o_portal_fullwidth_alert', 'groups': 'project.group_project_user'},
                E.t(
                    {"t-set": "o_portal_fullwidth_alert"},
                    # <t t-call="portal.portal_back_in_edit_mode">
                    E.t(
                        {"t-call": "portal.portal_back_in_edit_mode"},
                        # <t t-set="backend_url" t-value="'/web#return_label=Website&amp;model=project.project&amp;id=%s&amp;view_type=form' % (project.id)"/>
                        E.t(
                            {
                                "t-set": "backend_url",
                                "t-value": (
                                    f"'/web#return_label=Website&model={model.model}&id=%s&view_type=form'"
                                    f" % ({_fmt_underscores(model.model)}.id)"
                                ),
                            }
                        ),
                    ),
                ),
                # <t t-call="portal.portal_record_layout">
                E.t(
                    {"t-call": "portal.portal_record_layout"},
                    # <t t-set="card_header">
                    E.t(
                        {"t-set": "card_header"},
                        # <h5 class="mb-0">
                        E.h5(
                            {"class": "mb-0"},
                            # <small class="text-muted">Project - </small>
                            E.small(
                                {"class": "text-muted"},
                                f"{_fmt_title(model.model)} -",
                            ),
                            # <span t-field="project.name"/>
                            E.span(
                                {
                                    "t-field": f"{_fmt_underscores(model.model)}.{model.rec_name}"
                                }
                            )
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
                        ),
                    ),
                    # TODO added mathben
                    E.t(
                        {"t-set": "card_body"},
                        E.div({"class": "row"}, *lst_card_body),
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
                ),
                *lst_message_xml,
            )

            content = ET.tostring(root, pretty_print=True)

            view_value = self._create_ui_view(
                content, key, qweb_name, None, None, model_created
            )
            lst_views.append(view_value)

        return lst_views

    def generate_portal_create_model(self, o2m_models, module_name):
        model_created = o2m_models[0]
        dct_replace = {}

        """
          <template id="portal_create_ticket" name="Create Ticket">
            <t t-call="portal.portal_layout">
              <div class="container">
                <div class="row">
                  <div class="col-md-12">
                    <h1 class="text-center">Send a new ticket</h1>
                  </div>
                </div>
              </div>

              <form action="/submitted/ticket" method="POST" class="form-horizontal mt32" enctype="multipart/form-data">
                <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                <div class="form-group">
                  <label class="col-md-3 col-sm-4 control-label" for="name">Name</label>
                  <div class="col-md-7 col-sm-8">
                    <input type="text" class="form-control" name="name" t-attf-value="#{name}" required="True"/>
                  </div>
                </div>
                <div class="form-group">
                  <label class="col-md-3 col-sm-4 control-label" for="email">Email</label>
                  <div class="col-md-7 col-sm-8">
                    <input type="email" class="form-control" name="email" required="True" t-attf-value="#{email}" readonly="True" />
                  </div>
                </div>
                <div class="form-group">
                  <label class="col-md-3 col-sm-4 control-label" for="category">Category</label>
                  <div class="col-md-7 col-sm-8">
                    <select class="form-control" id="category" name="category" required="True">
                      <t t-foreach="categories" t-as="cat">
                        <option t-attf-value="#{cat.id}"><t t-esc="cat.name"/></option>
                      </t>
                    </select>
                  </div>
                </div>
                <div class="form-group">
                  <label class="col-md-3 col-sm-4 control-label" for="subject">Subject</label>
                  <div class="col-md-7 col-sm-8">
                    <input type="text" class="form-control" name="subject" required="True"/>
                  </div>
                </div>
                <div class="form-group">
                  <label class="col-md-3 col-sm-4 control-label" for="attachment">Add Attachments</label>
                  <div class="col-md-7 col-sm-8">
                      <div class="btn btn-default btn-file col-md-12"><input class="form-control o_website_form_input" name="attachment" id="attachment" type="file" multiple="multiple"/></div>
                  </div>
                </div>
                <div class="form-group">
                  <label class="col-md-3 col-dm-4 control-label" for="description">Description</label>
                  <div class="col-md-7 col-sm-8">
                    <textarea class="form-control" name="description" style="min-height: 120px" required="True"></textarea>
                  </div>
                </div>
                <div class="form-group">
                  <div class="col-md-offset-3 col-sm-offset-4 col-sm-8 col-md-7">
                    <button class="btn btn-primary btn-lg">Submit Ticket</button>
                  </div>
                </div>
              </form>
            </t>
          </template>
        """
        lst_views = []
        for model_id in o2m_models:
            qweb_name = f"Create {_fmt_title(model_id.model)}"
            key = f"portal_create_{_fmt_underscores(model_id.model)}"
            # priority = "40"
            # inherit_id = self.env.ref("portal.portal_my_home").id

            lst_field = _get_field_by_user(model_id, keep_name=True)
            lst_item_form = []

            item_xml = E.input(
                {
                    "type": "hidden",
                    "name": "csrf_token",
                    "t-att-value": "request.csrf_token()",
                }
            )
            lst_item_form.append(item_xml)

            # Bind model field
            lst_data_field_name = ["name", "email"]
            for field_id in lst_field:
                sub_item = None
                if field_id.ignore_on_code_generator_writer:
                    continue
                if field_id.ttype == "char":
                    dct_sub_item = {
                        "type": "text",
                        "class": "form-control",
                        "name": field_id.name,
                    }

                    if field_id.name in lst_data_field_name:
                        dct_sub_item["t-attf-value"] = (
                            "#{" + field_id.name + "}"
                        )
                    else:
                        dct_sub_item[
                            "t-att-value"
                        ] = f"default_{field_id.name}"

                    if field_id.required:
                        dct_sub_item["required"] = "True"

                    if field_id.readonly:
                        dct_sub_item["readonly"] = "True"

                    sub_item = E.input(dct_sub_item)
                elif field_id.ttype in ("text", "html"):
                    dct_sub_item = {
                        "class": "form-control",
                        "name": field_id.name,
                        "style": "min-height: 120px",
                    }

                    if field_id.name in lst_data_field_name:
                        default_value = "#{" + field_id.name + "}"
                    else:
                        default_value = f"default_{field_id.name}"

                    if field_id.required:
                        dct_sub_item["required"] = "True"

                    if field_id.readonly:
                        dct_sub_item["readonly"] = "True"

                    sub_item = E.textarea(
                        dct_sub_item, E.t({"t-esc": default_value})
                    )
                    str_to_replace = ET.tostring(sub_item)
                    # Don't format textarea, because it's added space in value
                    str_uuid = str(uuid.uuid4())
                    dct_replace[str_uuid.encode()] = str_to_replace
                    sub_item = str_uuid
                elif field_id.ttype == "binary":
                    dct_sub_item = {
                        "class": "form-control o_website_form_input",
                        "id": field_id.name,
                        # "multiple": "multiple",
                        "name": field_id.name,
                        "type": "file",
                    }

                    if field_id.required:
                        dct_sub_item["required"] = "True"

                    sub_item = E.div(
                        {"class": "btn btn-default btn-file col-md-12"},
                        E.input(dct_sub_item),
                    )
                elif field_id.ttype in ("many2one",):
                    var_rec_name = self.env[field_id.relation]._rec_name

                    dct_select_attr = {
                        "class": "form-control",
                        "id": field_id.name,
                        "name": field_id.name,
                    }

                    if field_id.required:
                        dct_select_attr["required"] = "True"

                    # TODO can be in conflict, if a field_id.name is item, or field_id.name[3:] exist
                    sub_name_var = (
                        field_id.name[:3] if len(field_id.name) > 3 else "item"
                    )

                    sub_item = E.select(
                        dct_select_attr,
                        E.t(
                            {"t-foreach": field_id.name, "t-as": sub_name_var},
                            E.option(
                                {
                                    "t-attf-value": f"#{{{sub_name_var}.id}}",
                                    "t-att-selected": (
                                        f"default_{field_id.name} =="
                                        f" {sub_name_var}.id"
                                    ),
                                },
                                E.t(
                                    {"t-esc": f"{sub_name_var}.{var_rec_name}"}
                                ),
                            ),
                        ),
                    )
                elif field_id.ttype == "one2many":
                    pass
                elif field_id.ttype in (
                    "many2many",
                    # "one2many"
                ):
                    # TODO enable one2many when support in submitted
                    var_rec_name = self.env[field_id.relation]._rec_name
                    # TODO can be in conflict, if a field_id.name is item, or field_id.name[3:] exist
                    sub_name_var = (
                        field_id.name[:3] if len(field_id.name) > 3 else "item"
                    )

                    dct_input_attr = {
                        "type": "checkbox",
                        "name": field_id.name,
                        "t-att-id": (
                            f"'{field_id.name}_' +"
                            f" {sub_name_var}.{var_rec_name} + '_' +"
                            f" str({sub_name_var}_index)"
                        ),
                        "t-att-value": f"{sub_name_var}.id",
                        "t-att-checked": (
                            f"{sub_name_var}.id in default_{field_id.name}"
                        ),
                    }

                    if field_id.required:
                        dct_input_attr["required"] = "required"

                    sub_item = E.t(
                        {"t-foreach": field_id.name, "t-as": sub_name_var},
                        E.input(dct_input_attr),
                        E.label(
                            {
                                "t-att-for": (
                                    f"'{field_id.name}_' +"
                                    f" {sub_name_var}.{var_rec_name} + '_' +"
                                    f" str({sub_name_var}_index)"
                                ),
                                "t-att-string": (
                                    f"{sub_name_var}.{var_rec_name}"
                                ),
                            },
                            E.t({"t-esc": f"{sub_name_var}.{var_rec_name}"}),
                        ),
                    )
                elif field_id.ttype == "boolean":
                    dct_input_attr = {
                        "type": "checkbox",
                        "name": field_id.name,
                        "t-att-id": field_id.name,
                        "t-att-value": "True",
                        "t-att-checked": f"default_{field_id.name}",
                    }

                    if field_id.required:
                        dct_input_attr["required"] = "required"

                    sub_item = E.input(dct_input_attr)
                elif field_id.ttype == "selection":
                    dct_select_attr = {
                        "class": "form-control",
                        "id": field_id.name,
                        "name": field_id.name,
                    }

                    if field_id.required:
                        dct_select_attr["required"] = "True"

                    # TODO can be in conflict, if a field_id.name is item, or field_id.name[3:] exist
                    sub_name_var = (
                        field_id.name[:3] if len(field_id.name) > 3 else "item"
                    )

                    sub_item = E.select(
                        dct_select_attr,
                        E.t(
                            {
                                "t-foreach": field_id.name,
                                "t-as": sub_name_var,
                                "t-att-selected": (
                                    f"default_{field_id.name} =="
                                    f" {sub_name_var}[0]"
                                ),
                            },
                            E.option(
                                {"t-attf-value": f"#{{{sub_name_var}[0]}}"},
                                E.t({"t-esc": f"{sub_name_var}[1]"}),
                            ),
                        ),
                    )
                elif field_id.ttype in ("float", "integer", "monetary"):
                    dct_sub_item = {
                        "type": "text",
                        "class": "form-control",
                        "name": field_id.name,
                    }
                    if field_id.force_widget == "float_time":
                        dct_sub_item["placeholder"] = "hh:mm"

                    if field_id.name in lst_data_field_name:
                        dct_sub_item["t-attf-value"] = (
                            "#{" + field_id.name + "}"
                        )
                    else:
                        dct_sub_item[
                            "t-att-value"
                        ] = f"default_{field_id.name}"

                    if field_id.required:
                        dct_sub_item["required"] = "True"

                    if field_id.readonly:
                        dct_sub_item["readonly"] = "True"

                    sub_item = E.input(dct_sub_item)
                elif field_id.ttype in ("datetime", "date"):
                    id_name = f"{field_id.name}_datepicker"
                    dct_sub_item = {
                        "type": "text",
                        "class": "form-control datetimepicker-input",
                        "t-att-data-target": id_name,
                        "t-att-name": "prefix",
                        "t-att-value": f"default_{field_id.name}",
                    }

                    sub_item = E.div(
                        {
                            "class": "input-group date",
                            "data-target-input": "nearest",
                            "t-att-id": id_name,
                        },
                        E.input(dct_sub_item),
                        E.div(
                            {
                                "class": "input-group-append",
                                "t-att-data-target": id_name,
                                "data-toggle": "datetimepicker",
                            },
                            E.div(
                                {"class": "input-group-text"},
                                E.i({"class": "fa fa-calendar"}),
                            ),
                        ),
                    )
                else:
                    _logger.warning(
                        f"Type '{field_id.ttype}' not supported to generate in"
                        " portal."
                    )

                if field_id.force_widget and field_id.force_widget not in (
                    "link_button",
                    "image",
                    "float_time",
                ):
                    # TODO support image, show upload image and open tools to work the picture
                    _logger.warning(
                        f"Force widget '{field_id.force_widget}', type"
                        f" '{field_id.ttype}' not supported to generate in"
                        " portal."
                    )

                if sub_item is not None:
                    item_xml = E.div(
                        {"class": "form-group"},
                        E.label(
                            {
                                "class": "col-md-3 col-sm-4 control-label",
                                "for": field_id.name,
                            },
                            field_id.name.capitalize(),
                        ),
                        E.div({"class": "col-md-7 col-sm-8"}, sub_item),
                    )
                    lst_item_form.append(item_xml)

            item_xml = E.div(
                {"class": "form-group"},
                E.div(
                    {
                        "class": (
                            "col-md-offset-3 col-sm-offset-4 col-sm-8 col-md-7"
                        )
                    },
                    E.button(
                        {"class": "btn btn-primary btn-lg"},
                        f"Submit {_fmt_title(model_id.model)}",
                    ),
                ),
            )
            lst_item_form.append(item_xml)

            form_xml = E.form(
                {
                    "action": (
                        f"/submitted/{model_id.name.lower().replace(' ', '_')}"
                    ),
                    "method": "POST",
                    "class": "form-horizontal mt32",
                    "enctype": "multipart/form-data",
                },
                *lst_item_form,
            )

            # <t t-call="portal.portal_layout">
            root = E.t(
                {"t-call": "portal.portal_layout"},
                # <t groups="project.group_project_user" t-set="o_portal_fullwidth_alert">
                # TODO how associate group_project_user?
                # E.t({'t-set': 'o_portal_fullwidth_alert', 'groups': 'project.group_project_user'},
                E.div(
                    {"class": "container"},
                    E.div(
                        {"class": "row"},
                        E.div(
                            {"class": "col-md-12"},
                            E.h1(
                                {"class": "text-center"},
                                "Send a new"
                                f" {model_id.name.lower().replace('_', ' ')}",
                            ),
                        ),
                    ),
                ),
                form_xml,
            )

            content = ET.tostring(root, pretty_print=True)

            for key_uid, value in dct_replace.items():
                new_value = (
                    b"\n<!-- prettier-ignore-start -->"
                    + value
                    + b"<!-- prettier-ignore-end -->\n"
                )
                content = content.replace(key_uid, new_value)

            view_value = self._create_ui_view(
                content, key, qweb_name, None, None, model_created
            )
            lst_views.append(view_value)

        return lst_views

    def _create_ui_view(
        self,
        content,
        key,
        qweb_name,
        priority,
        inherit_id,
        model_created,
    ):
        content = content.strip()
        value = {
            # 'id': template_id,
            "key": key,
            "name": qweb_name,
            "type": "qweb",
            "arch": content,
            # TODO model and m2o_model are not suppose to here, only to link with code_generator
            # TODO find a new way to implement it without using 'model', else _get_models_info of code_generator
            # TODO cannot detect it
            "model": model_created.model,
            "m2o_model": model_created.id,
        }
        if priority:
            value["priority"] = priority
        if inherit_id:
            value["inherit_id"] = inherit_id

        view_value = self.env["ir.ui.view"].create(value)
        return view_value

    def _generate_model_access(self, model_created):
        if self.enable_generate_all or self.enable_generate_portal:
            # group_id = self.env['res.groups'].search([('name', '=', 'Code Generator / Manager')])
            # group_id = self.env['res.groups'].search([('name', '=', 'Internal User')])
            lang = "en_US"
            group_id = self.env.ref("base.group_portal").with_context(
                lang=lang
            )
            model_name = model_created.model
            model_name_str = model_name.replace(".", "_")
            v = {
                "name": "%s Access %s" % (model_name_str, group_id.full_name),
                "model_id": model_created.id,
                "group_id": group_id.id,
                "perm_read": True,
                "perm_create": True,
                "perm_write": True,
                "perm_unlink": True,
            }

            access_value = self.env["ir.model.access"].create(v)

        super(CodeGeneratorGeneratePortalWizard, self)._generate_model_access(
            model_created
        )
