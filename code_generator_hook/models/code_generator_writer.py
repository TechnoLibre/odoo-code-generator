from odoo import models, fields, api

from code_writer import CodeWriter

BREAK_LINE = ['\n']
FROM_ODOO_IMPORTS_SUPERUSER = ['from odoo import _, api, models, fields, SUPERUSER_ID']
MODEL_SUPERUSER_HEAD = FROM_ODOO_IMPORTS_SUPERUSER + BREAK_LINE


class CodeGeneratorWriter(models.Model):
    _inherit = 'code.generator.writer'

    def set_module_init_file_extra(self, module):
        super(CodeGeneratorWriter, self).set_module_init_file_extra(module)
        if module.pre_init_hook_show or module.post_init_hook_show or module.uninstall_hook_show:
            lst_import = []
            if module.pre_init_hook_show:
                lst_import.append("pre_init_hook")
            if module.post_init_hook_show:
                lst_import.append("post_init_hook")
            if module.uninstall_hook_show:
                lst_import.append("uninstall_hook")
            self.code_generator_data.add_module_init_path(f'from .hooks import {", ".join(lst_import)}')

    def set_manifest_file_extra(self, cw, module):
        super(CodeGeneratorWriter, self).set_manifest_file_extra(cw, module)
        if module.pre_init_hook_show:
            cw.emit(f"'pre_init_hook': 'pre_init_hook',")

        if module.post_init_hook_show:
            cw.emit(f"'post_init_hook': 'post_init_hook',")

        if module.uninstall_hook_show:
            cw.emit(f"'uninstall_hook': 'uninstall_hook',")

    def _set_hook_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()

        for line in MODEL_SUPERUSER_HEAD:
            str_line = line.strip()
            cw.emit(str_line)

        def _add_hook(cw, hook_show, hook_code, hook_feature_gen_conf, method_name, has_second_arg):
            if hook_show:
                cw.emit()
                if has_second_arg:
                    cw.emit(f'def {method_name}(cr, e):')
                else:
                    cw.emit(f'def {method_name}(cr):')
                with cw.indent():
                    for line in hook_code.split("\n"):
                        cw.emit(line)
                    if hook_feature_gen_conf:
                        with cw.indent():
                            cw.emit("# General configuration")
                            with cw.block(before="values =", delim=('{', '}')):
                                pass

                            cw.emit("event_config = env['res.config.settings'].sudo().create(values)")
                            cw.emit("event_config.execute()")
                cw.emit()

        _add_hook(cw, module.pre_init_hook_show, module.pre_init_hook_code,
                  module.pre_init_hook_feature_general_conf, "pre_init_hook", False)
        _add_hook(cw, module.post_init_hook_show, module.post_init_hook_code,
                  module.post_init_hook_feature_general_conf, "post_init_hook", True)
        _add_hook(cw, module.uninstall_hook_show, module.uninstall_hook_code,
                  module.uninstall_hook_feature_general_conf, "uninstall_hook", True)

        hook_file_path = 'hooks.py'

        self.code_generator_data.write_file_str(hook_file_path, cw.render())

    def set_extra_get_lst_file_generate(self, module):
        super(CodeGeneratorWriter, self).set_extra_get_lst_file_generate(module)
        if module.pre_init_hook_show or module.post_init_hook_show or module.uninstall_hook_show:
            self._set_hook_file(module)
