from odoo import models, fields, api, modules, tools


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    comment = fields.Char(string="Comment", help="Hint about this record.")

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
