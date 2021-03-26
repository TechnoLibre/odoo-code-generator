import logging

from odoo import models, fields, api, _, tools

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = "ir.cron"

    m2o_module = fields.Many2one(
        "code.generator.module", string="Module", help="Module", ondelete="cascade"
    )

    force_use_datetime_installation = fields.Boolean(
        string="Force nextcall installation",
        help="Force to adapt update nextcall at installation datetime.",
    )

    ignore_threshold_time_upper = fields.Boolean(
        string="Keep all time",
        help="True will respect specific time without adding relative time"
        ", else ignore upper time then inverval_type.",
        default=True,
    )

    nextcall_template = fields.Char("NextCall function")
