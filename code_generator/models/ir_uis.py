# -*- coding: utf-8 -*-

from odoo import models, fields, api


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    m2o_module = fields.Many2one(
        "code.generator.module",
        string="Module",
        help="Module",
        ondelete="cascade",
    )

    @api.model
    def default_get(self, fields_list):
        result = super(IrUiMenu, self).default_get(fields_list)

        if "parent_id" in result and result["parent_id"]:
            parent_menu = self.browse(result["parent_id"])

            if (
                parent_menu.name == "Menu Raíz Modulo A"
                and parent_menu.m2o_module
            ):
                result["name"] = "Menu Acción de Ventana Module A"
                result["m2o_module"] = parent_menu.m2o_module.id

                module_a_model_actionwindow = self.env[
                    "ir.actions.act_window"
                ].search([("name", "=", "modulo.a.modelo.actionwindow")])
                if module_a_model_actionwindow:
                    result["action"] = (
                        "ir.actions.act_window,%s"
                        % module_a_model_actionwindow[0].id
                    )

        return result


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    m2o_model = fields.Many2one(
        "ir.model",
        string="Code generator Model",
        help="Model",
        ondelete="cascade",
    )

    @api.onchange("type", "m2o_model")
    def _comun_4onchange_type_m2o_model(self):
        result = None
        if self.type and self.type != "qweb":
            result = "%s<%s>\n%s\n</%s>" % (
                '<?xml version="1.0"?>\n',
                self.type,
                "%s",
                self.type,
            )

        model = None
        if self.m2o_model:
            model = self.m2o_model.model

            if (
                result
                and self.type in ["tree", "form"]
                and self.env[self.m2o_model.model]._rec_name
            ):
                xml_content = (
                    '\t<field name="%s" />'
                    % self.env[self.m2o_model.model]._rec_name
                )
                result %= (
                    "\t<sheet>\n\t\t<group>\n\t\t\t%s\n\t\t</group>\n\t</sheet>"
                    % xml_content
                    if self.type == "form"
                    else xml_content
                )

            elif result and self.type == "search":
                result %= '\t<filter name="no_share" string="Filter View" domain="[(\'share\', \'=\', False)]"/>\n\t<group expand="0" string="Group By">\n\t\t<filter name="company_id" string="Company" domain="[]" />\n\t</group>'

            elif result:
                result %= ""

        elif result:
            result %= ""

        return dict(value=dict(arch_base=result, model=model))
