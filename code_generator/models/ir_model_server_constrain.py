import re

from odoo import models, fields, api, modules, tools, _
from odoo.exceptions import ValidationError
from odoo.addons.base.models.ir_model import SAFE_EVAL_BASE
from odoo.tools.safe_eval import safe_eval

CONSTRAINEDLS = _(
    "The field Constrained lists the fields that the server constrain will"
    " check. It is a comma-separated list of field names, like name, size."
)
SERVERCONSTRAIN = _("%s Server constrain ")
SYNTAXERRORMSG = _("There is a syntax error in your %scode definition.")

SAFE_EVAL_BASE["re"] = re
SAFE_EVAL_BASE["ValidationError"] = ValidationError

SAFE_EVAL_4FUNCTION = SAFE_EVAL_BASE
SAFE_EVAL_4FUNCTION["api"] = api
SAFE_EVAL_4FUNCTION["models"] = models
SAFE_EVAL_4FUNCTION["fields"] = fields
SAFE_EVAL_4FUNCTION["_"] = _
PREDEFINEDVARS = _(
    "You specified a non predefined variable. The predefined variables are"
    " self, datetime, dateutil, time, re, ValidationError and the ones"
    " accessible through self, like self.env."
)


def common_4constrains(el_self, code, message=SYNTAXERRORMSG):
    """

    :param el_self:
    :param code:
    :param message:
    :return:
    """

    try:
        safe_eval(code, SAFE_EVAL_4FUNCTION, {"self": el_self}, mode="exec")

    except ValueError:
        raise ValidationError(PREDEFINEDVARS)

    except SyntaxError:
        raise ValidationError(message)


class IrModelServerConstrain(models.Model):
    _name = "ir.model.server_constrain"
    _description = "Code Generator Model Server Constrains"
    _rec_name = "constrained"

    constrained = fields.Char(
        required=True,
        help="Constrained fields, ej: name, age",
    )

    m2o_ir_model = fields.Many2one(
        comodel_name="ir.model",
        string="Code generator Model",
        domain=[("transient", "=", False)],
        required=True,
        help="Model that will hold this server constrain",
        ondelete="cascade",
    )

    txt_code = fields.Text(
        string="Code",
        required=True,
        help="Code to execute",
    )

    @api.onchange("constrained")
    @api.constrains("constrained")
    def _check_constrained(self):
        if self.constrained:
            splitted = self.constrained.split(",")
            if list(
                filter(
                    lambda e: e.strip()
                    not in self.env[self.m2o_ir_model.model]._fields.keys(),
                    splitted,
                )
            ):
                raise ValidationError(CONSTRAINEDLS)

    @api.onchange("txt_code")
    @api.constrains("txt_code")
    def _check_txt_code(self):
        if self.txt_code:
            constrain_detail = SERVERCONSTRAIN % self.constrained
            common_4constrains(
                self.env[self.m2o_ir_model.model],
                self.txt_code,
                SYNTAXERRORMSG % constrain_detail,
            )
