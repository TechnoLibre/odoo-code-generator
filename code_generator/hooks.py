from odoo import _, api, models, fields, SUPERUSER_ID


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        system_user = env['res.users'].browse(2)
        system_user.groups_id = [(4, env.ref("code_generator.code_generator_manager").id, False)]
