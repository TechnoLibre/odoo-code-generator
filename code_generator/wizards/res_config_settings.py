from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    s_data2export = fields.Selection(
        selection=[
            (
                "nonomenclator",
                "Include the data of all of the selected models to export.",
            ),
            (
                "nomenclator",
                "Include the data of the selected models to export set it as"
                " nomenclator.",
            ),
        ],
        string="Model data to export",
        default="nomenclator",
        config_parameter="code_generator.s_data2export",
        help="Model data to export",
    )
