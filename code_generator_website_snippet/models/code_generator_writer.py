# -*- coding: utf-8 -*-

from odoo import models, fields, api, modules, tools

from code_writer import CodeWriter
from lxml.builder import E
from lxml import etree as ET
import os

BREAK_LINE = ['\n']
BREAK_LINE_OFF = '\n'
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + \
                     BREAK_LINE_OFF + \
                     '<!-- License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). -->' + \
                     BREAK_LINE_OFF


class CodeGeneratorWriter(models.Model):
    _inherit = 'code.generator.writer'

    def get_lst_file_generate(self, module):
        if module.enable_generate_website_snippet:
            # Controller
            if module.enable_generate_website_snippet_javascript:
                self._set_website_snippet_controller_file(module)
                self._set_website_snippet_static_javascript_file(module)
            self._set_website_snippet_static_scss_file(module)

        super(CodeGeneratorWriter, self).get_lst_file_generate(module)

    def _set_website_snippet_controller_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()
        cw.emit("from odoo import http")
        cw.emit("from odoo.http import request")
        cw.emit("")
        cw.emit("")
        cw.emit("class HelloWorldController(http.Controller):")
        cw.emit("")
        with cw.indent():
            cw.emit(f"@http.route(['/{module.name}/helloworld'], type='json', auth=\"public\", website=True,")
        with cw.indent():
            with cw.indent():
                with cw.indent():
                    with cw.indent():
                        cw.emit("methods=['POST', 'GET'], csrf=False)")
        with cw.indent():
            cw.emit("def hello_world(self):")
            with cw.indent():
                cw.emit('return {"hello": "Hello World!"}')

        out = cw.render()

        l_model = out.split("\n")

        file_path = f'{self.code_generator_data.controllers_path}/main.py'

        self.code_generator_data.write_file_lst_content(file_path, l_model)

    def _set_website_snippet_static_javascript_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        content = f"odoo.define('{module.name}.animation', function (require)"""" {
    'use strict';

    var sAnimation = require('website.content.snippets.animation');

    sAnimation.registry."""f"{module.name}"""" = sAnimation.Class.extend({
        """f"selector: '.o_{module.name}',""""

        start: function () {
            var self = this;
            var def = this._rpc({route: '"""f"/{module.name}/helloworld""""'}).then(function (data) {

                if (data.error) {
                    return;
                }

                if (_.isEmpty(data)) {
                    return;
                }

                var data_json = data;
                var hello = data_json['hello'];
                self.$('."""f"{module.name}_value""""').text(hello);
            });

            return $.when(this._super.apply(this, arguments), def);
        }
    })
});
        """

        file_path = os.path.join("static", "src", "js", f"website.{module.name}.animation.js")
        self.code_generator_data.write_file_str(file_path, content)

    def _set_website_snippet_static_scss_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        content = ""

        file_path = os.path.join("static", "src", "scss", f"{module.name}.scss")
        self.code_generator_data.write_file_str(file_path, content)

    def set_xml_views_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_views_file(module)
        if not module.enable_generate_website_snippet:
            return

        lst_snippet = module.generate_website_snippet_list.split(";")
        if not any(lst_snippet):
            lst_snippet = [module.name]

        #
        # template scss
        #
        lst_template_xml = []

        comment = ET.Comment(' Snippets ')
        lst_template_xml.append(comment)

        for s_snippet in lst_snippet:
            xml_id = f"s_{s_snippet}"
            xml_id_class = f"o_{s_snippet}"
            xml_id_value = f"{s_snippet}"

            if module.enable_generate_website_snippet_javascript:
                s_class_extra = "text-center " if module.generate_website_snippet_type != "content" else ""
                s_value = E.div({"class": f"{s_class_extra}{xml_id_value}_value"}, "Hello")
            else:
                s_value = E.img({"class": f"img img-fluid",
                                 "src": f"/{module.name}/static/description/icon.png",
                                 "alt": s_snippet.title()})

            if module.generate_website_snippet_type == "structure":
                e_section = E.section({"class": f"{xml_id_class} oe_snippet_body"},
                                      E.div({"class": "container"},
                                            E.div({"class": "row mt16 mb16"}, s_value)))
            elif module.generate_website_snippet_type == "feature":
                e_section = E.section({"class": f"{xml_id_class}"},
                                      E.div({"class": "container"}, s_value))
            elif module.generate_website_snippet_type == "content":
                e_section = E.div({"class": f"{xml_id_class}"}, s_value)
            elif module.generate_website_snippet_type == "effect":
                e_section = E.section({"class": f"{xml_id_class}"},
                                      E.div({"class": "container"}, s_value))
            else:
                raise Exception(
                    f"Unknown from code_generator_website_snippet {module.generate_website_snippet_type}.")

            template_xml = E.template({
                "id": xml_id,
                "name": s_snippet.replace("_", " ").title(),
            },
                e_section
            )
            lst_template_xml.append(template_xml)

        if module.generate_website_snippet_type == "content":
            comment = ET.Comment(' Add snippets options ')
            lst_template_xml.append(comment)

            lst_div = []
            for s_snippet in lst_snippet:
                xml_id_class = f"o_{s_snippet}"
                xml_div = E.div({"data-selector": f".{xml_id_class}", "data-drop-in": ".row > div"})
                lst_div.append(xml_div)

            template_xml = E.template({
                "id": f"snippet_options",
                "inherit_id": "website.snippet_options",
            },
                E.xpath({"expr": "."}, *lst_div)
            )
            lst_template_xml.append(template_xml)

        comment = ET.Comment(' Add snippets to menu ')
        lst_template_xml.append(comment)

        lst_link = []
        for s_snippet in lst_snippet:
            xml_id = f"s_{s_snippet}"

            xml_t = E.t({"t-snippet": f"{module.name}.{xml_id}",
                         "t-thumbnail": f"/{module.name}/static/description/icon.png"})
            lst_link.append(xml_t)

        lst_xpath = [
            E.xpath(
                {"expr": f"//div[@id='snippet_{module.generate_website_snippet_type}']/div[hasclass('o_panel_body')]",
                 "position": "inside"}
                , *lst_link)
        ]
        template_xml = E.template({
            "id": "snippets",
            "inherit_id": "website.snippets",
        },
            *lst_xpath
        )
        lst_template_xml.append(template_xml)

        s_option_comment = " and Javascript" if module.enable_generate_website_snippet_javascript else ""
        s_comment = f" Add stylesheet{s_option_comment} "
        comment = ET.Comment(s_comment)
        lst_template_xml.append(comment)
        # website.assets_primary_variables

        lst_link = [
            E.link({"rel": "stylesheet", "type": "text/scss",
                    "href": f"/{module.name}/static/src/scss/{module.name}.scss"}),
        ]

        lst_xpath = [
            E.xpath({"expr": "//link[last()]", "position": "after"}, *lst_link),
        ]
        if module.enable_generate_website_snippet_javascript:
            lst_script = [
                E.script(
                    {"type": "text/javascript",
                     "src": f"/{module.name}/static/src/js/website.{module.name}.animation.js"}),
            ]
            lst_xpath.append(
                E.xpath({"expr": "//script[last()]", "position": "after"}, *lst_script),
            )

        template_xml = E.template({
            "id": "assets_frontend",
            "inherit_id": "website.assets_frontend",
        },
            *lst_xpath
        )
        lst_template_xml.append(template_xml)

        module_file = E.odoo({}, *lst_template_xml)
        data_file_path = os.path.join(self.code_generator_data.views_path, 'snippets.xml')
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(module_file, pretty_print=True)
        result_str = result.decode().replace("&gt;", ">")
        self.code_generator_data.write_file_str(data_file_path, result_str, data_file=True)
