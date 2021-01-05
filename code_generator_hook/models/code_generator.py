from odoo import models, fields, api, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = 'code.generator.module'

    # pre_init_hook
    pre_init_hook_show = fields.Boolean(string="Show pre_init_hook")

    pre_init_hook_feature_general_conf = fields.Boolean(
        string="General conf pre_init_hook",
        help="Add code to update general configurations on pre_init_hook.")

    pre_init_hook_code = fields.Text(string="Code of pre_init_hook", default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""")

    # post_init_hook
    post_init_hook_show = fields.Boolean(string="Show post_init_hook")

    post_init_hook_feature_general_conf = fields.Boolean(
        string="General conf post_init_hook",
        help="Add code to update general configurations on post_init_hook.")

    post_init_hook_code = fields.Text(string="Code of post_init_hook", default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""")

    # uninstall_hook
    uninstall_hook_show = fields.Boolean(string="Show uninstall_hook")

    uninstall_hook_feature_general_conf = fields.Boolean(
        string="General conf uninstall_hook",
        help="Add code to update general configurations on uninstall_hook.")

    uninstall_hook_code = fields.Text(string="Code of uninstall_hook", default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""")
