# -*- coding: utf-8 -*-

import base64

from odoo import api, models, fields, tools
from odoo.modules import get_module_resource

from enhanced_crud.models.enhanced_crud import CURRENTTARGETDOMAIN

dom_IrActionsActWindow = CURRENTTARGETDOMAIN + [('limit', '!=', 0)]


class EnhancedCrudConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    boo_apply2any = fields.Boolean(
        string='Global application',
        help='Global application',
        config_parameter='enhanced_crud.boo_apply2any'
    )

    s_pagination = fields.Selection(
        string='Pagination',
        help='Pagination',
        selection=[('5', '5'), ('10', '10'), ('20', '20'), ('40', '40'), ('80', '80'), ('100', '100')],
        default='80',
        config_parameter='enhanced_crud.s_pagination'
    )

    s_window_disposition = fields.Selection(
        string='Window disposition',
        help='Window disposition',
        selection=[('new', 'New Window (only available for now)')],  # ('current', 'Current Window'),
        default='new',
        config_parameter='enhanced_crud.s_window_disposition',
        readonly=True
    )

    @api.onchange('s_window_disposition')
    def _onchange_s_window_disposition(self):
        if self.s_window_disposition:
            image_name = 'enhanced_crud_screenshot.png' if self.s_window_disposition == 'new' else \
                'window_disposition_current.png'
            image_path = get_module_resource('enhanced_crud', 'static/src/img', image_name)
            self.img_window_disposition = tools.image_resize_image_big(base64.b64encode(open(image_path, 'rb').read()))

    @api.model
    def _default_image(self):
        image_path = get_module_resource('enhanced_crud', 'static/src/img', 'enhanced_crud_screenshot.png')
        return tools.image_resize_image_big(base64.b64encode(open(image_path, 'rb').read()))

    img_window_disposition = fields.Binary(
        'Enhanced CRUD window disposition photo',
        default=_default_image,
        attachment=True,
        help='This field holds the image used as photo for the employee, limited to 1024x1024px.',
        readonly=True
    )
    img_window_disposition_medium = fields.Binary(
        'Medium-sized Enhanced CRUD window disposition photo',
        attachment=True,
        help='Medium-sized photo of the employee. '
             'It is automatically resized as a 128x128px image, with aspect ratio preserved. '
             'Use this field in form views or some kanban views.'
    )

    img_window_disposition_small = fields.Binary(
        'Small-sized Enhanced CRUD window disposition photo',
        attachment=True,
        help='Small-sized photo of the employee. '
             'It is automatically resized as a 64x64px image, with aspect ratio preserved. '
             'Use this field anywhere a small image is required.'
    )

    boo_can_edit_pager = fields.Boolean(
        string='Pager "Can edit" variable',
        help='Pager "Can edit" variable',
        config_parameter='enhanced_crud.boo_can_edit_pager'
    )

    boo_on_formdiscarded = fields.Boolean(
        string='Changes confirmation on form discarded',
        help='Changes confirmation on form discarded',
        config_parameter='enhanced_crud.boo_on_formdiscarded'
    )

    boo_contextmenu = fields.Boolean(
        string='Context Menu',
        help='Context Menu',
        config_parameter='enhanced_crud.boo_contextmenu'
    )

    @api.multi
    def execute(self):

        self.env['ir.actions.act_window'].search(dom_IrActionsActWindow).write(dict(limit=self.s_pagination or 80))

        return super(EnhancedCrudConfigSettings, self).execute()
