from odoo import _, api, models, fields, SUPERUSER_ID

MODULE_NAME = "business_plan_import_pdf"
PDF_PATH = ""

def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        print("")