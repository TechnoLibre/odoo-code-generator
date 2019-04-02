# -*- coding: utf-8 -*-

from odoo import models, fields


class CodeGeneratorConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    s_data2export = fields.Selection(
        string='Model data to export',
        help='Model data to export',
        selection=[
            ('nonomenclator', 'Include the data of all of the selected models to export.'),
            ('nomenclator', 'Include the data of the selected models to export set it as nomenclator.')
        ],
        default='nomenclator',
        config_parameter='code_generator.s_data2export'
    )
