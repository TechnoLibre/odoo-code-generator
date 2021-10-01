from odoo import _, models, fields, api
from odoo.models import MAGIC_COLUMNS
from lxml.builder import E
from lxml import etree as ET

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


def _get_field_by_user(model):
    lst_field = []
    lst_magic_fields = MAGIC_FIELDS + ["name"]
    for field in model.field_id:
        if field.name not in lst_magic_fields:
            lst_field.append(field)
    return lst_field


class CodeGeneratorGenerateViewsWizard(models.TransientModel):
    _inherit = "code.generator.generate.views.wizard"

    selected_model_website_leaflet_ids = fields.Many2many(
        comodel_name="ir.model"
    )

    enable_generate_website_leaflet = fields.Boolean(
        string="Enable website leaflet feature",
        default=False,
        help=(
            "This variable need to be True to generate website leaflet if"
            " enable_generate_all is False"
        ),
    )

    def _generate_form_views_models(
        self, model_created, model_created_fields, module, dct_value_to_create
    ):
        result = super(
            CodeGeneratorGenerateViewsWizard, self
        )._generate_form_views_models(
            model_created, model_created_fields, module, dct_value_to_create
        )

        field_geo_id = model_created.field_id.filtered(
            lambda field: "geo_" in field.ttype
        )
        if not field_geo_id:
            return result

        model_name = model_created.model
        model_name_str = model_name.replace(".", "_")

        lst_field = []
        for field_geo in field_geo_id:
            field_xml = E.field({"name": field_geo.name})
            lst_field.append(field_xml)

        form_xml = E.geoengine({}, *lst_field)
        str_arch = ET.tostring(form_xml, pretty_print=True)
        view_value = self.env["ir.ui.view"].create(
            {
                "name": f"{model_name_str}_geoengine",
                "type": "form",
                "model": model_name,
                "arch": str_arch,
                "m2o_model": model_created.id,
            }
        )

        # Add layer
        for field_geo in field_geo_id.sorted(key="name"):
            value = {
                "name": f"Map Feature Basic {field_geo.name}",
                "geo_field_id": field_geo.id,
                "sequence": 6,
                "view_id": view_value.id,
                "nb_class": 1,
                "geo_repr": "basic",
                "begin_color": "#FF680A",
                "m2o_code_generator": module.id,
            }
            self.env["geoengine.vector.layer"].create(value)

        # Add raster
        # OSM
        value = {
            "name": "Map Feature Open Street Map",
            "overlay": 0,
            "view_id": view_value.id,
            "raster_type": "osm",
            "m2o_code_generator": module.id,
        }
        self.env["geoengine.raster.layer"].create(value)

        # d_wms
        value = {
            "name": "basic",
            "url": "vmap0.tiles.osgeo.org/wms/vmap0",
            "overlay": 1,
            "view_id": view_value.id,
            "raster_type": "d_wms",
            "m2o_code_generator": module.id,
        }
        self.env["geoengine.raster.layer"].create(value)

        return result

    @api.multi
    def button_generate_views(self):
        status = super(
            CodeGeneratorGenerateViewsWizard, self
        ).button_generate_views()
        if not status or (
            not self.enable_generate_all
            and not self.enable_generate_website_leaflet
        ):
            self.code_generator_id.enable_generate_website_leaflet = False
            return status

        self.code_generator_id.enable_generate_website_leaflet = True

        o2m_models = (
            self.code_generator_id.o2m_models
            if self.all_model
            else self.selected_model_website_leaflet_ids
        )

        return True

    def _add_dependencies(self):
        super(CodeGeneratorGenerateViewsWizard, self)._add_dependencies()
        if (
            not self.enable_generate_all
            and not self.enable_generate_website_leaflet
        ):
            return

        for code_generator in self.code_generator_id:
            code_generator.add_module_dependency("website")

    def _create_ui_view(
        self,
        content,
        template_id,
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
