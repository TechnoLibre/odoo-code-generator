from odoo import api, fields, models, modules, tools


class CodeGeneratorModule(models.Model):
    _inherit = "code.generator.module"

    # TODO rename variable with hook_*
    hook_constant_code = fields.Text(
        string="Code constant", help="Code in the begin of hook file."
    )

    # pre_init_hook
    pre_init_hook_show = fields.Boolean(string="Show pre_init_hook")

    pre_init_hook_feature_general_conf = fields.Boolean(
        string="General conf pre_init_hook",
        help="Add code to update general configurations on pre_init_hook.",
    )

    pre_init_hook_code = fields.Text(
        string="Code of pre_init_hook",
        default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""",
    )

    # post_init_hook
    post_init_hook_show = fields.Boolean(string="Show post_init_hook")

    post_init_hook_feature_general_conf = fields.Boolean(
        string="General conf post_init_hook",
        help="Add code to update general configurations on post_init_hook.",
    )

    post_init_hook_feature_code_generator = fields.Boolean(
        string="Code generator post_init_hook",
        help="Add code to use the code generator on post_init_hook.",
    )

    post_init_hook_code = fields.Text(
        string="Code of post_init_hook",
        default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""",
    )

    # uninstall_hook
    uninstall_hook_show = fields.Boolean(string="Show uninstall_hook")

    uninstall_hook_feature_general_conf = fields.Boolean(
        string="General conf uninstall_hook",
        help="Add code to update general configurations on uninstall_hook.",
    )

    uninstall_hook_code = fields.Text(
        string="Code of uninstall_hook",
        default="""with api.Environment.manage():
    env = api.Environment(cr, SUPERUSER_ID, {})""",
    )

    uninstall_hook_feature_code_generator = fields.Boolean(
        string="Code generator uninstall_hook",
        help="Add code to use the code generator on uninstall_hook.",
    )

    # Functionality
    enable_template_code_generator_demo = fields.Boolean(
        string="Functions code generator demo",
        help=(
            "Support help to use code generator with functionality variables."
        ),
    )

    enable_template_wizard_view = fields.Boolean(
        string="Template wizard", help="Add template wizard."
    )

    force_generic_template_wizard_view = fields.Boolean(
        string="Force template wizard",
        help="Use default value to generate template wizard.",
    )

    disable_generate_access = fields.Boolean(
        help="Disable the writing access.",
    )

    enable_cg_generate_portal = fields.Boolean(
        string="Wizard enable code generator portal",
        help="Add template of portal to wizard.",
    )

    enable_generate_portal = fields.Boolean(
        string="Wizard enable portal", help="Add template of portal to wizard."
    )

    enable_cg_portal_enable_create = fields.Boolean(
        help="Template will generate 'portal_enable_create'."
    )

    enable_template_website_snippet_view = fields.Boolean(
        string="Template website snippet",
        help=(
            "Add template website snippet, block drag and drop in "
            "website builder."
        ),
    )

    enable_sync_template = fields.Boolean(
        string="Sync generated code",
        help="Read generated code to fill the generator with fields.",
    )

    disable_fix_code_generator_sequence = fields.Boolean(
        string="Disable fix sequence",
        help=(
            "Don't force sequence of model in view, if True, always auto mode."
        ),
    )

    ignore_fields = fields.Char(
        string="Ignored field",
        help=(
            "Ignore field when enable_sync_template, use ; to separate field."
        ),
    )

    template_module_path_generated_extension = fields.Char(
        string="Path of os.path value to generated path module",
        help="Add parameters of os.path directory where module is generated.",
        default=".",
    )

    template_generate_website_snippet_type = fields.Char(
        help="Choose content,effect,feature,structure",
        default="effect",
    )

    template_generate_website_snippet_generic_model = fields.Char(
        string="website snippet feature with generic model",
        help=(
            "Separate model name by ';' to create a list. Will generate field"
            " of all this model."
        ),
    )
