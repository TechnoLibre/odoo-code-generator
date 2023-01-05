import logging
import os

from code_writer import CodeWriter
from lxml import etree as ET
from lxml.builder import E

from odoo import api, fields, models, modules, tools
from odoo.models import MAGIC_COLUMNS

_logger = logging.getLogger(__name__)

BREAK_LINE = ["\n"]
BREAK_LINE_OFF = "\n"
XML_VERSION_HEADER = (
    '<?xml version="1.0" encoding="utf-8"?>'
    + BREAK_LINE_OFF
    + "<!-- License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). -->"
    + BREAK_LINE_OFF
)

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
    "activity_summary",
    "activity_ids",
    "message_follower_ids",
    "message_ids",
    "website_message_ids",
    "activity_type_id",
    "activity_user_id",
    "message_channel_ids",
    "message_main_attachment_id",
    "message_partner_ids",
    "activity_date_deadline",
    "message_attachment_count",
    "message_has_error",
    "message_has_error_counter",
    "message_is_follower",
    "message_needaction",
    "message_needaction_counter",
    "message_unread",
    "message_unread_counter",
]


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def get_lst_file_generate(self, module, python_controller_writer):
        code_generator_snippet_ids = self.env["code.generator.snippet"].search(
            [("code_generator_id", "=", module.id)]
        )
        lst_controller_feature_added = []
        for code_generator_snippet_id in code_generator_snippet_ids:
            # Controller
            if code_generator_snippet_id.enable_javascript:
                # model_show_item_list
                key_controller_name = (
                    code_generator_snippet_id.controller_feature
                )
                if (
                    code_generator_snippet_id.controller_feature
                    == "model_show_item_list"
                ):
                    key_controller_name += f"_{code_generator_snippet_id.name}"
                if key_controller_name not in lst_controller_feature_added:
                    self._set_website_snippet_controller_file(
                        python_controller_writer, code_generator_snippet_id
                    )
                    lst_controller_feature_added.append(key_controller_name)
                self._set_website_snippet_static_javascript_file(
                    code_generator_snippet_id
                )
            self._set_website_snippet_static_scss_file(
                code_generator_snippet_id
            )

        super(CodeGeneratorWriter, self).get_lst_file_generate(
            module, python_controller_writer
        )

    def _set_website_snippet_controller_file(
        self, python_controller_writer, code_generator_snippet_id
    ):
        """
        Function to set the module hook file
        :param python_controller_writer:
        :param code_generator_snippet_id:
        :return:
        """

        lst_header = [
            "from odoo import http",
            "from odoo.http import request",
        ]

        if code_generator_snippet_id.show_diff_time:
            lst_header.append("import humanize")
            lst_header.append("from datetime import datetime")

        file_path = f"{self.code_generator_data.controllers_path}/main.py"

        python_controller_writer.add_controller(
            file_path,
            lst_header,
            self._cb_set_website_snippet_controller_file(
                code_generator_snippet_id
            ),
        )

    def _cb_set_website_snippet_controller_file(
        self, code_generator_snippet_id
    ):
        def _cb(module, cw):
            if (
                code_generator_snippet_id.controller_feature
                == "model_show_item_individual"
            ):
                if code_generator_snippet_id.model_name:
                    cw.emit(
                        f"@http.route(['/{code_generator_snippet_id.code_generator_id.name}/get_last_item'],"
                        " type='json', auth=\"public\", website=True,"
                        ' methods=["POST", "GET"], csrf=False)'
                    )
                    cw.emit("def get_last_item(self):")
                    with cw.indent():
                        lst_model_search = (
                            code_generator_snippet_id.get_model_list()
                        )
                        lst_model_id_search = []
                        for s_model in lst_model_search:
                            model_id = self.env["ir.model"].search(
                                [("model", "=", s_model)]
                            )
                            if model_id:
                                lst_model_id_search.append(model_id[0])
                            else:
                                _logger.warning(
                                    f"Model not existing : {s_model}"
                                )
                        for model_id in lst_model_id_search:
                            cw.emit(
                                "data_id ="
                                f' http.request.env["{model_id.model}"].search([],'
                                ' order="create_date desc", limit=1)'
                            )
                            cw.emit("dct_value = {}")
                            cw.emit("if data_id:")
                            with cw.indent():
                                for field_id in model_id.field_id:
                                    if field_id.name not in MAGIC_FIELDS:
                                        if field_id.ttype in (
                                            "char",
                                            "text",
                                            "integer",
                                            "monetary",
                                            "float",
                                            "datetime",
                                            "date",
                                            "boolean",
                                            "html",
                                        ):
                                            cw.emit(
                                                f"dct_value['{field_id.name}']"
                                                f" = data_id.{field_id.name}"
                                            )
                            cw.emit("return dct_value")
                else:
                    _logger.error("Cannot support empty snippet model_name.")
            elif (
                code_generator_snippet_id.controller_feature
                == "model_show_item_list"
            ):
                if code_generator_snippet_id.model_name:
                    lst_model_name = code_generator_snippet_id.get_model_list()
                    lst_url_get_page = (
                        code_generator_snippet_id.get_url_get_page()
                    )
                    lst_var_ids = code_generator_snippet_id.get_model_var_ids()
                    lst_var_id = code_generator_snippet_id.get_model_var_id()
                    lst_var_s = code_generator_snippet_id.get_model_var_s()
                    lst_var_prefix_associate_var = (
                        code_generator_snippet_id.get_model_var_prefix_associate_var()
                    )
                    lst_model_short_name_id = (
                        code_generator_snippet_id.get_model_var_id()
                    )
                    lst_model_short_name = (
                        code_generator_snippet_id.get_model_var()
                    )
                    lst_var_class_name = (
                        code_generator_snippet_id.get_model_var_class_name()
                    )
                    url_list = code_generator_snippet_id.get_url_get_list()
                    model_short_name_list = (
                        code_generator_snippet_id.get_snippet_list_name()
                    )
                    lst_var_xml_id_unit_name = (
                        code_generator_snippet_id.get_snippet_xml_id_unit_name()
                    )

                    for i, s_model_name in enumerate(lst_model_name):
                        # TODO valide if exist before create it
                        cw.emit(
                            f"@http.route(['{lst_url_get_page[i]}<int:{lst_model_short_name[i]}>'],"
                            " type='http', auth=\"public\", website=True)"
                        )
                        cw.emit(
                            f"def get_page_{lst_model_short_name[i]}(self,"
                            f" {lst_model_short_name[i]}=None):"
                        )
                        with cw.indent():
                            cw.emit(
                                "env ="
                                " request.env(context=dict(request.env.context))"
                            )
                            cw.emit()
                            cw.emit(
                                f"{lst_var_class_name[i]} ="
                                f' env["{s_model_name}"]'
                            )
                            cw.emit(f"if {lst_model_short_name[i]}:")
                            with cw.indent():
                                cw.emit(
                                    f"{lst_model_short_name_id[i]} ="
                                    f" {lst_var_class_name[i]}.sudo().browse({lst_model_short_name[i]}).exists()"
                                )
                            cw.emit("else:")
                            with cw.indent():
                                cw.emit(f"{lst_model_short_name_id[i]} = None")
                            cw.emit(
                                "dct_value ="
                                f' {{"{lst_model_short_name_id[i]}":'
                                f" {lst_model_short_name_id[i]}}}"
                            )
                            cw.emit()
                            cw.emit("# Render page")
                            with cw.block(
                                before="return request.render",
                                delim=("(", ")"),
                            ):
                                cw.emit(
                                    f'"{code_generator_snippet_id.code_generator_id.name}.{lst_var_xml_id_unit_name[i]}",'
                                )
                                cw.emit("dct_value")
                        cw.emit()

                    cw.emit(
                        f"@http.route(['{url_list}'],"
                        " type='json', auth=\"public\", website=True)"
                    )
                    cw.emit(f"def get_{model_short_name_list}(self):")
                    with cw.indent():
                        cw.emit(
                            "env ="
                            " request.env(context=dict(request.env.context))"
                        )
                        cw.emit()
                        for i, s_model_name in enumerate(lst_model_name):
                            cw.emit(
                                f"{lst_var_class_name[i]} ="
                                f' env["{s_model_name}"]'
                            )
                            with cw.block(
                                before=(
                                    f"{lst_var_ids[i]} ="
                                    f" {lst_var_class_name[i]}.sudo().search"
                                ),
                                after=".ids",
                                delim=("(", ")"),
                            ):
                                cw.emit("[]")
                                if code_generator_snippet_id.show_recent_item:
                                    cw.emit(f",order='create_date desc'")
                                if code_generator_snippet_id.limitation_item:
                                    cw.emit(
                                        f",limit={code_generator_snippet_id.limitation_item}"
                                    )
                            cw.emit(
                                f"{lst_var_s[i]} ="
                                f" {lst_var_class_name[i]}.sudo().browse({lst_var_ids[i]})"
                            )
                            cw.emit()
                        if code_generator_snippet_id.show_diff_time:
                            for i, s_model_name in enumerate(lst_model_name):
                                cw.emit(
                                    f"lst_time_diff{lst_var_prefix_associate_var[i]} = []"
                                )
                            cw.emit("timedate_now = datetime.now()")
                            # TODO support language from user language
                            cw.emit("# fr_CA not exist")
                            cw.emit(
                                "# check"
                                " .venv/lib/python3.7/site-packages/humanize/locale/"
                            )
                            cw.emit("_t = humanize.i18n.activate('fr_FR')")
                            for i, s_model_name in enumerate(lst_model_name):
                                cw.emit(
                                    f"for {lst_var_id[i]} in {lst_var_s[i]}:"
                                )
                                with cw.indent():
                                    cw.emit(
                                        "diff_time = timedate_now -"
                                        f" {lst_var_id[i]}.create_date"
                                    )
                                    cw.emit(
                                        "str_diff_time ="
                                        " humanize.naturaltime(diff_time).capitalize()"
                                        ' + "."'
                                    )
                                    cw.emit(
                                        f"lst_time_diff{lst_var_prefix_associate_var[i]}.append(str_diff_time)"
                                    )
                            cw.emit("humanize.i18n.deactivate()")
                            cw.emit()
                        with cw.block(
                            before="dct_value = ",
                            delim=("{", "}"),
                        ):
                            for i, s_model_name in enumerate(lst_model_name):
                                cw.emit(
                                    f"{',' if i else ''}'{lst_var_s[i]}':"
                                    f" {lst_var_s[i]}"
                                )
                                if code_generator_snippet_id.show_diff_time:
                                    cw.emit(
                                        f",'lst_time{lst_var_prefix_associate_var[i]}':"
                                        f" lst_time_diff{lst_var_prefix_associate_var[i]}"
                                    )

                        cw.emit()
                        cw.emit("# Render page")
                        with cw.block(
                            before=(
                                "return"
                                ' request.env["ir.ui.view"].render_template'
                            ),
                            delim=("(", ")"),
                        ):
                            cw.emit(
                                f'"{code_generator_snippet_id.code_generator_id.name}.'
                                f'{code_generator_snippet_id.get_snippet_xml_id_list_name()}",'
                            )
                            cw.emit("dct_value")
                else:
                    _logger.error("Cannot support empty snippet model_name.")
            elif code_generator_snippet_id.controller_feature == "helloworld":
                cw.emit(
                    f"@http.route(['/{code_generator_snippet_id.code_generator_id.name}/helloworld'],"
                    " type='json', auth=\"public\", website=True,"
                    ' methods=["POST", "GET"], csrf=False)'
                )
                cw.emit("def hello_world(self):")
                with cw.indent():
                    cw.emit('return {"hello": "Hello World!"}')
            else:
                _logger.warning(
                    "controller_feature"
                    f" '{code_generator_snippet_id.controller_feature}' not"
                    " supported."
                )

        return _cb

    def _set_website_snippet_static_javascript_file(
        self, code_generator_snippet_id
    ):
        """
        Function to set the module hook file
        :param code_generator_snippet_id:
        :return:
        """
        cw = CodeWriter()
        cw_before_empty_data = CodeWriter()
        cw_inside_empty_data = CodeWriter()
        cw_destroy = CodeWriter()
        cw.cur_indent = 4 * cw.default_dent
        url = ""
        header_event_list = ""

        if (
            code_generator_snippet_id.controller_feature
            == "model_show_item_individual"
        ):
            cw_before_empty_data.emit("self._$loadedContent = $(data);")
            cw_before_empty_data.emit()
            cw_inside_empty_data.emit()
            cw_inside_empty_data.emit(
                f'self.$(".o_loading_{code_generator_snippet_id.module_snippet_name}").text("NO'
                ' DATA");'
            )
            if code_generator_snippet_id.model_name:
                lst_model_search = code_generator_snippet_id.model_name.split(
                    ";"
                )
            else:
                lst_model_search = []
            lst_model_id_search = []
            for s_model in lst_model_search:
                model_id = self.env["ir.model"].search(
                    [("model", "=", s_model)]
                )
                if model_id:
                    lst_model_id_search.append(model_id[0])
                else:
                    _logger.warning(f"Model not existing : {s_model}")
            for model_id in lst_model_id_search:
                for field_id in model_id.field_id:
                    if field_id.name not in MAGIC_FIELDS:
                        cw.emit(f'if (data["{field_id.name}"]) {{')
                        with cw.indent():
                            with cw.indent():
                                cw.emit(
                                    f'self.$(".{field_id.name}_value").text(data["{field_id.name}"]);'
                                )
                            cw.emit("}")
            cw.emit(
                f'self.$(".o_loading_{code_generator_snippet_id.module_snippet_name}").remove();'
            )
            url = f"/{code_generator_snippet_id.code_generator_id.name}/get_last_item"
            header_event_list = """this._eventList = this.$('.container');
            this._originalContent = this._eventList[0].outerHTML;"""
            cw_destroy.emit(
                "this._eventList.replaceWith(this._originalContent);"
            )
        elif (
            code_generator_snippet_id.controller_feature
            == "model_show_item_list"
        ):
            if code_generator_snippet_id.model_name:
                cw.emit("self._$loadedContent = $(data);")
                cw.emit("self._eventList.replaceWith(self._$loadedContent);")
                url = code_generator_snippet_id.get_url_get_list()
                header_event_list = f"""this._eventList = this.$('.container');
                this._originalContent = this._eventList[0].outerHTML;"""
                cw_destroy.emit(
                    "this._$loadedContent.replaceWith(this._originalContent);"
                )
            else:
                _logger.error("Cannot support empty snippet model_name.")
        elif code_generator_snippet_id.controller_feature == "helloworld":
            cw.emit("self._$loadedContent = $(data);")
            cw.emit('self._eventList.text(data["hello"]);')
            url = f"/{code_generator_snippet_id.code_generator_id.name}/helloworld"
            header_event_list = f"""this._eventList = this.$('.{code_generator_snippet_id.module_snippet_name}_value');
            this._originalContent = this._eventList.text();"""
            cw_destroy.emit("this._eventList.text(this._originalContent);")
        else:
            _logger.error(
                "Not supported controller feature"
                f" {code_generator_snippet_id.controller_feature}"
            )
            return

        code = cw.render()
        code_before_empty_data = cw_before_empty_data.render()
        code_inside_empty_data = cw_inside_empty_data.render()
        code_destroy = cw_destroy.render()

        content = (
            f"odoo.define('{code_generator_snippet_id.module_snippet_name}.animation',"
            " function"
            " (require)"
            """ {
    'use strict';

    let sAnimation = require('website.content.snippets.animation');

    sAnimation.registry."""
            f"{code_generator_snippet_id.module_snippet_name}"
            """ = sAnimation.Class.extend({
        """
            "selector:"
            f" '.{code_generator_snippet_id.get_snippet_template_class()}',"
            """

        start: function () {
            let self = this;
            """
            + header_event_list
            + """
            let def = this._rpc({route: '"""
            f"{url}"
            """'}).then(function (data) {

                if (data.error) {
                    return;
                }

"""
            + code_before_empty_data
            + """
                if (_.isEmpty(data)) {"""
            + code_inside_empty_data
            + """return;
                }

"""
            + code
            + """    
            });

            return $.when(this._super.apply(this, arguments), def);
        },
        destroy: function () {
            this._super.apply(this, arguments);
            if (this._$loadedContent) {"""
            + code_destroy
            + """
            }
        },
    })
});
        """
        )

        file_path = os.path.join(
            "static",
            "src",
            "js",
            f"website.{code_generator_snippet_id.module_snippet_name}.animation.js",
        )
        self.code_generator_data.write_file_str(file_path, content)

    def _set_website_snippet_static_scss_file(self, code_generator_snippet_id):
        """
        Function to set the module hook file
        :param code_generator_snippet_id:
        :return:
        """

        content = ""

        file_path = os.path.join(
            "static",
            "src",
            "scss",
            f"{code_generator_snippet_id.module_snippet_name}.scss",
        )
        self.code_generator_data.write_file_str(file_path, content)

    def set_xml_views_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_views_file(module)
        code_generator_snippet_ids = self.env["code.generator.snippet"].search(
            [("code_generator_id", "=", module.id)]
        )
        if not code_generator_snippet_ids:
            return
        self._set_xml_views_file_snippet(
            [a for a in code_generator_snippet_ids]
        )
        self._set_xml_views_file_website(
            [a for a in code_generator_snippet_ids]
        )

    def _create_generic_html_field_model(
        self, model_name, lst_xml, lst_xml_small, s_class_extra
    ):
        """
        fill lst_xml from model_name
        """
        model_id = self.env["ir.model"].search([("model", "=", model_name)])
        if not model_id:
            _logger.warning(f"Model not existing : {model_name}")
            return
        for field_id in model_id.field_id:
            if field_id.name not in MAGIC_FIELDS:
                s_value = E.div(
                    {"class": f"{s_class_extra}{field_id.name}_value"}
                )
                s_label = E.b({}, f"{field_id.name}: ")
                lst_xml_small.append(s_label)
                lst_xml_small.append(s_value)
                a_row_value = E.div(
                    {"class": "row mt16 mb16"},
                    s_label,
                    s_value,
                )
                lst_xml.append(a_row_value)

    def _create_generic_html_field_model_2(
        self, model_name, model_short_name_under, lst_xml
    ):
        """
        fill lst_xml from model_name
        """
        model_id = self.env["ir.model"].search([("model", "=", model_name)])
        if not model_id:
            _logger.warning(f"Model not existing : {model_name}")
            return
        rec_name = model_id.get_rec_name()
        # ADD rec_name h4
        xml_item = E.h4(
            {
                "t-if": f"{model_short_name_under}.{rec_name}",
                "class": "o_default_snippet_text",
                "t-field": f"{model_short_name_under}.{rec_name}",
            }
        )
        lst_xml.append(xml_item)
        xml_item = E.h4(
            {
                "t-if": f"not {model_short_name_under}.{rec_name}",
                "class": "o_default_snippet_text",
            },
            "EMPTY",
        )
        lst_xml.append(xml_item)
        for field_id in model_id.field_id:
            if field_id.name not in MAGIC_FIELDS and field_id.name != rec_name:
                if field_id.force_widget == "image":
                    xml_item = E.div(
                        {},
                        E.img(
                            {
                                "t-if": (
                                    f"{model_short_name_under}.{field_id.name}"
                                ),
                                "t-att-src": f"image_data_uri({model_short_name_under}.{field_id.name})",
                                "alt": field_id.name,
                                "class": "img img-fluid d-block mx-auto",
                            }
                        ),
                    )
                elif field_id.force_widget == "link_button":
                    xml_item = E.div(
                        {"t-if": f"{model_short_name_under}.{field_id.name}"},
                        E.a(
                            {
                                "target": "_blank",
                                "t-attf-href": f"{{{{{model_short_name_under}.{field_id.name}}}}}",
                                "t-field": (
                                    f"{model_short_name_under}.{field_id.name}"
                                ),
                            }
                        ),
                    )
                elif field_id.force_widget == "float_time":
                    xml_item = E.div(
                        {},
                        E.span(
                            {
                                "t-field": (
                                    f"{model_short_name_under}.{field_id.name}"
                                ),
                                "t-options": (
                                    '{"widget": "duration", "unit":'
                                    ' "hour", "round": "minute"}'
                                ),
                            }
                        ),
                    )
                else:
                    xml_item = E.p(
                        {
                            "t-if": (
                                f"{model_short_name_under}.{field_id.name}"
                            ),
                            "class": "o_default_snippet_text",
                            "t-field": (
                                f"{model_short_name_under}.{field_id.name}"
                            ),
                        }
                    )
                lst_xml.append(xml_item)

    def _create_generic_html_field_model_3(
        self, model_name, model_short_name_under, lst_xml
    ):
        """
        fill lst_xml from model_name
        """
        model_id = self.env["ir.model"].search([("model", "=", model_name)])
        if not model_id:
            _logger.warning(f"Model not existing : {model_name}")
            return
        rec_name = model_id.get_rec_name()
        # ADD rec_name
        xml_item = E.div(
            {
                "class": "col-lg-12 s_title",
                "data-name": "Title",
            },
            E.h1(
                {
                    "class": "s_title_thin",
                    "style": "font-size: 62px; text-align: center;",
                    "t-field": f"{model_short_name_under}.{rec_name}",
                    "t-if": f"{model_short_name_under}.{rec_name}",
                }
            ),
            E.h1(
                {
                    "class": "s_title_thin",
                    "style": "font-size: 62px; text-align: center;",
                    "t-if": f"not {model_short_name_under}.{rec_name}",
                },
                "EMPTY",
            ),
        )
        lst_xml.append(xml_item)
        for field_id in model_id.field_id:
            if field_id.name not in MAGIC_FIELDS and field_id.name != rec_name:
                if field_id.force_widget == "image":
                    xml_item = E.div(
                        {
                            "class": "col-lg-12 s_text pt16 pb16",
                            "data-name": "Text",
                            "t-if": (
                                f"{model_short_name_under}.{field_id.name}"
                            ),
                        },
                        E.img(
                            {
                                "t-if": (
                                    f"{model_short_name_under}.{field_id.name}"
                                ),
                                "t-att-src": f"image_data_uri({model_short_name_under}.{field_id.name})",
                                "alt": field_id.name,
                                "class": "img img-fluid d-block mx-auto",
                            }
                        ),
                    )
                elif field_id.force_widget == "link_button":
                    xml_item = E.div(
                        {
                            "class": "col-lg-12 s_text pt16 pb16",
                            "data-name": "Text",
                            "t-if": (
                                f"{model_short_name_under}.{field_id.name}"
                            ),
                        },
                        E.p(
                            {
                                "class": "lead o_default_snippet_text",
                                "style": "text-align: center;",
                            },
                            E.a(
                                {
                                    "target": "_blank",
                                    "t-attf-href": f"{{{{{model_short_name_under}.{field_id.name}}}}}",
                                    "t-field": f"{model_short_name_under}.{field_id.name}",
                                }
                            ),
                        ),
                    )
                elif field_id.force_widget == "float_time":
                    xml_item = E.div(
                        {
                            "class": "col-lg-12 s_text pt16 pb16",
                            "data-name": "Text",
                            "t-if": (
                                f"{model_short_name_under}.{field_id.name}"
                            ),
                        },
                        E.p(
                            {
                                "class": "lead o_default_snippet_text",
                                "style": "text-align: center;",
                            },
                            E.span(
                                {
                                    "t-field": f"{model_short_name_under}.{field_id.name}",
                                    "t-options": (
                                        '{"widget": "duration", "unit":'
                                        ' "hour", "round": "minute"}'
                                    ),
                                }
                            ),
                        ),
                    )
                else:
                    xml_item = E.div(
                        {
                            "class": "col-lg-12 s_text pt16 pb16",
                            "data-name": "Text",
                            "t-if": (
                                f"{model_short_name_under}.{field_id.name}"
                            ),
                        },
                        E.p(
                            {
                                "class": "lead o_default_snippet_text",
                                "style": "text-align: center;",
                                "t-field": (
                                    f"{model_short_name_under}.{field_id.name}"
                                ),
                            }
                        ),
                    )
                lst_xml.append(xml_item)

    def _set_xml_views_file_snippet(self, lst_snippet_id):
        #
        # template scss
        #
        lst_template_xml = []
        # TODO can write generic code
        dct_snippet_content = {
            "structure": list(
                filter(
                    lambda snippet: snippet.snippet_type == "structure",
                    lst_snippet_id,
                )
            ),
            "content": list(
                filter(
                    lambda snippet: snippet.snippet_type == "content",
                    lst_snippet_id,
                )
            ),
            "feature": list(
                filter(
                    lambda snippet: snippet.snippet_type == "feature",
                    lst_snippet_id,
                )
            ),
            "effect": list(
                filter(
                    lambda snippet: snippet.snippet_type == "effect",
                    lst_snippet_id,
                )
            ),
        }

        has_javascript = bool(
            filter(
                lambda snippet: snippet.enable_javascript,
                lst_snippet_id,
            )
        )

        comment = ET.Comment(" Snippets ")
        lst_template_xml.append(comment)

        for snippet_id in lst_snippet_id:
            xml_id = snippet_id.get_snippet_template_xml_id()
            xml_id_class = snippet_id.get_snippet_template_class()

            lst_row_value = []

            lst_s_value = []
            if snippet_id.enable_javascript:
                s_class_extra = (
                    "text-center "
                    if snippet_id.snippet_type != "content"
                    else ""
                )
                if (
                    snippet_id.controller_feature
                    == "model_show_item_individual"
                ):
                    if not snippet_id.model_name:
                        _logger.error(
                            "Snippet controller_feature"
                            " 'model_show_item_individual' need model_name"
                        )
                    else:
                        s_value = E.h3(
                            {
                                "class": f"o_loading_{snippet_id.module_snippet_name}"
                            },
                            "LOADING...",
                        )
                        lst_row_value.append(s_value)

                        lst_model_search = snippet_id.get_model_list()
                        for s_model in lst_model_search:
                            self._create_generic_html_field_model(
                                s_model,
                                lst_row_value,
                                lst_s_value,
                                s_class_extra,
                            )
                elif snippet_id.controller_feature == "helloworld":
                    s_value = E.div(
                        {
                            "class": f"{s_class_extra}{snippet_id.module_snippet_name}_value"
                        },
                        "Hello",
                    )
                    lst_s_value.append(s_value)
                elif snippet_id.controller_feature == "model_show_item_list":
                    # Ignore it, content is empty, fully generated
                    pass
                else:
                    _logger.warning(
                        f"controller_feature '{snippet_id.controller_feature}'"
                        " is not supported."
                    )
            else:
                s_value = E.img(
                    {
                        "class": f"img img-fluid",
                        "src": f"/{snippet_id.code_generator_id.name}/static/description/icon.png",
                        "alt": snippet_id.module_snippet_name.title(),
                    }
                )
                lst_s_value.append(s_value)

            if lst_row_value:
                lst_s_value = lst_row_value

            if snippet_id.snippet_type == "structure":
                if lst_row_value:
                    e_section = E.section(
                        {"class": f"{xml_id_class} oe_snippet_body"},
                        E.div({"class": "container"}, *lst_row_value),
                    )
                else:
                    lst_row = [
                        E.div({"class": "row mt16 mb16"}, a)
                        for a in lst_s_value
                    ]

                    e_section = E.section(
                        {"class": f"{xml_id_class} oe_snippet_body"},
                        E.div({"class": "container"}, *lst_row),
                    )
            elif snippet_id.snippet_type == "feature":
                e_section = E.section(
                    {"class": f"{xml_id_class}"},
                    E.div({"class": "container"}, *lst_s_value),
                )
            elif snippet_id.snippet_type == "content":
                e_section = E.div(
                    {"class": f"{xml_id_class}"},
                    E.div({"class": "container"}, *lst_s_value),
                )
            elif snippet_id.snippet_type == "effect":
                e_section = E.section(
                    {"class": f"{xml_id_class}"},
                    E.div({"class": "container"}, *lst_s_value),
                )
            else:
                raise Exception(
                    "Unknown from code_generator_website_snippet"
                    f" {snippet_id.snippet_type}."
                )

            template_xml = E.template(
                {
                    "id": xml_id,
                    "name": snippet_id.module_snippet_name.replace(
                        "_", " "
                    ).title(),
                },
                e_section,
            )
            lst_template_xml.append(template_xml)

        lst_snippet_content = dct_snippet_content.get("content")
        if lst_snippet_content:
            comment = ET.Comment(" Add snippets options ")
            lst_template_xml.append(comment)

            lst_div = []
            for snippet_id in lst_snippet_content:
                xml_id_class = snippet_id.get_snippet_template_class()
                xml_div = E.div(
                    {
                        "data-selector": f".{xml_id_class}",
                        "data-drop-in": ".row > div",
                    }
                )
                lst_div.append(xml_div)

            template_xml = E.template(
                {
                    "id": f"snippet_options",
                    "inherit_id": "website.snippet_options",
                },
                E.xpath({"expr": "."}, *lst_div),
            )
            lst_template_xml.append(template_xml)

        comment = ET.Comment(" Add snippets to menu ")
        lst_template_xml.append(comment)

        for (
            snippet_type,
            lst_snippet_id_by_type,
        ) in dct_snippet_content.items():
            lst_link = []
            if lst_snippet_id_by_type:
                for snippet_id in lst_snippet_id_by_type:
                    xml_id = snippet_id.get_snippet_template_xml_id()

                    xml_t = E.t(
                        {
                            "t-snippet": (
                                f"{snippet_id.code_generator_id.name}.{xml_id}"
                            ),
                            "t-thumbnail": f"/{snippet_id.code_generator_id.name}/static/description/icon.png",
                        }
                    )
                    lst_link.append(xml_t)

                lst_xpath = [
                    E.xpath(
                        {
                            "expr": f"//div[@id='snippet_{snippet_type}']/div[hasclass('o_panel_body')]",
                            "position": "inside",
                        },
                        *lst_link,
                    )
                ]
                template_xml = E.template(
                    {
                        "id": f"snippet_{snippet_type}",
                        "inherit_id": "website.snippets",
                    },
                    *lst_xpath,
                )
                lst_template_xml.append(template_xml)

        s_comment = f" Add stylesheet "
        if has_javascript:
            s_comment += "and Javascript "
        comment = ET.Comment(s_comment)
        lst_template_xml.append(comment)
        # website.assets_primary_variables

        lst_link = []
        lst_script = []
        for snippet_id in lst_snippet_id:
            lst_link.append(
                E.link(
                    {
                        "rel": "stylesheet",
                        "type": "text/scss",
                        "href": f"/{snippet_id.code_generator_id.name}/static/src/scss/{snippet_id.module_snippet_name}.scss",
                    }
                )
            )
            if snippet_id.enable_javascript:
                lst_script.append(
                    E.script(
                        {
                            "type": "text/javascript",
                            "src": f"/{snippet_id.code_generator_id.name}/static/src/js/website.{snippet_id.module_snippet_name}.animation.js",
                        }
                    )
                )

        lst_xpath = []
        if lst_link:
            lst_xpath.append(
                E.xpath(
                    {"expr": "//link[last()]", "position": "after"}, *lst_link
                )
            )
        if lst_script:
            lst_xpath.append(
                E.xpath(
                    {"expr": "//script[last()]", "position": "after"},
                    *lst_script,
                )
            )

        if lst_xpath:
            template_xml = E.template(
                {
                    "id": "assets_frontend",
                    "inherit_id": "website.assets_frontend",
                },
                *lst_xpath,
            )
            lst_template_xml.append(template_xml)

        if lst_template_xml:
            module_file = E.odoo({}, *lst_template_xml)
            data_file_path = os.path.join(
                self.code_generator_data.views_path, "snippets.xml"
            )
            result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
                module_file, pretty_print=True
            )
            result_str = result.decode().replace("&gt;", ">")
            self.code_generator_data.write_file_str(
                data_file_path, result_str, data_file=True
            )

    def _set_xml_views_file_website(self, lst_snippet_id):
        lst_template_xml = []

        for snippet_id in lst_snippet_id:
            if snippet_id.controller_feature == "model_show_item_list":
                lst_xml_model = []

                lst_var_s = snippet_id.get_model_var_s()
                lst_var = snippet_id.get_model_var()
                lst_var_prefix_associate_var = (
                    snippet_id.get_model_var_prefix_associate_var()
                )
                lst_url_get_page = snippet_id.get_url_get_page()
                lst_var_xml_id_unit_name = (
                    snippet_id.get_snippet_xml_id_unit_name()
                )
                lst_var_xml_name_title = (
                    snippet_id.get_snippet_xml_name_title()
                )
                lst_model_short_name_id = snippet_id.get_model_var_id()

                if snippet_id.model_name:
                    lst_model_name = snippet_id.get_model_list()

                    for i, model_name in enumerate(lst_model_name):
                        one_pager_xml = (
                            self._set_xml_views_file_one_pager_model_website(
                                model_name,
                                lst_model_short_name_id[i],
                                lst_var_xml_id_unit_name[i],
                                lst_var_xml_name_title[i],
                            )
                        )
                        lst_template_xml.append(one_pager_xml)

                        xml_model = self._create_xml_views_file_model_website(
                            snippet_id,
                            model_name,
                            lst_var_s[i],
                            lst_var[i],
                            lst_var_prefix_associate_var[i],
                            lst_url_get_page[i],
                        )
                        lst_xml_model.append(xml_model)

                    # Snippet content
                    root = E.template(
                        {
                            "id": snippet_id.get_snippet_xml_id_list_name(),
                            "name": snippet_id.get_snippet_xml_name_title_list(),
                        },
                        # <t t-ignore="true">
                        E.t(
                            {"t-ignore": "true"},
                            # <div class="container">
                            E.div(
                                {"class": "container"},
                                # <div class="row align-items-center">
                                *lst_xml_model,
                            ),
                        ),
                    )
                    lst_template_xml.append(root)
                else:
                    _logger.error("Cannot support empty snippet model_name.")

        if lst_template_xml:
            module_file = E.odoo({}, *lst_template_xml)
            data_file_path = os.path.join(
                self.code_generator_data.templates_path, "website.xml"
            )
            result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
                module_file, pretty_print=True
            )
            result_str = result.decode()
            # TODO < is not supported in xml attribute, so why support > ?
            result_str = result_str.replace("&gt;", ">")
            self.code_generator_data.write_file_str(
                data_file_path, result_str, data_file=True
            )

    def _set_xml_views_file_one_pager_model_website(
        self,
        model_name,
        model_short_name_under,
        xml_id_unit_name,
        model_short_name_title,
    ):
        lst_xml_item = []
        self._create_generic_html_field_model_3(
            model_name, model_short_name_under, lst_xml_item
        )

        # one page
        root = E.template(
            {
                "id": xml_id_unit_name,
                "name": model_short_name_title,
            },
            # <t t-call="website.layout">
            E.t(
                {"t-call": "website.layout"},
                # <div id="wrap">
                E.div(
                    {"id": "wrap"},
                    # <div class="oe_structure">
                    E.div(
                        {"class": "oe_structure"},
                        # <section class="pt32 pb32" t-if="not offre">
                        E.section(
                            {
                                "class": "pt32 pb32",
                                "t-if": f"not {model_short_name_under}",
                            },
                            # <div class="container">
                            E.div(
                                {"class": "container"},
                                # <div class="row s_nb_column_fixed">
                                E.div(
                                    {"class": "row s_nb_column_fixed"},
                                    # <div class="col-lg-12 s_title pt16 pb16" style="text-align: center;">
                                    E.div(
                                        {
                                            "class": (
                                                "col-lg-12 s_title pt16 pb16"
                                            ),
                                            "style": "text-align: center;",
                                        },
                                        # <h1 class="s_title_default">
                                        E.h1(
                                            {"class": "s_title_default"},
                                            # <font style="font-size: 62px;">Offre non existante</font>
                                            E.font(
                                                {"style": "font-size: 62px;"},
                                                f"{model_short_name_under} non"
                                                " existante",
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                        # <section class="s_cover parallax s_parallax_is_fixed bg-black-50 pt96 pb96 s_parallax_no_overflow_hidden" data-scroll-background-ratio="1" style="background-image: none;" t-if="offre">
                        E.section(
                            {
                                "t-if": model_short_name_under,
                                "class": (
                                    "s_cover parallax"
                                    " s_parallax_is_fixed"
                                    " bg-black-50"
                                    " pt96 pb96"
                                    " s_parallax_no_overflow_hidden"
                                ),
                                "data-scroll-background-ratio": "1",
                                "style": "background-image: none;",
                            },
                            # <span class="s_parallax_bg oe_img_bg oe_custom_bg" style="background-image: url('/web/image/website.s_cover_default_image'); background-position: 50% 0;"/>
                            E.span(
                                {
                                    "class": (
                                        "s_parallax_bg oe_img_bg oe_custom_bg"
                                    ),
                                    "style": (
                                        "background-image:"
                                        " url('/web/image/website.s_cover_default_image');"
                                        " background-position: 50% 0;"
                                    ),
                                }
                            ),
                            # <div class="container">
                            E.div(
                                {"class": "container"},
                                # <div class="row s_nb_column_fixed">
                                E.div(
                                    {"class": "row s_nb_column_fixed"},
                                    *lst_xml_item,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
        return root

    def _create_xml_views_file_model_website(
        self,
        snippet_id,
        model_name,
        model_short_name_s,
        model_short_name_under,
        prefix_associate_var,
        url_unit,
    ):
        lst_xml_item = []
        self._create_generic_html_field_model_2(
            model_name, model_short_name_under, lst_xml_item
        )
        if snippet_id.show_diff_time:
            # <p class="o_default_snippet_text" t-if="offre_index &lt; len(lst_time)" t-raw="lst_time[offre_index]"/>
            xml_show_time = E.p(
                {
                    "t-if": (
                        f"len(lst_time{prefix_associate_var}) >="
                        f" {model_short_name_under}_index"
                    ),
                    "class": "o_default_snippet_text",
                    "t-raw": f"lst_time{prefix_associate_var}[{model_short_name_under}_index]",
                }
            )
            lst_xml_item.append(xml_show_time)

        return E.div(
            {"class": "row align-items-center"},
            # <div class="col-lg-6 s_col_no_bgcolor pb24">
            E.div(
                {"class": "col-lg-6 s_col_no_bgcolor pb24"},
                # <div class="row" t-if="offres">
                E.div(
                    {
                        "class": "row",
                        "t-if": model_short_name_s,
                    },
                    # <div t-as="offre" t-foreach="offres">
                    E.div(
                        {
                            "t-foreach": model_short_name_s,
                            "t-as": model_short_name_under,
                        },
                        # <a t-att-href="'/offre/%d' % offre.id" t-if="offre">
                        E.a(
                            {
                                "t-if": model_short_name_under,
                                "t-att-href": (
                                    f"'{url_unit}%d' %"
                                    f" {model_short_name_under}.id"
                                ),
                            },
                            # <div class="col-lg-12 pt16 pb16" data-name="Box">
                            E.div(
                                {
                                    "class": "col-lg-12 pt16 pb16",
                                    "data-name": "Box",
                                },
                                # <i class="fa fa-2x fa-files-o rounded-circle bg-primary s_features_grid_icon"/>
                                E.i(
                                    {
                                        "class": (
                                            "fa fa-2x"
                                            " fa-files-o"
                                            " rounded-circle"
                                            " bg-primary"
                                            " s_features_grid_icon"
                                        )
                                    }
                                ),
                                # <div class="s_features_grid_content">
                                E.div(
                                    {"class": "s_features_grid_content"},
                                    *lst_xml_item,
                                ),
                            ),
                        ),
                    ),
                ),
                # <div class="row" t-if="not offres">
                E.div(
                    {
                        "class": "row",
                        "t-if": f"not {model_short_name_s}",
                    },
                    f"Aucune {model_short_name_under} disponible.",
                ),
            ),
        )
