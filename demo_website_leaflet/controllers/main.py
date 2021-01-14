from odoo import http
from operator import attrgetter
import json
import numpy
from pyproj import Transformer
from odoo.http import request
from collections import defaultdict


class MapFeatureController(http.Controller):

    @http.route(['/demo_website_leaflet/map/config'], type='json', auth="public", website=True,
                methods=['POST', 'GET'], csrf=False)
    def map_detail(self):
        name = "test"
        lat = 45.587134
        lng = -73.733368
        enable = True
        size_width = 800
        size_height = 600
        provider = "CartoDB"
        zoom = 13
        categories = {}
        features = defaultdict(list)
        transformer = Transformer.from_crs("epsg:3857", "epsg:4326")

        map_feature_ids = request.env["demo.website_leaflet.map.feature"].sudo().search([("active", "=", True)])
        for feature in map_feature_ids:
            value = {}
            # Help robot, ignore this
            if False:
                pass
            elif feature.type == "geo_line":
                if not feature.geo_line:
                    continue
                xy = feature.geo_line.xy
            elif feature.type == "geo_point":
                if not feature.geo_point:
                    continue
                xy = feature.geo_point.xy
            elif feature.type == "geo_polygon":
                if not feature.geo_polygon:
                    continue
                xy = feature.geo_polygon.exterior.coords.xy

            coord_UTM = numpy.column_stack(xy).tolist()
            coord_lat_long = [transformer.transform(*i) for i in coord_UTM]
            if feature.open_popup:
                value["open_popup"] = feature.open_popup
            if feature.html_text:
                value["html_popup"] = feature.html_text

            # Help robot, ignore this
            if False:
                pass
            elif feature.type == "geo_line":
                value["coordinates"] = coord_lat_long
                features["lines"].append(value)
            elif feature.type == "geo_point":
                value["coordinates"] = coord_lat_long[0]
                features["markers"].append(value)
            elif feature.type == "geo_polygon":
                value["coordinates"] = coord_lat_long
                features["areas"].append(value)

        return {
            "name": name,
            "lat": lat,
            "lng": lng,
            "enable": enable,
            "size_width": size_width,
            "size_height": size_height,
            "zoom": zoom,
            "provider": provider,
            "features": features,
            "categories": categories,
        }
