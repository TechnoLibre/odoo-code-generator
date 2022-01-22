from lxml import etree as ET
from lxml.builder import E

from odoo import _, api, fields, models
from odoo.models import MAGIC_COLUMNS

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


class CodeGeneratorGenerateThemeWebsiteWizard(models.TransientModel):
    _inherit = "code.generator.generate.views.wizard"

    enable_generate_theme_website = fields.Boolean(
        string="Enable theme website feature",
        default=False,
        help=(
            "This variable need to be True to generate theme_website if"
            " enable_generate_all is False"
        ),
    )

    theme_website_primary_color = fields.Char(
        string="Primary Color",
        default="#38B44A",
        help="Choose your primary color",
    )
    theme_website_secondary_color = fields.Char(
        string="Secondary Color",
        default="#AEA79F",
        help="Choose your secondary color",
    )
    theme_website_extra_1_color = fields.Char(
        string="Extra 1 Color",
        default="#ffbd92",
        help="Choose your extra 1 color",
    )
    theme_website_extra_2_color = fields.Char(
        string="Extra 2 Color",
        default="#ffbd92",
        help="Choose your extra 2 color",
    )
    theme_website_extra_3_color = fields.Char(
        string="Extra 3 Color",
        default="#ffbd92",
        help="Choose your extra 3 color",
    )

    theme_website_body_color = fields.Char(
        string="Body Color", default="#fff", help="Choose your body color"
    )
    theme_website_menu_color = fields.Char(
        string="Menu Color", default="#fff", help="Choose your menu color"
    )
    theme_website_footer_color = fields.Char(
        string="Footer Color", default="#fff", help="Choose your footer color"
    )
    theme_website_text_color = fields.Char(
        string="Text Color", default="#000", help="Choose your text color"
    )

    @api.multi
    def button_generate_views(self):
        status = super(
            CodeGeneratorGenerateThemeWebsiteWizard, self
        ).button_generate_views()
        if not status or not self.enable_generate_theme_website:
            self.code_generator_id.enable_generate_theme_website = False
            return status

        name = self.code_generator_id.name
        if not name.startswith("theme_"):
            self.code_generator_id.name = f"theme_{name}"

        self.code_generator_id.sequence = 900

        self.code_generator_id.category_id = self.env.ref(
            "base.module_category_theme"
        ).id

        self.code_generator_id.theme_website_primary_color = (
            self.theme_website_primary_color
        )
        self.code_generator_id.theme_website_secondary_color = (
            self.theme_website_secondary_color
        )
        self.code_generator_id.theme_website_extra_1_color = (
            self.theme_website_extra_1_color
        )
        self.code_generator_id.theme_website_extra_2_color = (
            self.theme_website_extra_2_color
        )
        self.code_generator_id.theme_website_extra_3_color = (
            self.theme_website_extra_3_color
        )
        self.code_generator_id.theme_website_body_color = (
            self.theme_website_body_color
        )
        self.code_generator_id.theme_website_menu_color = (
            self.theme_website_menu_color
        )
        self.code_generator_id.theme_website_footer_color = (
            self.theme_website_footer_color
        )
        self.code_generator_id.theme_website_text_color = (
            self.theme_website_text_color
        )

        self.code_generator_id.enable_generate_theme_website = True

        self.generate_theme_website_record(self.code_generator_id.name)

        return True

    def _add_dependencies(self):
        super(
            CodeGeneratorGenerateThemeWebsiteWizard, self
        )._add_dependencies()
        if not self.enable_generate_theme_website:
            return

        for code_generator in self.code_generator_id:
            code_generator.add_module_dependency(
                ["website_theme_install", "website"]
            )

    def generate_theme_website_record(self, module_name):
        """
          <record id="action_website" model="ir.actions.act_url">
            <field name="name">Website</field>
            <field name="url">/</field>
            <field name="target">self</field>
          </record>
          <record id="base.open_menu" model="ir.actions.todo">
            <field name="action_id" ref="action_website"/>
            <field name="state">open</field>
          </record>
        :param module_name:
        :return:
        """

        value = {
            "name": "Website",
            "url": "/",
            "target": "self",
            "m2o_code_generator": self.code_generator_id.id,
        }
        ir_actions_act_url = self.env["ir.actions.act_url"].create(value)

        value = {
            "action_id": ir_actions_act_url.id,
            "state": "open",
            "m2o_code_generator": self.code_generator_id.id,
        }
        self.env["ir.actions.todo"].create(value)
