from odoo import api, fields, models, modules, tools


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    comment = fields.Char(help="Hint about this record.")

    # TODO this is wrong, use instead link to code_generator. Check _get_models_info from code_generator_module.py
    is_code_generator = fields.Boolean(
        compute="_compute_is_code_generator",
        store=True,
        help="Do a link with code generator to show associate actions server",
    )

    @api.depends("model_id")
    def _compute_is_code_generator(self):
        for rec in self:
            # TODO this is wrong, because it will show if multiple code.generator.module
            cgs = self.env["code.generator.module"].search([])
            if cgs:
                for cg in cgs:
                    model_ids = cg.o2m_models
                    if rec.model_id.id in model_ids.ids:
                        rec.is_code_generator = True

    @api.onchange("model_id", "state")
    def _onchange_model_id_state(self):
        if self.model_id.m2o_module and (
            self.state == "code" or self.state == "multi"
        ):
            result = dict()

            if self.state == "code":
                result.update(
                    dict(
                        value=dict(code="raise Warning('Not implemented yet')")
                    )
                )

            if not self.binding_model_id:
                result.update(
                    dict(
                        warning=dict(
                            title="Contextual action",
                            message=(
                                "Remember to create the contextual action..."
                            ),
                        )
                    )
                )

            return result

        elif self.model_id and self.state == "code":
            return dict(value=dict(code=self.DEFAULT_PYTHON_CODE))
