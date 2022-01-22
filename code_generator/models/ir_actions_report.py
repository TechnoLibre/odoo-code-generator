from odoo import api, fields, models, modules, tools


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    m2o_model = fields.Many2one(
        comodel_name="ir.model",
        string="Code generator Model",
        help="Model related with this report",
        compute="_compute_m2os",
        store=True,
    )

    m2o_template = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Template",
        help="Template related with this report",
        compute="_compute_m2os",
    )

    @api.depends("model", "report_name")
    def _compute_m2os(self):
        for report in self:
            searched = self.env["ir.model"].search(
                [("model", "=", report.model.strip())]
            )
            if searched:
                report.m2o_model = searched[0].id

            stripped = report.report_name.strip()
            splitted = stripped.split(".")
            searched = self.env["ir.ui.view"].search(
                [
                    ("type", "=", "qweb"),
                    ("name", "=", splitted[len(splitted) - 1]),
                ]
            )
            if searched:
                report.m2o_template = searched[0].id
