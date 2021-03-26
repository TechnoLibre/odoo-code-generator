from odoo import _, models, fields, api


class CodeGeneratorAddControllerWizard(models.TransientModel):
    _name = "code.generator.add.controller.wizard"
    _description = "Code Generator Add Controller Wizard"

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    # option_adding = fields.Selection([
    #     ('inherit', 'Inherit Model'),
    #     ('nomenclator', 'Nomenclator'),
    # ], required=True, default='nomenclator', help="Inherit to inherit a new model.\nNomenclator to export data.")

    # option_blacklist = fields.Selection([
    #     ('blacklist', 'Blacklist'),
    #     ('whitelist', 'Whitelist'),
    # ], required=True, default='whitelist', help="When whitelist, all selected fields will be added.\n"
    #                                             "When blacklist, all selected fields will be ignored.")

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda s: s.env.user.id,
    )

    model_ids = fields.Many2many(
        comodel_name="ir.model",
        string="Models",
        help="Select the model you want to inherit or import data.",
    )

    field_ids = fields.Many2many(
        comodel_name="ir.model.fields",
        string="Fields",
        help="Select the field you want to inherit or import data.",
    )

    # clear_fields_blacklist = fields.Boolean(string="Clear field blacklisted", default=False,
    #                                         help="Erase all blacklisted fields when enable.")

    @api.onchange("model_ids")
    def _onchange_model_ids(self):
        field_ids = [field_id.id for model_id in self.model_ids for field_id in model_id.field_id]
        self.field_ids = [(6, 0, field_ids)]

    @api.multi
    def button_generate_add_controller(self):
        pass
