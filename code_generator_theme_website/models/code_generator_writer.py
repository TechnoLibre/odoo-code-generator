from odoo import models, fields, api

import os
import shutil
import tempfile
import uuid
from lxml.builder import E
from lxml import etree as ET
from collections import defaultdict

from code_writer import CodeWriter
from odoo.models import MAGIC_COLUMNS

BREAK_LINE = ["\n"]
BREAK_LINE_OFF = "\n"
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF
FROM_ODOO_IMPORTS = ["from odoo import _, api, models, fields"]
MODEL_HEAD = FROM_ODOO_IMPORTS + BREAK_LINE


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def set_xml_data_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_data_file(module)
        if not module.theme_website:
            return

        dct_associate_data = {}
        #
        # Actions act_url
        #
        lst_record_xml = []
        for action_act_url in module.o2m_model_act_url:
            lst_field = [
                E.field({"name": "name"}, action_act_url.name),
                E.field({"name": "url"}, action_act_url.url),
                E.field({"name": "target"}, action_act_url.target),
            ]
            id_action = self._get_action_act_url_name(action_act_url)
            dct_associate_data[action_act_url.name] = id_action
            record_xml = E.record({"model": "ir.actions.act_url", "id": id_action}, *lst_field)
            lst_record_xml.append(record_xml)

        for action_todo in module.o2m_model_act_todo:
            lst_field = [
                E.field(
                    {"name": "action_id", "ref": dct_associate_data.get(action_todo.action_id.name)}
                ),
                E.field({"name": "state"}, action_todo.state),
            ]
            # TODO force id, cannot support more than 1 action_todo
            record_xml = E.record({"model": "ir.actions.todo", "id": "base.open_menu"}, *lst_field)
            lst_record_xml.append(record_xml)

        module_file = E.odoo({}, *lst_record_xml)
        data_file_path = os.path.join(self.code_generator_data.data_path, f"{module.name}_data.xml")
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(module_file, pretty_print=True)
        self.code_generator_data.write_file_binary(data_file_path, result, data_file=True)

    def set_xml_views_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_views_file(module)
        if not module.theme_website:
            return

        #
        # template scss
        #
        lst_template_xml = []

        # website.assets_frontend
        lst_link = [
            E.link(
                {
                    "rel": "stylesheet",
                    "type": "text/scss",
                    "href": f"/{module.name}/static/src/scss/_variables.scss",
                }
            ),
            E.link(
                {
                    "rel": "stylesheet",
                    "type": "text/scss",
                    "href": f"/{module.name}/static/src/scss/custom.scss",
                }
            ),
        ]

        lst_xpath = [
            E.xpath({"expr": "//link[last()]", "position": "after"}, *lst_link),
        ]
        template_xml = E.template(
            {
                "id": f"{module.name}_assets_frontend",
                "inherit_id": "website.assets_frontend",
                "name": module.display_name,
                "active": "True",
            },
            *lst_xpath,
        )
        lst_template_xml.append(template_xml)

        # website.assets_primary_variables
        lst_link = [
            E.link(
                {
                    "rel": "stylesheet",
                    "type": "text/scss",
                    "href": f"/{module.name}/static/src/scss/primary_variables.scss",
                }
            ),
        ]

        lst_xpath = [
            E.xpath(
                {
                    "expr": "//link[@href='/website/static/src/scss/primary_variables.scss']",
                    "position": "replace",
                },
                *lst_link,
            ),
        ]
        template_xml = E.template(
            {
                "id": f"{module.name}_assets_primary_variables",
                "inherit_id": "website._assets_primary_variables",
            },
            *lst_xpath,
        )
        lst_template_xml.append(template_xml)

        module_file = E.odoo({}, *lst_template_xml)
        data_file_path = os.path.join(
            self.code_generator_data.views_path, f"{module.name}_templates.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(module_file, pretty_print=True)
        self.code_generator_data.write_file_binary(data_file_path, result, data_file=True)

    def set_module_python_file(self, module):
        super(CodeGeneratorWriter, self).set_module_python_file(module)
        if not module.theme_website:
            return

        cw = CodeWriter()
        for line in MODEL_HEAD:
            str_line = line.strip()
            cw.emit(str_line)

        cw.emit()
        cw.emit(f"class {self._get_class_name(module.name)}(models.AbstractModel):")
        with cw.indent():
            cw.emit("_inherit = 'theme.utils'")
        cw.emit()
        with cw.indent():
            cw.emit(f"def _{module.name}_post_copy(self, mod):")
            with cw.indent():
                cw.emit("self.disable_view('website_theme_install.customize_modal')")

        file_path = os.path.join(self.code_generator_data.models_path, f"{module.name}.py")

        self.code_generator_data.write_file_str(file_path, cw.render())

    def set_module_css_file(self, module):
        super(CodeGeneratorWriter, self).set_module_css_file(module)
        if not module.theme_website:
            return

        # _variables.scss files
        cw = CodeWriter(default_width=80)
        # cw.emit(f"$primary: {module.theme_website_primary_color} !default;")
        # cw.emit(f"$secondary: {module.theme_website_secondary_color} !default;")
        # cw.emit(f"$body-color: {module.theme_website_body_color} !default;")
        file_path = os.path.join(self.code_generator_data.css_path, "_variables.scss")
        self.code_generator_data.write_file_str(file_path, cw.render())

        # custom.scss files
        cw = CodeWriter()
        file_path = os.path.join(self.code_generator_data.css_path, "custom.scss")
        self.code_generator_data.write_file_str(file_path, cw.render())

        # primary_variables.scss files
        cw = CodeWriter()
        file_path = os.path.join(self.code_generator_data.css_path, "primary_variables.scss")
        cw.emit("$o-theme-layout: 'full';")
        cw.emit("//$o-theme-navbar-height: 300px;")
        cw.emit()
        cw.emit("//" + "-" * 78)
        cw.emit_wrapped_text(
            "Colors",
            prefix="// ",
            indent_after_first=True,
        )
        cw.emit("//" + "-" * 78)
        cw.emit()
        cw.emit("// Extend default color palettes with website-related colors")
        cw.emit("$-palettes: ();")
        cw.emit("@each $palette in $o-color-palettes {")
        with cw.indent():
            cw.emit("$-palettes: append($-palettes, map-merge((")
            with cw.indent():
                cw.emit(f"'body': {module.theme_website_body_color},")
                cw.emit(f"'menu': {module.theme_website_menu_color},")
                cw.emit(f"'footer': {module.theme_website_footer_color},")
                cw.emit(f"'text': {module.theme_website_text_color},")
                cw.emit(f"'alpha': {module.theme_website_primary_color},")
                cw.emit(f"'beta': {module.theme_website_secondary_color},")
                cw.emit(f"'gamma': {module.theme_website_extra_1_color},")
                cw.emit(f"'delta': {module.theme_website_extra_2_color},")
                cw.emit(f"'epsilon': {module.theme_website_extra_3_color},")
                cw.emit(f"'h1': null, // Default to text")
                cw.emit(f"'h2': null, // Default to h1")
                cw.emit(f"'h3': null, // Default to h2")
                cw.emit(f"'h4': null, // Default to h3")
                cw.emit(f"'h5': null, // Default to h4")
                cw.emit(f"'h6': null, // Default to h5")
            cw.emit("), $palette));")
        cw.emit("}")
        cw.emit()
        cw.emit("$o-color-palettes: $-palettes;")
        cw.emit()
        cw.emit("$o-theme-color-palettes: ();")
        cw.emit("@each $-palette in $-palettes {")
        with cw.indent():
            cw.emit(
                "$o-theme-color-palettes: append($o-theme-color-palettes, map-merge($-palette, ("
            )
            with cw.indent():
                cw.emit("'primary': map-get($-palette, 'alpha'),")
                cw.emit("'secondary': map-get($-palette, 'beta'),")
            cw.emit(")));")
        cw.emit("}")
        cw.emit()
        cw.emit("// By default, all user color palette values are null. Each null value is")
        cw.emit("// automatically replaced with corresponding color of chosen color palette.")
        cw.emit("$o-user-color-palette: () !default;")
        cw.emit()
        cw.emit("// By default, all user theme color palette values are null. Each null value")
        cw.emit("// is automatically replaced with corresponding color of chosen theme color")
        cw.emit("// palette.")
        cw.emit("$o-user-theme-color-palette: () !default;")
        cw.emit()
        cw.emit("//" + "-" * 78)
        cw.emit_wrapped_text(
            "Fonts",
            prefix="// ",
            indent_after_first=True,
        )
        cw.emit("//" + "-" * 78)
        cw.emit()
        cw.emit("$o-theme-fonts: (")
        with cw.indent():
            cw.emit(
                '(-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Noto, "Helvetica Neue", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"), // This is BS default'
            )
            cw.emit("('Open Sans', sans-serif),")
            cw.emit("('Source Sans Pro', sans-serif),")
            cw.emit("('Raleway', sans-serif),")
            cw.emit("('Noto Serif', serif),")
            cw.emit("('Arvo', Times, serif),")
        cw.emit(") !default;")
        cw.emit("$o-theme-font-urls: (")
        with cw.indent():
            cw.emit("null,")
            cw.emit("'Open+Sans:400,400i,700,700i',")
            cw.emit("'Source+Sans+Pro:400,400i,700,700i',")
            cw.emit("'Raleway:400,400i,700,700i',")
            cw.emit("'Noto+Serif:400,400i,700,700i',")
            cw.emit("'Arvo:400,400i,700,700i',")
        cw.emit(") !default;")
        cw.emit("$o-theme-font-names: (")
        with cw.indent():
            cw.emit("'Bootstrap',")
            cw.emit("'Open Sans',")
            cw.emit("'Source Sans Pro',")
            cw.emit("'Raleway',")
            cw.emit("'Noto Serif',")
            cw.emit("'Arvo',")
        cw.emit(") !default;")
        cw.emit("$o-theme-font-number: 1 !default;")
        cw.emit("$o-theme-headings-font-number: 1 !default;")
        cw.emit("$o-theme-buttons-font-number: 1 !default;")
        cw.emit("$o-theme-navbar-font-number: 1 !default;")
        self.code_generator_data.write_file_str(file_path, cw.render())
