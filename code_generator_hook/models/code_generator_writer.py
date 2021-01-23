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
            # Specify root component
            self.code_generator_data.add_module_init_path('', f'from .hooks import {", ".join(lst_import)}')

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

        # Add constant
        if module.hook_constant_code:
            if module.enable_template_code_generator_demo:
                cw.emit("# TODO HUMAN: change my module_name to create a specific demo functionality")
            for line in module.hook_constant_code.split('\n'):
                cw.emit(line)

        def _add_hook(cw, hook_show, hook_code, hook_feature_gen_conf, post_init_hook_feature_code_generator,
                      uninstall_hook_feature_code_generator,
                      method_name, has_second_arg):
            if hook_show:
                cw.emit()
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
                    if post_init_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit()
                            cw.emit("# The path of the actual file")
                            cw.emit("# path_module_generate = os.path.normpath(os.path.join(os.path.dirname"
                                    "(__file__), '..'))")
                            cw.emit()
                            cw.emit('short_name = MODULE_NAME.replace("_", " ").title()')
                            cw.emit()
                            cw.emit("# Add code generator")
                            cw.emit("value = {")
                            with cw.indent():
                                cw.emit('"shortdesc": short_name,')
                                cw.emit("\"name\": MODULE_NAME,")
                                cw.emit("\"license\": \"AGPL-3\",")
                                cw.emit("\"author\": \"TechnoLibre\",")
                                cw.emit("\"website\": \"https://technolibre.ca\",")
                                cw.emit("\"application\": True,")
                                # with cw.block(before='"depends" :', delim=('[', '],')):
                                #     cw.emit('"code_generator",')
                                #     cw.emit('"code_generator_hook",')
                                cw.emit("\"enable_sync_code\": True,")
                                cw.emit("# \"path_sync_code\": path_module_generate,")
                            cw.emit("}")
                            cw.emit()
                            cw.emit("value[\"post_init_hook_show\"] = True")
                            cw.emit("value[\"uninstall_hook_show\"] = True")
                            cw.emit("value[\"post_init_hook_feature_code_generator\"] = True")
                            cw.emit("value[\"uninstall_hook_feature_code_generator\"] = True")
                            cw.emit("value[\"hook_constant_code\"] = f'MODULE_NAME = \"{MODULE_NAME}\"'")
                            cw.emit()
                            cw.emit("# TODO HUMAN: enable your functionality to generate")
                            cw.emit(f'value["enable_template_code_generator_demo"] = '
                                    f'{module.enable_template_code_generator_demo}')
                            cw.emit('value["enable_template_model"] = False')
                            cw.emit()
                            cw.emit("code_generator_id = env[\"code.generator.module\"].create(value)")
                            cw.emit()
                            cw.emit("# Add dependencies")
                            with cw.block(before='lst_depend =', delim=('[', ']')):
                                cw.emit("\"code_generator\",")
                                cw.emit("\"code_generator_hook\",")
                            cw.emit(
                                "lst_dependencies = env[\"ir.module.module\"].search([(\"name\", \"in\", lst_depend)])")
                            cw.emit("for depend in lst_dependencies:")
                            with cw.indent():
                                with cw.block(before='value =', delim=('{', '}')):
                                    cw.emit("\"module_id\": code_generator_id.id,")
                                    cw.emit("\"depend_id\": depend.id,")
                                    cw.emit("\"name\": depend.display_name,")
                                cw.emit("env[\"code.generator.module.dependency\"].create(value)")
                            cw.emit()
                            cw.emit("# Generate module")
                            cw.emit("value = {")
                            with cw.indent():
                                cw.emit("\"code_generator_ids\": code_generator_id.ids")
                            cw.emit("}")
                            cw.emit("code_generator_writer = env[\"code.generator.writer\"].create(value)")
                    if uninstall_hook_feature_code_generator:
                        with cw.indent():
                            cw.emit(
                                'code_generator_id = env["code.generator.module"].search([("name", "=", MODULE_NAME)])')
                            cw.emit('if code_generator_id:')
                            with cw.indent():
                                cw.emit('code_generator_id.unlink()')

        _add_hook(cw, module.pre_init_hook_show, module.pre_init_hook_code,
                  module.pre_init_hook_feature_general_conf, False, False, "pre_init_hook", False)
        _add_hook(cw, module.post_init_hook_show, module.post_init_hook_code,
                  module.post_init_hook_feature_general_conf, module.post_init_hook_feature_code_generator, False,
                  "post_init_hook", True)
        _add_hook(cw, module.uninstall_hook_show, module.uninstall_hook_code,
                  module.uninstall_hook_feature_general_conf, False, module.post_init_hook_feature_code_generator,
                  "uninstall_hook", True)

        hook_file_path = 'hooks.py'

        self.code_generator_data.write_file_str(hook_file_path, cw.render())

    def set_extra_get_lst_file_generate(self, module):
        super(CodeGeneratorWriter, self).set_extra_get_lst_file_generate(module)
        if module.pre_init_hook_show or module.post_init_hook_show or module.uninstall_hook_show:
            self._set_hook_file(module)
