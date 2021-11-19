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


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    m2o_model = fields.Many2one(
        "ir.model",
        string="Code generator Model",
        help="Model",
        ondelete="cascade",
    )
