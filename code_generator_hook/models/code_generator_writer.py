from odoo import models, fields, api

from code_writer import CodeWriter
from odoo.models import MAGIC_COLUMNS

MAGIC_FIELDS = MAGIC_COLUMNS + ['display_name', '__last_update', 'access_url', 'access_token', 'access_warning', 'name']
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

    def _write_sync_template(self, module, model_model, cw, var_model_model, lst_keep_f2exports,
                             lst_force_f2exports=None):
        if lst_force_f2exports:
            f2exports = lst_force_f2exports
        else:
            f2exports = self.env["ir.model.fields"].search(
                [('model', '=', model_model), ('name', 'not in', MAGIC_FIELDS)])
        for field_id in f2exports:
            if not lst_force_f2exports and field_id.ttype == "one2many":
                # TODO refactor, simplify this with a struct
                lst_keep_f2exports.append((field_id, model_model, var_model_model))
                continue
            var_value_field_name = f"value_field_{field_id.name}"
            with cw.block(before=f"{var_value_field_name} =", delim=('{', '}')):
                cw.emit(f'"name": "{field_id.name}",')
                cw.emit(f'"model": "{model_model}",')
                cw.emit(f'"field_description": "{field_id.field_description}",')
                cw.emit(f'"ttype": "{field_id.ttype}",')
                if field_id.ttype in ["many2one", "many2many", "one2many"]:
                    cw.emit(f'"comodel_name": "{field_id.relation}",')
                    cw.emit(f'"relation": "{field_id.relation}",')
                    if field_id.ttype == "one2many":
                        field_many2one_ids = self.env["ir.model.fields"].search(
                            [('model', '=', field_id.relation), ('ttype', '=', 'many2one'),
                             ('name', 'not in', MAGIC_FIELDS)])
                        if len(field_many2one_ids) == 1:
                            cw.emit(f'"relation_field": "{field_many2one_ids.name}",')
                        else:
                            print("Error, cannot support this situation, where is the many2one?")
                elif field_id.ttype == "selection":
                    cw.emit(f'"selection": str(list()),')
                cw.emit(f'"model_id": {var_model_model}.id,')
            cw.emit(f'env["ir.model.fields"].create({var_value_field_name})')
            cw.emit()

        if lst_force_f2exports:
            lst_force_f2exports.clear()
        elif f2exports:
            cw.emit('# Hack to solve field name')
            cw.emit(f'field_x_name = env["ir.model.fields"].search([("model_id", "=", {var_model_model}.id), '
                    f'("name", "=", "x_name")])')
            cw.emit('field_x_name.name = "name"')
            cw.emit(f'{var_model_model}.rec_name = "name"')

    def _set_hook_file(self, module):
        """
        Function to set the module hook file
        :param module:
        :return:
        """

        cw = CodeWriter()
        lst_keep_f2exports = []

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
                            cw.emit("# TODO HUMAN: enable your functionality to generate")
                            if module.enable_template_code_generator_demo:
                                cw.emit('value["enable_template_code_generator_demo"] = '
                                        f'{module.enable_template_code_generator_demo}')
                                cw.emit('value["template_model_name"] = ""')
                                cw.emit('value["enable_template_wizard_view"] = False')
                            cw.emit(f'value["enable_sync_template"] = {module.enable_sync_template}')
                            cw.emit(f"value[\"post_init_hook_show\"] = {module.enable_template_code_generator_demo}")
                            cw.emit(f"value[\"uninstall_hook_show\"] = {module.enable_template_code_generator_demo}")
                            cw.emit("value[\"post_init_hook_feature_code_generator\"] = "
                                    f"{module.enable_template_code_generator_demo}")
                            cw.emit("value[\"uninstall_hook_feature_code_generator\"] = "
                                    f"{module.enable_template_code_generator_demo}")
                            cw.emit()
                            if module.enable_template_code_generator_demo:
                                cw.emit("new_module_name = MODULE_NAME")
                                cw.emit('if not value["enable_template_code_generator_demo"] and "code_generator_" '
                                        'in MODULE_NAME:')
                                with cw.indent():
                                    cw.emit('new_module_name = MODULE_NAME[len("code_generator_"):]')
                                    cw.emit('value["template_module_name"] = new_module_name')
                                cw.emit("value[\"hook_constant_code\"] = f'MODULE_NAME = \"{new_module_name}\"'")
                            else:
                                cw.emit("value[\"hook_constant_code\"] = f'MODULE_NAME = \"{MODULE_NAME}\"'")
                            cw.emit()
                            cw.emit("code_generator_id = env[\"code.generator.module\"].create(value)")
                            cw.emit()
                            if module.dependencies_id:
                                cw.emit("# Add dependencies")
                                cw.emit("# TODO HUMAN: update your dependencies")
                                with cw.block(before='lst_depend =', delim=('[', ']')):
                                    for depend in module.dependencies_id:
                                        cw.emit(f'"{depend.depend_id.name}",')
                                cw.emit("lst_dependencies = env[\"ir.module.module\"]"
                                        ".search([(\"name\", \"in\", lst_depend)])")
                                cw.emit("for depend in lst_dependencies:")
                                with cw.indent():
                                    with cw.block(before='value =', delim=('{', '}')):
                                        cw.emit("\"module_id\": code_generator_id.id,")
                                        cw.emit("\"depend_id\": depend.id,")
                                        cw.emit("\"name\": depend.display_name,")
                                    cw.emit("env[\"code.generator.module.dependency\"].create(value)")
                                cw.emit()
                            if module.template_model_name:
                                lst_model = module.template_model_name.split(";")
                                len_model = len(lst_model)
                                i = -1
                                for model_model in lst_model:
                                    i += 1
                                    model_name = model_model.replace(".", "_")
                                    title_model_model = model_name.replace("_", " ").title()
                                    variable_model_model = f"model_{model_name}"
                                    cw.emit(f"# Add {title_model_model}")
                                    cw.emit("value = {")
                                    with cw.indent():
                                        cw.emit(f"\"name\": \"{model_name}\",")
                                        cw.emit(f"\"model\": \"{model_model}\",")
                                        cw.emit("\"m2o_module\": code_generator_id.id,")
                                        cw.emit("\"rec_name\": None,")
                                        cw.emit("\"nomenclator\": True,")
                                    cw.emit("}")
                                    cw.emit(f"{variable_model_model} = env[\"ir.model\"].create(value)")
                                    cw.emit("")
                                    cw.emit("##### Begin Field")
                                    if module.enable_sync_template:
                                        self._write_sync_template(module, model_model, cw, variable_model_model,
                                                                  lst_keep_f2exports)
                                    else:
                                        cw.emit("value_field_boolean = {")
                                        with cw.indent():
                                            cw.emit("\"name\": \"field_boolean\",")
                                            cw.emit("\"model\": \"demo.model\",")
                                            cw.emit("\"field_description\": \"field description\",")
                                            cw.emit("\"ttype\": \"boolean\",")
                                            cw.emit(f"\"model_id\": {variable_model_model}.id,")
                                        cw.emit("}")
                                        cw.emit("env[\"ir.model.fields\"].create(value_field_boolean)")
                                        cw.emit()
                                        cw.emit("# FIELD TYPE Many2one")
                                        cw.emit("#value_field_many2one = {")
                                        with cw.indent():
                                            cw.emit("#\"name\": \"field_many2one\",")
                                            cw.emit("#\"model\": \"demo.model\",")
                                            cw.emit("#\"field_description\": \"field description\",")
                                            cw.emit("#\"ttype\": \"many2one\",")
                                            cw.emit('#"comodel_name": "model.name",')
                                            cw.emit('#"relation": "model.name",')
                                            cw.emit(f"#\"model_id\": {variable_model_model}.id,")
                                        cw.emit("#}")
                                        cw.emit("#env[\"ir.model.fields\"].create(value_field_many2one)")
                                        cw.emit("")
                                        cw.emit("# Hack to solve field name")
                                        cw.emit("field_x_name = env[\"ir.model.fields\"].search([('model_id', '=', "
                                                f"{variable_model_model}.id), ('name', '=', 'x_name')])")
                                        cw.emit("field_x_name.name = \"name\"")
                                        cw.emit(f"{variable_model_model}.rec_name = \"name\"")
                                        cw.emit("")
                                    if i >= len_model - 1 and lst_keep_f2exports:
                                        cw.emit("")
                                        cw.emit("# Added one2many field, many2many need to be creat before add "
                                                "one2many")
                                        for field_id, model_model, variable_model_model in lst_keep_f2exports:
                                            # Finish to print one2many move at the end
                                            self._write_sync_template(module, model_model, cw, variable_model_model,
                                                                      lst_keep_f2exports,
                                                                      lst_force_f2exports=[field_id])
                                    cw.emit("##### End Field")
                                    cw.emit()
                                    # TODO add data nomenclator, research data from model
                                    # TODO By default, no data will be nomenclator
                                    # cw.emit("# Add data nomenclator")
                                    # cw.emit("value = {")
                                    # with cw.indent():
                                    #     cw.emit("\"field_boolean\": True,")
                                    #     cw.emit("\"name\": \"demo\",")
                                    # cw.emit("}")
                                    # cw.emit(f"env[\"{model_model}\"].create(value)")
                                    # cw.emit()
                            if module.enable_template_wizard_view:
                                cw.emit("# Generate view")
                                cw.emit("wizard_view = env['code.generator.generate.views.wizard'].create({")
                                with cw.indent():
                                    cw.emit("'code_generator_id': code_generator_id.id,")
                                    cw.emit("'enable_generate_all': False,")
                                    cw.emit("'enable_generate_portal': True,")
                                cw.emit("})")
                                cw.emit("")
                                cw.emit("wizard_view.button_generate_views()")
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
