# -*- coding: utf-8 -*-

import os

from code_writer import CodeWriter
from lxml import etree as ET
from lxml.builder import E

from odoo import api, fields, models, modules, tools

BREAK_LINE = ["\n"]
BREAK_LINE_OFF = "\n"
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def set_xml_views_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_views_file(module)
        if not module.enable_generate_geoengine:
            return

        # Hack for no permission restriction
        module = module.sudo()

        #
        # template scss
        #
        lst_template_xml = []

        if module.o2m_geoengine_vector_layer:
            for vector in module.o2m_geoengine_vector_layer:
                str_view_id = self.code_generator_data.dct_view_id.get(
                    vector.view_id.name
                )
                str_geo_field_id = (
                    f"field_{vector.geo_field_id.model.replace('.', '_')}__{vector.geo_field_id.name}"
                )
                lst_field = [
                    E.field({"name": "geo_field_id", "ref": str_geo_field_id}),
                    E.field({"name": "name"}, vector.name),
                    E.field({"name": "sequence", "eval": "6"}),
                    E.field({"name": "view_id", "ref": str_view_id}),
                    E.field({"name": "geo_repr"}, vector.geo_repr),
                    E.field({"name": "nb_class", "eval": "1"}),
                    E.field({"name": "begin_color"}, vector.begin_color),
                ]

                xml = E.record(
                    {
                        "id": f"geoengine_vector_layer_{vector.view_id.name}_{vector.geo_field_id.name}",
                        "model": "geoengine.vector.layer",
                    },
                    *lst_field,
                )
                lst_template_xml.append(xml)

        if module.o2m_geoengine_raster_layer:
            for raster in module.o2m_geoengine_raster_layer:
                lst_field = [
                    E.field({"name": "raster_type"}, raster.raster_type),
                    E.field({"name": "name"}, raster.name),
                    E.field(
                        {"name": "overlay", "eval": str(int(raster.overlay))}
                    ),
                    E.field({"name": "view_id", "ref": str_view_id}),
                ]

                if raster.url:
                    lst_field.append(E.field({"name": "url"}, raster.url))

                xml = E.record(
                    {
                        "id": f"geoengine_raster_layer_{raster.view_id.name}_{raster.raster_type}",
                        "model": "geoengine.raster.layer",
                    },
                    *lst_field,
                )
                lst_template_xml.append(xml)

        module_file = E.odoo({}, *lst_template_xml)
        data_file_path = os.path.join(
            self.code_generator_data.views_path, "geoengine.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_file, pretty_print=True
        )
        self.code_generator_data.write_file_binary(
            data_file_path, result, data_file=True
        )
