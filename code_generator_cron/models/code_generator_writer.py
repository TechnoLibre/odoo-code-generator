import os

from lxml import etree as ET
from lxml.builder import E

from odoo import api, fields, models

BREAK_LINE_OFF = "\n"
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def _set_model_py_file(self, module, model, model_model):
        key = "model."
        if module.o2m_model_cron and module.o2m_model_cron.code.startswith(
            key
        ):
            function_name = module.o2m_model_cron.code[len(key) : -2]
            items = self.env["code.generator.model.code"].search(
                [
                    ("name", "=", function_name),
                    ("m2o_model", "=", model.model),
                    ("m2o_module", "=", module.id),
                ]
            )
            if not items:
                value = {
                    "code": '''"""TODO what to run"""
return''',
                    "name": function_name,
                    "decorator": "@api.model",
                    "param": "self",
                    "m2o_module": module.id,
                    "m2o_model": model.id,
                }
                self.env["code.generator.model.code"].create(value)
        super(CodeGeneratorWriter, self)._set_model_py_file(
            module, model, model_model
        )

    def _write_generated_template(self, module, model_model, cw):
        super(CodeGeneratorWriter, self)._write_generated_template(
            module, model_model, cw
        )
        act_server_ids = self.env["ir.actions.server"].search(
            [
                ("model_name", "=", model_model),
                ("usage", "=", "ir_cron"),
            ]
        )
        if module.template_module_id and act_server_ids:
            for act_server_id in act_server_ids:
                var_model_id = (
                    f"model_{act_server_id.model_name.replace('.', '_')}"
                )
                ir_cron_ids = self.env["ir.cron"].search(
                    [("ir_actions_server_id", "=", act_server_id.id)]
                )
                for ir_cron_id in ir_cron_ids:
                    ir_model_data_id = self.env["ir.model.data"].search(
                        [
                            ("model", "=", "ir.cron"),
                            ("res_id", "=", ir_cron_id.id),
                        ]
                    )
                    if ir_model_data_id:
                        cron_id_name_var = f'"{ir_model_data_id.name}"'
                    else:
                        cron_id_name_var = "cron_id.name"
                    code_name = (
                        ir_cron_id.code
                        if not ir_cron_id.code.startswith("model.")
                        else ir_cron_id.code[6:-2]
                    )
                    self._write_cron(
                        cw,
                        model_model,
                        module,
                        name=ir_cron_id.name,
                        user_id_ref=self._get_ir_model_data(
                            ir_cron_id.user_id, module_name=module.name
                        ),
                        interval_number=ir_cron_id.interval_number,
                        interval_type=ir_cron_id.interval_type,
                        numbercall=ir_cron_id.numbercall,
                        nextcall_template=self._process_nextcall(ir_cron_id),
                        var_model_id=var_model_id,
                        state=ir_cron_id.state,
                        code=ir_cron_id.code,
                        cron_id_name_var=cron_id_name_var,
                        code_name=code_name,
                    )
        elif module.enable_cron_template:
            self._write_cron(cw, model_model, module)

    def _write_cron(
        self,
        cw,
        model_model,
        module,
        name="Backup Scheduler",
        user_id_ref="base.user_root",
        interval_number=1,
        interval_type="days",
        numbercall=-1,
        nextcall_template="(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d 03:00:00')",
        var_model_id="model_db_backup",
        state="code",
        code="model.action_backup_all()",
        cron_id_name_var="cron_id.name",
        code_name="action_backup_all",
    ):
        cw.emit("##### Cron")
        with cw.block(
            before="cron_id = env['ir.cron'].search(",
            delim=("[", "]"),
            after=")",
        ):
            cw.emit(f'("name", "=", "{name}"),')
            cw.emit(f'("user_id", "=", env.ref(\'{user_id_ref}\').id),')
            cw.emit(f'("interval_number", "=", {interval_number}),')
            cw.emit(f'("interval_type", "=", "{interval_type}"),')
            cw.emit(f'("numbercall", "=", {numbercall}),')
            cw.emit(f'("nextcall_template" , "=", "{nextcall_template}"),')
            cw.emit(f'("model_id", "=", {var_model_id}.id),')
            cw.emit(f'("state", "=", "{state}"),')
            cw.emit(f'("code", "=", "{code}"),')
        cw.emit("if not cron_id:")
        with cw.indent():
            with cw.block(before="value =", delim=("{", "}")):
                cw.emit('"m2o_module": code_generator_id.id,')
                cw.emit(f'"name": "{name}",')
                cw.emit(f"\"user_id\": env.ref('{user_id_ref}').id,")
                cw.emit(f'"interval_number": {interval_number},')
                cw.emit(f'"interval_type": "{interval_type}",')
                cw.emit(f'"numbercall": {numbercall},')
                cw.emit(f'"nextcall_template": "{nextcall_template}",')
                cw.emit(f'"model_id": {var_model_id}.id,')
                cw.emit(f'"state": "{state}",')
                cw.emit(f'"code": "{code}",')
            cw.emit('cron_id = env["ir.cron"].create(value)')
        cw.emit()

        with cw.block(
            before="cron_id_name_id = env['ir.model.data'].search(",
            delim=("[", "]"),
            after=")",
        ):
            cw.emit(f'("name", "=", {cron_id_name_var}),')
            cw.emit(f'("model", "=", "ir.cron"),')
            cw.emit(f'("module", "=", MODULE_NAME),')
            cw.emit(f'("res_id", "=", cron_id.id),')
            cw.emit(f'("noupdate", "=", True),')

        cw.emit("if not cron_id_name_id:")
        with cw.indent():
            with cw.block(
                before="cron_id_name_id = env['ir.model.data'].search(",
                delim=("[", "]"),
                after=")",
            ):
                cw.emit(f'("name", "=", {cron_id_name_var}),')
                cw.emit(f'("model", "=", "ir.cron"),')
                cw.emit(f'("module", "=", MODULE_NAME),')
                cw.emit(f'("noupdate", "=", True),')
            cw.emit("if cron_id_name_id:")
            with cw.indent():
                cw.emit("# cron exist but his id is not associate")
                cw.emit("cron_id_name_id.res_id = cron_id.id")
            cw.emit("else:")
            with cw.indent():
                with cw.block(before="value =", delim=("{", "}")):
                    cw.emit(f'"name": {cron_id_name_var},')
                    cw.emit(f'"model": "ir.cron",')
                    cw.emit(f'"module": MODULE_NAME,')
                    cw.emit(f'"res_id": cron_id.id,')
                    cw.emit(f'"noupdate": True,')
                cw.emit('env["ir.model.data"].create(value)')
        cw.emit()
        code_ids = self.env["code.generator.model.code"].search(
            [
                ("name", "=", code_name),
                ("m2o_model", "=", model_model),
                ("m2o_module", "=", module.id),
            ]
        )
        if not code_ids:
            cw.emit(f"# {code_name} function cron")
            with cw.block(before="value =", delim=("{", "}")):
                # TODO create code if not exist and move this code above all code
                # TODO add code in code generator to be create later
                # TODO refactor this code from code memory
                cw.emit('"code": \'\'\'"""Run all scheduled backups."""')
                cw.emit_raw("return self.search([]).action_backup()''',\n")
                cw.emit(f'"name": "{code_name}",')
                cw.emit('"decorator": "@api.model",')
                cw.emit('"param": "self",')
                cw.emit('"m2o_module": code_generator_id.id,')
                cw.emit(f'"m2o_model": {var_model_id}.id,')
            cw.emit('env["code.generator.model.code"].create(value)')
        cw.emit()

    def set_xml_data_file(self, module):
        super(CodeGeneratorWriter, self).set_xml_data_file(module)
        if not module.o2m_model_cron:
            return

        #
        # Cron
        #
        lst_record_xml = []
        i = -1
        for ir_cron_id in module.o2m_model_cron:
            i += 1

            model_id_name = self._get_ir_model_data(
                ir_cron_id.model_id,
                give_a_default=True,
                module_name=module.name,
            )
            if model_id_name.startswith("ir_"):
                model_id_name = model_id_name[3:]

            lst_field = [
                E.field({"name": "name"}, ir_cron_id.name),
                E.field(
                    {
                        "name": "user_id",
                        "ref": self._get_ir_model_data(
                            ir_cron_id.user_id,
                            give_a_default=True,
                            module_name=module.name,
                        ),
                    }
                ),
                E.field(
                    {"name": "interval_number"},
                    str(ir_cron_id.interval_number),
                ),
                E.field({"name": "interval_type"}, ir_cron_id.interval_type),
                E.field({"name": "numbercall"}, str(ir_cron_id.numbercall)),
                E.field({"name": "model_id", "ref": model_id_name}),
                E.field({"name": "state"}, ir_cron_id.state),
                E.field({"name": "code"}, ir_cron_id.code),
            ]

            if ir_cron_id.nextcall_template:
                nextcall_field = ir_cron_id.nextcall_template
                lst_field.append(
                    E.field({"name": "nextcall", "eval": nextcall_field})
                )
            elif not ir_cron_id.ignore_threshold_time_upper:
                nextcall_field = self._process_nextcall(ir_cron_id)
                lst_field.append(
                    E.field({"name": "nextcall", "eval": nextcall_field})
                )
            else:
                lst_field.append(
                    E.field(
                        {"name": "nextcall"},
                        ir_cron_id.nextcall.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )

            model_data_id = self.env["ir.model.data"].search(
                [
                    ("model", "=", "ir.cron"),
                    ("module", "=", module.name),
                    ("res_id", "=", ir_cron_id.id),
                ]
            )
            if model_data_id:
                str_id = model_data_id.name
            else:
                str_id = f"ir_cron_{module.name}_{i}"
            record_xml = E.record(
                {"model": "ir.cron", "id": str_id}, *lst_field
            )
            lst_record_xml.append(record_xml)

        # TODO need to separate noupdate cron_id to no noupdate, different group
        odoo_data = {} if not model_data_id.noupdate else {"noupdate": "1"}
        module_file = E.odoo(odoo_data, *lst_record_xml)
        data_file_path = os.path.join(
            self.code_generator_data.data_path, "ir_cron.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_file, pretty_print=True
        )
        self.code_generator_data.write_file_binary(
            data_file_path, result, data_file=True
        )

    @staticmethod
    def _process_nextcall(ir_cron_id):
        """
        Recreate nextcall_template
        :param ir_cron_id:
        :return: new nextcall in string
        """
        if ir_cron_id.interval_type == "months":
            str_timedelta = f"relativedelta({ir_cron_id.interval_type}={ir_cron_id.interval_number})"
        else:
            str_timedelta = f"timedelta({ir_cron_id.interval_type}={ir_cron_id.interval_number})"
        if not ir_cron_id.force_use_datetime_installation:
            if ir_cron_id.interval_type == "months":
                # Check if per years
                if not ir_cron_id.interval_number % 12:
                    timestamp = (
                        f"%Y-{ir_cron_id.nextcall.strftime('%m-%d %H:%M:%S')}"
                    )
                else:
                    timestamp = (
                        f"%Y-%m-{ir_cron_id.nextcall.strftime('%d %H:%M:%S')}"
                    )
            elif ir_cron_id.interval_type == "weeks":
                timestamp = (
                    f"%Y-%m-%d {ir_cron_id.nextcall.strftime('%H:%M:%S')}"
                )
            elif ir_cron_id.interval_type == "days":
                timestamp = (
                    f"%Y-%m-%d {ir_cron_id.nextcall.strftime('%H:%M:%S')}"
                )
            elif ir_cron_id.interval_type == "hours":
                timestamp = (
                    f"%Y-%m-%d %H:{ir_cron_id.nextcall.strftime('%M:%S')}"
                )
            elif ir_cron_id.interval_type == "minutes":
                timestamp = (
                    f"%Y-%m-%d %H:%M:{ir_cron_id.nextcall.strftime('%S')}"
                )
        else:
            timestamp = "%Y-%m-%d %H:%M:%S"
        nextcall_field = (
            f"(datetime.now() + {str_timedelta}).strftime('{timestamp}')"
        )
        return nextcall_field
