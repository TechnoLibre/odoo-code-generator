from odoo import _, api, models, fields, SUPERUSER_ID


def pre_init_hook(cr):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        # Remove all website pages before installing data

        website_page_ids = env['website.page'].search([])
        website_menu_ids = env['website.menu'].search([])
        # TODO website doesn't support multi
        # website_page_ids.website_id = None
        # TODO replace by :
        for website_page in website_page_ids:
            website_page.website_id = None
        for website_menu in website_menu_ids:
            website_menu.website_id = None
