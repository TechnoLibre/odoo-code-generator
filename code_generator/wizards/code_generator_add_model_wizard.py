from odoo import _, models, fields, api


class CodeGeneratorAddModelWizard(models.TransientModel):
    _name = "code.generator.add.model.wizard"
    _description = "Code Generator Model Wizard"

    code_generator_id = fields.Many2one(comodel_name="code.generator.module", string="Code Generator", required=True,
                                        ondelete='cascade')

    option_adding = fields.Selection([
        ('inherit', 'Inherit Model'),
        ('nomenclator', 'Nomenclator'),
    ], required=True, default='nomenclator', help="Inherit to inherit a new model.\nNomenclator to export data.")

    option_blacklist = fields.Selection([
        ('blacklist', 'Blacklist'),
        ('whitelist', 'Whitelist'),
    ], required=True, default='whitelist', help="When whitelist, all selected fields will be added.\n"
                                                "When blacklist, all selected fields will be ignored.")

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda s: s.env.user.id,
    )

    model_ids = fields.Many2many(
        comodel_name="ir.model", string="Models",
        help="Select the model you want to inherit or import data.")

    field_ids = fields.Many2many(
        comodel_name="ir.model.fields", string="Fields",
        help="Select the field you want to inherit or import data.")

    clear_fields_blacklist = fields.Boolean(string="Clear field blacklisted", default=False,
                                            help="Erase all blacklisted fields when enable.")

    @api.onchange('model_ids')
    def _onchange_model_ids(self):
        field_ids = [field_id.id for model_id in self.model_ids for field_id in model_id.field_id]
        self.field_ids = [(6, 0, field_ids)]

    @api.multi
    def button_generate_add_model(self):
        if self.clear_fields_blacklist:
            field_ids = self.env["code.generator.ir.model.fields"].search(
                [("m2o_module", "=", self.code_generator_id.id)])
            field_ids.unlink()

        is_nomenclator = self.option_adding == "nomenclator"
        lst_field_id = [a.id for a in self.field_ids]
        lst_ignore_model = ["website_theme_install"]
        for model_id in self.model_ids:
            # model_name = model_id.model

            # Ignore base model
            if model_id.model not in ("ir.ui.view",):
                module_name = model_id.modules
                lst_module_name = []
                if "," in module_name:
                    lst_module_name = [a.strip() for a in module_name.split(",")]
                else:
                    lst_module_name.append(module_name)

                for module_name in lst_module_name:
                    if module_name in lst_ignore_model:
                        continue
                    # Add dependency
                    # check not exist before added
                    module_id = self.env["ir.module.module"].search([("name", "=", module_name)])
                    dependencies_len = self.env["code.generator.module.dependency"].search_count(
                        [("module_id", "=", self.code_generator_id.id), ("depend_id", "=", module_id.id)])
                    if not dependencies_len:
                        value_dependencies = {
                            "module_id": self.code_generator_id.id,
                            "depend_id": module_id.id,
                            "name": module_id.display_name,
                        }
                        self.env["code.generator.module.dependency"].create(value_dependencies)

            if is_nomenclator:
                self.code_generator_id.nomenclator_only = True
                model_id.nomenclator = True
                model_id.m2o_module = self.code_generator_id.id

                # Disable nomenclator for unused fields
                for field_id in model_id.field_id:
                    if field_id.id in lst_field_id:
                        value = {
                            "m2o_module": self.code_generator_id.id,
                            "m2o_fields": field_id.id,
                            "nomenclature_blacklist": self.option_blacklist == "blacklist",
                            "nomenclature_whitelist": self.option_blacklist == "whitelist",
                        }
                        self.env["code.generator.ir.model.fields"].create(value)
