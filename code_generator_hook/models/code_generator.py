from odoo import models, fields, api, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = 'code.generator.module'

    # TODO rename variable with hook_*
    hook_constant_code = fields.Text(string="Code constant", help="Code in the begin of hook file.")

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

    post_init_hook_feature_code_generator = fields.Boolean(
        string="Code generator post_init_hook",
        help="Add code to use the code generator on post_init_hook.")

    post_init_hook_code = fields.Text(string="Code of post_init_hook", default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""")

    # uninstall_hook
    uninstall_hook_show = fields.Boolean(string="Show uninstall_hook")

    uninstall_hook_feature_general_conf = fields.Boolean(
        string="General conf uninstall_hook",
        help="Add code to update general configurations on uninstall_hook.")

    uninstall_hook_code = fields.Text(string="Code of uninstall_hook", default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""")

    uninstall_hook_feature_code_generator = fields.Boolean(
        string="Code generator uninstall_hook", help="Add code to use the code generator on uninstall_hook.")

    # Functionality
    enable_template_code_generator_demo = fields.Boolean(string="Functions code generator demo",
                                                         help="Support help to use code generator "
                                                              "with functionality variables.")

    template_model_name = fields.Char(string="Functions models", help="Add model from list, separate by ';' and "
                                                                      "generate template.")

    enable_template_wizard_view = fields.Boolean(string="Template wizard", help="Add template wizard.")
