from odoo import models, fields, api, modules, tools


class IrModelDependency(models.Model):
    _name = "code.generator.ir.model.dependency"
    _description = "Code Generator ir model Dependency"

    depend_id = fields.Many2one("ir.model", "Dependency", ondelete="cascade")
    name = fields.Char(compute="compute_name")

    ir_model_ids = fields.One2many(
        comodel_name="ir.model",
        inverse_name="inherit_model_ids",
        string="Ir model",
        help="Origin model with dependency",
    )

    @api.depends("depend_id")
    def compute_name(self):
        for rec in self:
            if rec.depend_id:
                rec.name = rec.depend_id.model
