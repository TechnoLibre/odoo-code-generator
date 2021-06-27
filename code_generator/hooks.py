from odoo import _, api, models, fields, SUPERUSER_ID, tools


def post_init_hook(cr, e):
    if not tools.config["dev_mode"]:
        raise Exception(
            _(
                "Cancel installation module code_generator, please specify"
                " --dev [options] in your instance."
            )
        )

    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        system_user = env["res.users"].browse(2)
        system_user.groups_id = [
            (4, env.ref("code_generator.code_generator_manager").id, False)
        ]
