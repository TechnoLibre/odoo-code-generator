# -*- coding: utf-8 -*-

from lxml import etree

from odoo import _, api
from odoo import fields as ofields
from odoo import models

CURRENTTARGETDOMAIN = [
    ("target", "=", "current"),
    ("view_mode", "not in", ["form", "tree", "tree,kanban"]),
]


def set_js_class_4views(view):
    """
    Function to modify the js_class attribute of each associated view
    :param view:
    :return:
    """

    arch2update = etree.XML(view["arch"])

    for tree_or_form in arch2update.xpath("//%s" % view["type"]):
        if view["type"] == "tree":
            tree_or_form.set("js_class", "enhanced_crud_tree")
        elif view["type"] == "form":
            tree_or_form.set("js_class", "enhanced_crud_form")
        elif view["type"] == "kanban":
            tree_or_form.set("js_class", "enhanced_crud_kanban")

        if view["type"] == "tree" and "editable" in tree_or_form.keys():
            del tree_or_form.attrib["editable"]

    view["arch"] = etree.tostring(arch2update)
    return view


class EnhancedCrudBase(models.AbstractModel):
    _inherit = "base"

    _action_id, _set_js_class_4view = None, False

    @api.model
    def _set_js_class_4views(self, view):
        """
        Function to modify the js_class attribute of each associated view
        :param view:
        :return:
        """

        return set_js_class_4views(view)

    @api.model
    def load_views(self, views, options=None):
        self._action_id = None
        self._set_js_class_4view = False
        if "action_id" in options:
            act_window = self.env["ir.actions.act_window"].browse(
                options["action_id"]
            )
            if self.env["enhanced.crud.act_window"].search(
                [("m2o_act_window", "=", act_window.id)]
            ) or (
                act_window.target == "current"
                and act_window.view_mode not in ["form", "tree", "tree,kanban"]
                and self.env["ir.config_parameter"]
                .sudo()
                .get_param("enhanced_crud.boo_apply2any", default=False)
            ):
                self._action_id = options["action_id"]

        if "set_js_class_4view" in self._context:
            self._set_js_class_4view = True

        return super(EnhancedCrudBase, self).load_views(views, options)

    @api.model
    def fields_view_get(
        self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):
        """
        Redefining the fields_view_get method to be able to call the _set_js_class_4views method
        :param view_id:
        :param view_type:
        :param toolbar:
        :param submenu:
        :return:
        """

        if self._set_js_class_4view or (
            self._action_id
            and view_type in ["tree", "form", "kanban"]
            and self.user_has_groups("enhanced_crud.enhanced_crud_manager")
        ):
            return self._set_js_class_4views(
                super(EnhancedCrudBase, self).fields_view_get(
                    view_id, view_type, toolbar, submenu
                )
            )

        else:
            return super(EnhancedCrudBase, self).fields_view_get(
                view_id, view_type, toolbar, submenu
            )

    @api.model
    def enhanced_crud_window_disposition(self):
        """
        Function that returns the configuration of the window disposition
        :return:
        """

        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("enhanced_crud.s_window_disposition", default="new")
        )

    @api.model
    def enhanced_crud_can_edit_pager(self):
        """
        Function that returns the configuration of the boo_can_edit_pager
        :return:
        """

        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("enhanced_crud.boo_can_edit_pager", default=False)
        )

    @api.model
    def enhanced_crud_on_formdiscarded(self):
        """
        Function that returns the configuration of the boo_on_formdiscarded
        :return:
        """

        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("enhanced_crud.boo_on_formdiscarded", default=True)
        )

    @api.model
    def enhanced_crud_contextmenu(self):
        """
        Function that returns the configuration of the boo_contextmenu
        :return:
        """

        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("enhanced_crud.boo_contextmenu", default=False)
        )


class EnhancedCrudActWindow(models.Model):
    _name = "enhanced.crud.act_window"
    _description = (
        "Window actions whose views have their js_class attribute pointed to"
        " the Enhanced CRUD module"
    )

    m2o_act_window = ofields.Many2one(
        string="Window action",
        help="Window action",
        comodel_name="ir.actions.act_window",
        required=True,
        domain=CURRENTTARGETDOMAIN,
        ondelete="cascade",
    )
