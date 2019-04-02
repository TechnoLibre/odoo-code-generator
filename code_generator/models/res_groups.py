# -*- coding: utf-8 -*-

from odoo import models, fields


class ResGroups(models.Model):
    _inherit = 'res.groups'

    m2o_module = fields.Many2one(
        'code.generator.module',
        string='Module',
        help="Module",
        ondelete='cascade'
    )
