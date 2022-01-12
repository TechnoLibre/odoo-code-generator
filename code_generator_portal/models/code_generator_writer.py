import logging

from code_writer import CodeWriter

from odoo import api, fields, models, modules, tools
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

BREAK_LINE = ["\n"]

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
    "activity_summary",
    "activity_type_id",
    "activity_user_id",
    "message_channel_ids",
    "message_main_attachment_id",
    "message_partner_ids",
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


class CodeGenerator(models.Model):
    _inherit = "code.generator.module"

    # TODO duplicate with code_generator_hook
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


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def get_lst_file_generate(self, module):
        if module.enable_generate_portal:
            # Controller
            self._set_portal_controller_file(module)
            if module.portal_enable_create:
                # Controller main
                self._set_portal_controller_main_file(module)

        super(CodeGeneratorWriter, self).get_lst_file_generate(module)

    def _set_portal_controller_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()
        cw.emit("from collections import OrderedDict")
        cw.emit("from operator import itemgetter")
        cw.emit("")
        cw.emit("from odoo import http, _")
        cw.emit("from odoo.exceptions import AccessError, MissingError")
        cw.emit("from odoo.http import request")
        cw.emit(
            "from odoo.addons.portal.controllers.portal import CustomerPortal,"
            " pager as portal_pager"
        )
        cw.emit("from odoo.tools import groupby as groupbyelem")
        cw.emit("")
        cw.emit("from odoo.osv.expression import OR")
        cw.emit("")
        cw.emit("")
        cw.emit("class CustomerPortal(CustomerPortal):")
        cw.emit("")
        with cw.indent():
            cw.emit("def _prepare_portal_layout_values(self):")
            with cw.indent():
                cw.emit(
                    "values = super(CustomerPortal,"
                    " self)._prepare_portal_layout_values()"
                )
                for model in module.o2m_models:
                    cw.emit(
                        f"values['{self._fmt_underscores(model.model)}_count']"
                        f" = request.env['{model.model}'].search_count([])"
                    )
                cw.emit("return values")
        cw.emit("")

        for model in module.o2m_models:
            has_group_by = False
            with cw.indent():
                cw.emit(
                    "# ------------------------------------------------------------"
                )
                cw.emit(f"# My {self._fmt_title(model.model)}")
                cw.emit(
                    "# ------------------------------------------------------------"
                )
                cw.emit(
                    f"def _{self._fmt_underscores(model.model)}_get_page_view_values(self,"
                    f" {self._fmt_underscores(model.model)}, access_token,"
                    " **kwargs):"
                )
                with cw.indent():
                    cw.emit("values = {")
                    with cw.indent():
                        cw.emit(
                            "'page_name':"
                            f" '{self._fmt_underscores(model.model)}',"
                        )
                        cw.emit(
                            f"'{self._fmt_underscores(model.model)}':"
                            f" {self._fmt_underscores(model.model)},"
                        )
                        # MATHBEN ADDED
                        cw.emit("'user': request.env.user")
                with cw.indent():
                    cw.emit("}")
                    cw.emit(
                        "return"
                        f" self._get_page_view_values({self._fmt_underscores(model.model)},"
                        " access_token, values,"
                        f" 'my_{self._fmt_underscores(model.model)}s_history',"
                        " False, **kwargs)"
                    )
            cw.emit("")
            with cw.indent():
                cw.emit(
                    f"@http.route(['/my/{self._fmt_underscores(model.model)}s',"
                    f" '/my/{self._fmt_underscores(model.model)}s/page/<int:page>'],"
                    " type='http', auth=\"user\", website=True)"
                )
                # cw.emit(f"def portal_my_{_fmt_underscores(model.model)}s(self, page=1, date_begin=None, date_end=None, "
                #         f"sortby=None, **kw):")
                # MATHBEN ADDED
                cw.emit(
                    f"def portal_my_{self._fmt_underscores(model.model)}s(self,"
                    " page=1, date_begin=None, date_end=None, sortby=None,"
                    " filterby=None, search=None, search_in='content', **kw):"
                )
                # MATHBEN NEED THIS FOR NEXT MODEL IF ONE DEPEND TO ANOTHER ONE
                # f"sortby=None, filterby=None, search=None, search_in='content', groupby='project', **kw):")
                with cw.indent():
                    cw.emit("values = self._prepare_portal_layout_values()")
                    cw.emit(
                        f"{self._fmt_camel(model.model)} ="
                        f" request.env['{model.model}']"
                    )
                    cw.emit("domain = []")
            cw.emit("")
            with cw.indent():
                with cw.indent():
                    cw.emit("searchbar_sortings = {")
                    with cw.indent():
                        cw.emit(
                            "'date': {'label': _('Newest'), 'order':"
                            " 'create_date desc'},"
                        )
                        cw.emit(
                            "'name': {'label': _('Name'), 'order': 'name'},"
                        )
                        # MATHBEN NEEDED BY TASK
                        # cw.emit("'name': {'label': _('Title'), 'order': 'name'},")
                        # cw.emit("'stage': {'label': _('Stage'), 'order': 'stage_id'},")
                        # cw.emit("'update': {'label': _('Last Stage Update'), 'order': 'date_last_stage_update desc'},")
                with cw.indent():
                    cw.emit("}")
                    cw.emit("searchbar_filters = {")
                    with cw.indent():
                        cw.emit("'all': {'label': _('All'), 'domain': []},")
                with cw.indent():
                    cw.emit("}")
                    cw.emit("searchbar_inputs = {")
                    # MATHBEN REMOVED, WAS in task
                    # with cw.indent():
                    #     cw.emit(
                    #         "'content': {'input': 'content', 'label': _('Search <span class=\"nolabel\"> (in Content)</span>')},")
                    #     cw.emit("'message': {'input': 'message', 'label': _('Search in Messages')},")
                    #     cw.emit("'customer': {'input': 'customer', 'label': _('Search in Customer')},")
                    #     cw.emit("'stage': {'input': 'stage', 'label': _('Search in Stages')},")
                    #     cw.emit("'all': {'input': 'all', 'label': _('Search in All')},")
                with cw.indent():
                    cw.emit("}")
                    cw.emit("searchbar_groupby = {")
                    # MATHBEN REMOVED, WAS in task
                    # with cw.indent():
                    #     cw.emit("'none': {'input': 'none', 'label': _('None')},")
                    #     cw.emit("'project': {'input': 'project', 'label': _('Project')},")
                with cw.indent():
                    cw.emit("}")
            cw.emit("")
            with cw.indent():
                with cw.indent():
                    pass
                    # MATHBEN WAS FOR TASK NOT USE IN PROJECT
                    # cw.emit("# extends filterby criteria with project the customer has access to")
                    # cw.emit("projects = request.env['project.project'].search([])")
                    # cw.emit("for project in projects:")
                    # with cw.indent():
                    #     cw.emit("searchbar_filters.update({")
                    #     with cw.indent():
                    #         cw.emit(
                    #             "str(project.id): {'label': project.name, 'domain': [('project_id', '=', project.id)]}")
                    # with cw.indent():
                    #     cw.emit("})")
            pass
            # cw.emit("")
            # with cw.indent():
            #     with cw.indent():
            #         cw.emit("# extends filterby criteria with project (criteria name is the project id)")
            #         cw.emit("# Note: portal users can't view projects they don't follow")
            #         cw.emit(
            #             "project_groups = request.env['project.task'].read_group([('project_id', 'not in', projects.ids)], "
            #             "['project_id'], ['project_id'])")
            #     with cw.indent():
            #         cw.emit("for group in project_groups:")
            #         with cw.indent():
            #             cw.emit("proj_id = group['project_id'][0] if group['project_id'] else False")
            #             cw.emit("proj_name = group['project_id'][1] if group['project_id'] else _('Others')")
            #             cw.emit("searchbar_filters.update({")
            #             with cw.indent():
            #                 cw.emit("str(proj_id): {'label': proj_name, 'domain': [('project_id', '=', proj_id)]}")
            #         with cw.indent():
            #             cw.emit("})")
            # cw.emit("")
            with cw.indent():
                with cw.indent():
                    cw.emit("# default sort by value")
                    cw.emit("if not sortby:")
                    with cw.indent():
                        cw.emit("sortby = 'date'")
                with cw.indent():
                    cw.emit("order = searchbar_sortings[sortby]['order']")
                    cw.emit("# default filter by value")
                    cw.emit("if not filterby:")
                    with cw.indent():
                        cw.emit("filterby = 'all'")
                with cw.indent():
                    cw.emit("domain = searchbar_filters[filterby]['domain']")
            cw.emit("")
            with cw.indent():
                with cw.indent():
                    cw.emit("# search")
                    cw.emit("if search and search_in:")
                    with cw.indent():
                        cw.emit("search_domain = []")
                    pass
                    # MATHBEN REMOVE IT, NOT USED IN PROJECT
                    #     cw.emit("if search_in in ('content', 'all'):")
                    #     with cw.indent():
                    #         cw.emit(
                    #             "search_domain = OR([search_domain, ['|', ('name', 'ilike', search), ('description', 'ilike', search)]])")
                    # with cw.indent():
                    #     cw.emit("if search_in in ('customer', 'all'):")
                    #     with cw.indent():
                    #         cw.emit("search_domain = OR([search_domain, [('partner_id', 'ilike', search)]])")
                    # with cw.indent():
                    #     cw.emit("if search_in in ('message', 'all'):")
                    #     with cw.indent():
                    #         cw.emit("search_domain = OR([search_domain, [('message_ids.body', 'ilike', search)]])")
                    # with cw.indent():
                    #     cw.emit("if search_in in ('stage', 'all'):")
                    #     with cw.indent():
                    #         cw.emit("search_domain = OR([search_domain, [('stage_id', 'ilike', search)]])")
                    with cw.indent():
                        cw.emit("domain += search_domain")
            with cw.indent():
                with cw.indent():
                    cw.emit(
                        "# archive groups - Default Group By 'create_date'"
                    )
                    cw.emit(
                        "archive_groups ="
                        f" self._get_archive_groups('{model.model}', domain)"
                    )
                    cw.emit("if date_begin and date_end:")
                    with cw.indent():
                        cw.emit(
                            "domain += [('create_date', '>', date_begin),"
                            " ('create_date', '<=', date_end)]"
                        )
                with cw.indent():
                    cw.emit(f"# {self._fmt_underscores(model.model)}s count")
                    cw.emit(
                        f"{self._fmt_underscores(model.model)}_count ="
                        f" {self._fmt_camel(model.model)}.search_count(domain)"
                    )
                    cw.emit("# pager")
                    cw.emit("pager = portal_pager(")
                    with cw.indent():
                        cw.emit(
                            f'url="/my/{self._fmt_underscores(model.model)}s",'
                        )
                        cw.emit(
                            "url_args={'date_begin': date_begin, 'date_end':"
                            " date_end, 'sortby': sortby, 'filterby':"
                            " filterby, 'search_in': search_in, 'search':"
                            " search},"
                        )
                        cw.emit(
                            f"total={self._fmt_underscores(model.model)}_count,"
                        )
                        cw.emit("page=page,")
                        cw.emit("step=self._items_per_page")
                with cw.indent():
                    cw.emit(")")
                    # cw.emit(
                    #     "# content according to pager and archive selected"
                    # )
                    # MATHBEN NOT IN PROJECT, BUT TASK
                    # cw.emit("if groupby == 'project':")
                    # with cw.indent():
                    #     cw.emit("order = \"project_id, %s\" % order  "
                    #             "# force sort on project first to group by project in view")
            cw.emit("")
            with cw.indent():
                with cw.indent():
                    cw.emit(
                        "# content according to pager and archive selected"
                    )
                    cw.emit(
                        f"{self._fmt_underscores(model.model)}s ="
                        f" {self._fmt_camel(model.model)}.search(domain,"
                        " order=order, limit=self._items_per_page,"
                        " offset=pager['offset'])"
                    )
                    # MATHBEN LAST LINE, TASK WAS offset=(page - 1) * self._items_per_page
                    cw.emit(
                        f"request.session['my_{self._fmt_underscores(model.model)}s_history']"
                        f" = {self._fmt_underscores(model.model)}s.ids[:100]"
                    )
                    # MATHBEN NEXT BLOCK 43 COMMENT TO NEXT LINE
                    # cw.emit("if groupby == 'project':")
                    # with cw.indent():
                    #     cw.emit(
                    #         "grouped_tasks = [request.env['project.task'].concat(*g) for k, g in groupbyelem(tasks, itemgetter('project_id'))]")
                pass
                # with cw.indent():
                #     cw.emit("else:")
                #     with cw.indent():
                #         cw.emit("grouped_tasks = [tasks]")
                # MATHBEN END BLOCK 43
            cw.emit("")
            with cw.indent():
                with cw.indent():
                    cw.emit("values.update({")
                    with cw.indent():
                        cw.emit("'date': date_begin,")
                        cw.emit("'date_end': date_end,")
                        # MATHBEN WAS IN TASK
                        # cw.emit("'grouped_tasks': grouped_tasks,")
                        # GROUPED_TASKS CAN REPLACE PROJECTS
                        cw.emit(
                            f"'{self._fmt_underscores(model.model)}s':"
                            f" {self._fmt_underscores(model.model)}s,"
                        )
                        cw.emit(
                            "'page_name':"
                            f" '{self._fmt_underscores(model.model)}',"
                        )
                        cw.emit("'archive_groups': archive_groups,")
                        cw.emit(
                            "'default_url':"
                            f" '/my/{self._fmt_underscores(model.model)}s',"
                        )
                        cw.emit("'pager': pager,")
                        cw.emit("'searchbar_sortings': searchbar_sortings,")
                        cw.emit("'searchbar_groupby': searchbar_groupby,")
                        cw.emit("'searchbar_inputs': searchbar_inputs,")
                        cw.emit("'search_in': search_in,")
                        if has_group_by:
                            cw.emit("'groupby': groupby,")
                        cw.emit(
                            "'searchbar_filters':"
                            " OrderedDict(sorted(searchbar_filters.items())),"
                        )
                        cw.emit("'sortby': sortby,")
                        cw.emit("'filterby': filterby,")
                with cw.indent():
                    cw.emit("})")
                    cw.emit(
                        "return"
                        f' request.render("{module.name}.portal_my_{self._fmt_underscores(model.model)}s",'
                        " values)"
                    )
            cw.emit("")
            with cw.indent():
                cw.emit(
                    f"@http.route(['/my/{self._fmt_underscores(model.model)}/<int:{self._fmt_underscores(model.model)}_id>'],"
                    " type='http', auth=\"public\", website=True)"
                )
                cw.emit(
                    f"def portal_my_{self._fmt_underscores(model.model)}(self,"
                    f" {self._fmt_underscores(model.model)}_id=None,"
                    " access_token=None, **kw):"
                )
                with cw.indent():
                    cw.emit("try:")
                    with cw.indent():
                        cw.emit(
                            f"{self._fmt_underscores(model.model)}_sudo ="
                            f" self._document_check_access('{model.model}',"
                            f" {self._fmt_underscores(model.model)}_id,"
                            " access_token)"
                        )
                with cw.indent():
                    cw.emit("except (AccessError, MissingError):")
                    with cw.indent():
                        cw.emit("return request.redirect('/my')")
            cw.emit("")
            with cw.indent():
                with cw.indent():
                    if "attachment_ids" in [a.name for a in model.field_id]:
                        cw.emit(
                            "# ensure attachment are accessible with access"
                            " token inside template"
                        )
                        cw.emit(
                            "for attachment in"
                            f" {self._fmt_underscores(model.model)}_sudo.attachment_ids:"
                        )
                        with cw.indent():
                            cw.emit("attachment.generate_access_token()")
                with cw.indent():
                    cw.emit(
                        "values ="
                        f" self._{self._fmt_underscores(model.model)}_get_page_view_values({self._fmt_underscores(model.model)}_sudo,"
                        " access_token, **kw)"
                    )
                    cw.emit(
                        "return"
                        f' request.render("{module.name}.portal_my_{self._fmt_underscores(model.model)}",'
                        " values)"
                    )
            cw.emit("")

        out = cw.render()

        l_model = out.split("\n")

        file_path = f"{self.code_generator_data.controllers_path}/portal.py"

        self.code_generator_data.write_file_lst_content(file_path, l_model)

    def _set_portal_controller_main_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()
        cw.emit("import logging")
        cw.emit("import werkzeug")
        cw.emit("import odoo.http as http")
        cw.emit("from odoo.http import request")
        cw.emit("import base64")
        cw.emit("_logger = logging.getLogger(__name__)")
        cw.emit("")
        cw.emit("")
        cw.emit(
            "class"
            f" {module.name.replace('_', ' ').title().replace(' ', '')}Controller(http.Controller):"
        )
        cw.emit("")
        with cw.indent():
            for model_id in module.o2m_models:
                lst_field_id = _get_field_by_user(model_id, keep_name=True)
                cw.emit(
                    f'@http.route("/new/{_fmt_underscores(model_id.model)}",'
                    ' type="http", auth="user", website=True)'
                )
                cw.emit(
                    f"def create_new_{_fmt_underscores(model_id.model)}(self,"
                    " **kw):"
                )
                with cw.indent():
                    lst_special_field = ["email", "name"]
                    lst_var_name = []
                    for field_id in lst_field_id:
                        if field_id.name in lst_special_field:
                            # TODO need to search a char with a special attribute to understand it's an email or name from user, an attribute to means if it's a user, or something else like a connexion information
                            cw.emit(
                                f"{field_id.name} ="
                                f" http.request.env.user.{field_id.name}"
                            )
                            lst_var_name.append(field_id.name)
                        elif field_id.ttype in ("many2one", "many2many"):
                            related_ir_model_id = self.env["ir.model"].search(
                                [("model", "=", field_id.relation)]
                            )
                            has_active = related_ir_model_id.field_id.filtered(
                                lambda x: x.name == "active"
                            )
                            if has_active:
                                search_txt = "[('active', '=', True)]"
                            else:
                                search_txt = "[]"
                            cw.emit(
                                f"{field_id.name} ="
                                f" http.request.env['{field_id.relation}'].search({search_txt})"
                            )
                            lst_var_name.append(field_id.name)
                        else:
                            _logger.warning(
                                f"Field type {field_id.ttype} is not supported"
                                " in portal writer main."
                            )

                    str_var_name = (
                        "{"
                        + ", ".join([f"'{a}': {a}" for a in lst_var_name])
                        + "}"
                    )
                    cw.emit(
                        "return"
                        f" http.request.render('{module.name}.portal_create_{_fmt_underscores(model_id.model)}',"
                        f" {str_var_name})"
                    )

                cw.emit()
                cw.emit(
                    f'@http.route("/submitted/{_fmt_underscores(model_id.model)}",'
                    ' type="http", auth="user", website=True, csrf=True)'
                )
                cw.emit(
                    f"def submit_{_fmt_underscores(model_id.model)}(self,"
                    " **kw):"
                )
                with cw.indent():
                    with cw.block(before="vals =", delim=("{", "}")):
                        for field_id in lst_field_id:
                            if field_id.ttype in ("char", "text"):
                                cw.emit(
                                    f"'{field_id.name}':"
                                    f" kw.get('{field_id.name}'),"
                                )
                            elif field_id.ttype in ("many2one",):
                                # TODO missing validation if value exist
                                cw.emit(
                                    f"'{field_id.name}':"
                                    f" int(kw.get('{field_id.name}')),"
                                )

                    for field_id in lst_field_id:
                        if (
                            field_id.ttype == "binary"
                            and not field_id.readonly
                        ):
                            cw.emit(f"if kw.get('{field_id.name}'):")
                            with cw.indent():
                                cw.emit(
                                    f"c_file_{field_id.name} ="
                                    f" request.httprequest.files.getlist('{field_id.name}')[-1]"
                                )
                                cw.emit(
                                    f"vals['{field_id.name}'] ="
                                    f" base64.b64encode(c_file_{field_id.name}.read())"
                                )
                        elif field_id.ttype in ("many2many",):
                            # TODO missing validation if value exist
                            cw.emit(f"if kw.get('{field_id.name}'):")
                            with cw.indent():
                                cw.emit(
                                    f"lst_value_{field_id.name} = [(4, int(a))"
                                    " for a in"
                                    f" request.httprequest.form.getlist('{field_id.name}')]"
                                )
                                cw.emit(
                                    f"vals['{field_id.name}'] ="
                                    f" lst_value_{field_id.name}"
                                )

                    cw.emit(
                        f"new_{_fmt_underscores(model_id.model)} ="
                        f" request.env['{model_id.model}'].sudo().create(vals)"
                    )
                    has_mail = bool(
                        self.env["code.generator.module.dependency"]
                        .search([("module_id", "=", module.id)])
                        .filtered(lambda a: a.name == "Discuss")
                    )
                    if has_mail:
                        cw.emit(
                            f"new_{_fmt_underscores(model_id.model)}.message_subscribe(partner_ids=request.env.user.partner_id.ids)"
                        )
                    cw.emit(
                        "return"
                        f" werkzeug.utils.redirect(f'/my/{self._fmt_underscores(model_id.model)}/"
                        "{"
                        f"new_{_fmt_underscores(model_id.model)}.id"
                        "}')"
                    )

        out = cw.render()

        l_model = out.split("\n")

        file_path = f"{self.code_generator_data.controllers_path}/main.py"

        self.code_generator_data.write_file_lst_content(file_path, l_model)
