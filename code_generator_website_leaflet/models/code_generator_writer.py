import os

from lxml import etree as ET
from lxml.builder import E

from odoo import api, fields, models, modules, tools

BREAK_LINE = ["\n"]
BREAK_LINE_OFF = "\n"
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def get_lst_file_generate(self, module, python_controller_writer):
        if module.enable_generate_website_leaflet:
            # Controller
            self._set_website_leaflet_controller_file(python_controller_writer)
            self._set_website_leaflet_static_file(module)
            self._set_website_leaflet_static_javascript_file(module)

        super(CodeGeneratorWriter, self).get_lst_file_generate(
            module, python_controller_writer
        )

    def _set_website_leaflet_controller_file(self, python_controller_writer):
        """
        Function to set the module hook file
        :param python_controller_writer:
        :return:
        """

        lst_header = [
            "from odoo import http",
            "from operator import attrgetter",
            "import json",
            "import numpy",
            "from pyproj import Transformer",
            "from odoo.http import request",
            "from collections import defaultdict",
        ]

        file_path = f"{self.code_generator_data.controllers_path}/main.py"

        python_controller_writer.add_controller(
            file_path,
            lst_header,
            self._cb_set_website_leaflet_controller_file,
        )

    def _cb_set_website_leaflet_controller_file(self, module, cw):
        lst_fields = []
        lst_model = []
        active_id = None
        open_popup_id = None
        html_text_id = None
        for a in module.o2m_models:
            active_id = a.field_id.filtered(lambda key: key.name == "active")
            open_popup_id = a.field_id.filtered(
                lambda key: key.name == "open_popup"
            )
            html_text_id = a.field_id.filtered(
                lambda key: key.name == "html_text"
            )
            fields_id = a.field_id.filtered(
                lambda key: "geo_" in key.ttype
            ).sorted(key="name")
            if fields_id:
                lst_model.append(a)
                lst_fields = [b for b in fields_id]
                # Find right model
                break
        if not len(lst_fields):
            return
        # Cannot support multiple model with field geo
        assert len(lst_model) == 1
        model_id = lst_model[0]

        cw.emit(
            f"@http.route(['/{module.name}/map/config'], type='json',"
            ' auth="public", website=True, methods=["POST", "GET"],'
            " csrf=False)"
        )
        cw.emit("def map_detail(self):")
        with cw.indent():
            cw.emit('name = "test"')
            cw.emit("lat = 45.587134")
            cw.emit("lng = -73.733368")
            cw.emit("enable = True")
            cw.emit("size_width = 800")
            cw.emit("size_height = 600")
            cw.emit('provider = "CartoDB"')
            cw.emit("zoom = 13")
            cw.emit("categories = {}")
            # cw.emit(f"for i in http.request.env['{model_id.model}'].search([[\"active\", \"=\", True]]):")
            # with cw.indent():
            #     cw.emit("categories[i.id] = {")
            #     with cw.indent():
            #         cw.emit("\"name\": i.name,")
            #         cw.emit("\"description\": i.description,")
            # with cw.indent():
            #     cw.emit("}")
        with cw.indent():
            cw.emit("features = defaultdict(list)")
            cw.emit(
                'transformer = Transformer.from_crs("epsg:3857", "epsg:4326")'
            )
        cw.emit("")
        with cw.indent():
            str_search = ""
            if active_id:
                str_search = '("active", "=", True)'
            cw.emit(
                "map_feature_ids ="
                f' request.env["{model_id.model}"].sudo().search([{str_search}])'
            )
            cw.emit("for feature in map_feature_ids:")
            with cw.indent():
                cw.emit("value = {}")

                if len(lst_fields) == 1:
                    for field_id in lst_fields:
                        cw.emit(f"if not feature.{field_id.name}:")
                        with cw.indent():
                            cw.emit(f"continue")
                        if field_id.ttype == "geo_polygon":
                            cw.emit(
                                "xy ="
                                f" feature.{field_id.name}.exterior.coords.xy"
                            )
                        else:
                            cw.emit(f"xy = feature.{field_id.name}.xy")
                else:
                    cw.emit("# Help robot, ignore this")
                    cw.emit("if False:")
                    with cw.indent():
                        cw.emit("pass")
                    for field_id in lst_fields:
                        cw.emit(f'elif feature.type == "{field_id.name}":')
                        with cw.indent():
                            cw.emit(f"if not feature.{field_id.name}:")
                            with cw.indent():
                                cw.emit(f"continue")
                            if field_id.ttype == "geo_polygon":
                                cw.emit(
                                    "xy ="
                                    f" feature.{field_id.name}.exterior.coords.xy"
                                )
                            else:
                                cw.emit(f"xy = feature.{field_id.name}.xy")
        cw.emit("")
        with cw.indent():
            with cw.indent():
                cw.emit("coord_UTM = numpy.column_stack(xy).tolist()")
                cw.emit(
                    "coord_lat_long = [transformer.transform(*i) for i in"
                    " coord_UTM]"
                )
        # cw.emit("")
        with cw.indent():
            # with cw.indent():
            #     cw.emit("if feature.category_id:")
            #     with cw.indent():
            #         cw.emit("value[\"category_id\"] = feature.category_id.id")
            if open_popup_id:
                with cw.indent():
                    cw.emit("if feature.open_popup:")
                    with cw.indent():
                        cw.emit('value["open_popup"] = feature.open_popup')
            if html_text_id:
                with cw.indent():
                    cw.emit("if feature.html_text:")
                    with cw.indent():
                        cw.emit('value["html_popup"] = feature.html_text')
        cw.emit("")
        with cw.indent():
            with cw.indent():

                if len(lst_fields) == 1:
                    for field_id in lst_fields:
                        if field_id.ttype == "geo_point":
                            cw.emit('value["coordinates"] = coord_lat_long[0]')
                            cw.emit('features["markers"].append(value)')
                        else:
                            cw.emit('value["coordinates"] = coord_lat_long')
                            if field_id.ttype == "geo_polygon":
                                cw.emit('features["areas"].append(value)')
                            elif field_id.ttype == "geo_line":
                                cw.emit('features["lines"].append(value)')
                else:
                    cw.emit("# Help robot, ignore this")
                    cw.emit("if False:")
                    with cw.indent():
                        cw.emit("pass")

                    for field_id in lst_fields:
                        cw.emit(f'elif feature.type == "{field_id.name}":')
                        with cw.indent():
                            if field_id.ttype == "geo_point":
                                cw.emit(
                                    'value["coordinates"] = coord_lat_long[0]'
                                )
                                cw.emit('features["markers"].append(value)')
                            else:
                                cw.emit(
                                    'value["coordinates"] = coord_lat_long'
                                )
                                if field_id.ttype == "geo_polygon":
                                    cw.emit('features["areas"].append(value)')
                                elif field_id.ttype == "geo_line":
                                    cw.emit('features["lines"].append(value)')
        cw.emit()
        with cw.indent():
            cw.emit("return {")
            with cw.indent():
                cw.emit('"name": name,')
                cw.emit('"lat": lat,')
                cw.emit('"lng": lng,')
                cw.emit('"enable": enable,')
                cw.emit('"size_width": size_width,')
                cw.emit('"size_height": size_height,')
                cw.emit('"zoom": zoom,')
                cw.emit('"provider": provider,')
                cw.emit('"features": features,')
                cw.emit('"categories": categories,')
            cw.emit("}")

    def _set_website_leaflet_static_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        module_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        # file_path = os.path.join("static", "src", "js", "website.leaflet.animation.js")
        # source_file = os.path.join(module_path, file_path)

        # self.code_generator_data.copy_file(source_file, file_path)
        destination_directory = os.path.join("static", "src")
        source_directory = os.path.join(module_path, "static", "src")
        self.code_generator_data.copy_directory(
            source_directory, destination_directory
        )

        destination_file = os.path.join(
            destination_directory, "scss", "leaflet.scss"
        )
        source_file = os.path.join(source_directory, "scss", "leaflet.scss")

        search_and_replace = [("/website_leaflet", f"/{module.name}")]

        self.code_generator_data.copy_file(
            source_file,
            destination_file,
            data_file=False,
            search_and_replace=search_and_replace,
        )

    def _set_website_leaflet_static_javascript_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        content = (
            """function force_refresh_map(map) {
    map.invalidateSize(true);

    setTimeout(function () {
        force_refresh_map(map);
    }, 1000);
}

"""
            f"odoo.define('{module.name}.animation', function (require)"
            """ {
    'use strict';

    var sAnimation = require('website.content.snippets.animation');

    var lat = 55.505,
        lng = 38.6611378,
        enable = false,
        size_width = 500,
        size_height = 300,
        zoom = 13,
        provider = 'OpenStreetMap',
        name = '',
        features = '',
        geojson = '';

    sAnimation.registry.website_leaflet = sAnimation.Class.extend({
        """
            f"selector: '.{module.name}',"
            """

        start: function () {
            var self = this;
            var def = this._rpc({route: '"""
            f"/{module.name}/map/config"
            """'}).then(function (data) {
                // $timeline.empty();
                // $goal.empty();
                // $progression.empty();

                if (data.error) {
                    // $donationError.append(qweb.render('website.Error', {data: data}));
                    return;
                }

                if (_.isEmpty(data)) {
                    return;
                }

                var data_json = data;
                lat = data_json['lat'];
                lng = data_json['lng'];
                enable = data_json['enable'];
                size_width = data_json['size_width'];
                size_height = data_json['size_height'];
                zoom = data_json['zoom'];
                provider = data_json['provider'];
                name = data_json['name'];

                if (!enable) {
                    console.info("Map disabled");
                    return;
                }

                try {
                    geojson = JSON.parse(data_json['geojson']);
                } catch (error) {
                    console.error(error);
                    console.debug(data_json['geojson']);
                    geojson = ""
                }
                features = data_json['features'];

                var div_map = self.$('.map');
                if (!div_map.length) {
                    console.error("Cannot find map.");
                    return;
                } else if (div_map.length > 1) {
                    console.error("Cannot manage multiple map in one snippet.");
                    return;
                }
                // div_map.width(size_width);
                // $('#mapid').css('width', size_width);
                // div_map.height(size_height);
                // $('#mapid').css('height', size_height)
                // hide google icon
                // $('.img-fluid').hide();

                var map_id = "map_id_" + [...Array(10)].map(_ => (Math.random() * 36 | 0).toString(36)).join``;
                div_map.id = map_id;
                div_map.attr("id", map_id);

                console.info("Map Leaflet id generated : " + map_id);

                var point = new L.LatLng(lat, lng);
                var map = L.map(map_id).setView(point, zoom);
                force_refresh_map(map);
                L.tileLayer.provider(provider).addTo(map);
                if (geojson) {
                    L.geoJSON(geojson, {
                        onEachFeature: function (feature, layer) {
                            if (feature.properties.popup) {
                                layer.bindPopup(feature.properties.popup);
                            }
                        }
                    }).addTo(map);
                }
                if (features) {
                    if (features.markers) {
                        let markers = features.markers;
                        for (let marker of markers) {
                            console.info(marker);
                            // Implement category
                            var obj = L.marker(marker.coordinates).addTo(map);
                            if (marker.html_popup) {
                                let obj_popup = obj.bindPopup(marker.html_popup);
                                if (marker.open_popup) {
                                    obj_popup.openPopup();
                                }
                            }
                        }
                    }
                    if (features.lines) {
                        let lines = features.lines;
                        for (let line of lines) {
                            console.info(line);
                            var obj = L.polyline(line.coordinates).addTo(map);
                            if (line.html_popup) {
                                let obj_popup = obj.bindPopup(line.html_popup);
                                if (line.open_popup) {
                                    obj_popup.openPopup();
                                }
                            }
                        }
                    }
                    if (features.areas) {
                        let areas = features.areas;
                        for (let area of areas) {
                            console.info(area);
                            var obj = L.polygon(area.coordinates).addTo(map);
                            if (area.html_popup) {
                                let obj_popup = obj.bindPopup(area.html_popup);
                                if (area.open_popup) {
                                    obj_popup.openPopup();
                                }
                            }
                        }
                    }
                }
                var popup = L.popup();

                function onMapClick(e) {
                    popup
                        .setLatLng(e.latlng)
                        .setContent("You clicked the map at " + e.latlng.toString())
                        .openOn(map);
                }

                map.on('click', onMapClick);
            });

            return $.when(this._super.apply(this, arguments), def);
        }
    })

});
        """
        )

        file_path = os.path.join(
            "static", "src", "js", "website.leaflet.animation.js"
        )
        self.code_generator_data.write_file_str(file_path, content)

    def set_xml_views_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_views_file(module)
        if not module.enable_generate_website_leaflet:
            return

        #
        # template scss
        #
        lst_template_xml = []

        # map
        template_xml = E.template(
            {
                "id": f"s_{module.name}",
                "name": "Leaflet",
            },
            E.section(
                {"class": module.name},
                E.div(
                    {"class": "container"},
                    E.div(
                        {"class": "row"},
                        E.div(
                            {
                                "class": "map",
                                "style": "height:600px;width:800px;",
                            }
                        ),
                    ),
                ),
            ),
        )
        lst_template_xml.append(template_xml)

        # snippet
        lst_link = [
            E.t(
                {
                    "t-snippet": f"{module.name}.s_{module.name}",
                    "t-thumbnail": (
                        f"/{module.name}/static/description/icon.png"
                    ),
                }
            ),
        ]

        lst_xpath = [
            E.xpath(
                {
                    "expr": (
                        "//div[@id='snippet_feature']//t[@t-snippet][last()]"
                    ),
                    "position": "after",
                },
                *lst_link,
            ),
        ]
        template_xml = E.template(
            {
                "id": f"{module.name}_snippet",
                "inherit_id": "website.snippets",
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
                    "href": f"/{module.name}/static/src/scss/leaflet.scss",
                }
            ),
            E.link(
                {
                    "rel": "stylesheet",
                    "type": "text/scss",
                    "href": (
                        f"/{module.name}/static/src/scss/leaflet_custom.scss"
                    ),
                }
            ),
        ]
        lst_script = [
            E.script(
                {
                    "type": "text/javascript",
                    "src": f"/{module.name}/static/src/js/website.leaflet.animation.js",
                }
            ),
            E.script(
                {
                    "type": "text/javascript",
                    "src": f"/{module.name}/static/src/js/lib/leaflet.js",
                }
            ),
            E.script(
                {
                    "type": "text/javascript",
                    "src": f"/{module.name}/static/src/js/lib/leaflet-providers.js",
                }
            ),
        ]

        lst_xpath = [
            E.xpath(
                {"expr": "//link[last()]", "position": "after"}, *lst_link
            ),
            E.xpath(
                {"expr": "//script[last()]", "position": "after"}, *lst_script
            ),
        ]
        template_xml = E.template(
            {
                "id": f"{module.name}_assets_frontend",
                "inherit_id": "website.assets_frontend",
            },
            *lst_xpath,
        )
        lst_template_xml.append(template_xml)

        module_file = E.odoo({}, *lst_template_xml)
        data_file_path = os.path.join(
            self.code_generator_data.views_path, "snippets.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_file, pretty_print=True
        )
        self.code_generator_data.write_file_binary(
            data_file_path, result, data_file=True
        )
