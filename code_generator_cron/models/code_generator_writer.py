from odoo import models, fields, api

import os
from lxml.builder import E
from lxml import etree as ET

BREAK_LINE_OFF = "\n"
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF


class CodeGeneratorWriter(models.Model):
    _inherit = "code.generator.writer"

    def _set_model_py_file(self, module, model, model_model):
        if not model.o2m_codes and module.o2m_model_cron:
            key = "model."
            if module.o2m_model_cron.code.startswith(key):
                function_name = module.o2m_model_cron.code[len(key) : -2]
                value = {
                    "code": '''"""TODO what to run"""
return''',
                    "name": function_name,
                    "decorator": "@api.model",
                    "param": "",
                    "m2o_module": module.id,
                    "m2o_model": model.id,
                }
                self.env["code.generator.model.code"].create(value)
        super(CodeGeneratorWriter, self)._set_model_py_file(module, model, model_model)

    def _write_generated_template(self, module, model_model, cw):
        super(CodeGeneratorWriter, self)._write_generated_template(module, model_model, cw)
        if module.enable_cron_template:
            cw.emit("##### Cron")
            name = "Backup Scheduler"
            with cw.block(before="value =", delim=("{", "}")):
                cw.emit('"m2o_module": code_generator_id.id,')
                cw.emit(f'"name": "{name}",')
                cw.emit("\"user_id\": env.ref('base.user_root').id,")
                cw.emit('"interval_number": 1,')
                cw.emit('"interval_type": "days",')
                cw.emit('"numbercall": -1,')
                cw.emit(
                    '"nextcall_template": "(datetime.now() + timedelta(days=1)).strftime(\'%Y-%m-%d 03:00:00\')",'
                )
                cw.emit('"model_id": model_db_backup.id,')
                cw.emit('"state": "code",')
                cw.emit('"code": "model.action_backup_all()",')
            cw.emit('env["ir.cron"].create(value)')
            cw.emit()
            cw.emit("# action_backup_all function cron")
            with cw.block(before="value =", delim=("{", "}")):
                cw.emit('"code": \'\'\'"""Run all scheduled backups."""')
                cw.emit_raw("return self.search([]).action_backup()''',\n")
                cw.emit('"name": "action_backup_all",')
                cw.emit('"decorator": "@api.model",')
                cw.emit('"param": "",')
                cw.emit('"m2o_module": code_generator_id.id,')
                cw.emit('"m2o_model": model_db_backup.id,')
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
        for cron in module.o2m_model_cron:
            i += 1

            model_id_name = self._get_ir_model_data(cron.model_id, give_a_default=True)
            if model_id_name.startswith("ir_"):
                model_id_name = model_id_name[3:]

            lst_field = [
                E.field({"name": "name"}, cron.name),
                E.field(
                    {
                        "name": "user_id",
                        "ref": self._get_ir_model_data(cron.user_id, give_a_default=True),
                    }
                ),
                E.field({"name": "interval_number"}, str(cron.interval_number)),
                E.field({"name": "interval_type"}, cron.interval_type),
                E.field({"name": "numbercall"}, str(cron.numbercall)),
                E.field({"name": "model_id", "ref": model_id_name}),
                E.field({"name": "state"}, cron.state),
                E.field({"name": "code"}, cron.code),
            ]

            if cron.nextcall_template:
                nextcall_field = cron.nextcall_template
                lst_field.append(E.field({"name": "nextcall", "eval": nextcall_field}))
            elif not cron.ignore_threshold_time_upper:
                if cron.interval_type == "months":
                    str_timedelta = f"relativedelta({cron.interval_type}={cron.interval_number})"
                else:
                    str_timedelta = f"timedelta({cron.interval_type}={cron.interval_number})"
                if not cron.force_use_datetime_installation:
                    if cron.interval_type == "months":
                        # Check if per years
                        if not cron.interval_number % 12:
                            timestamp = f"%Y-{cron.nextcall.strftime('%m-%d %H:%M:%S')}"
                        else:
                            timestamp = f"%Y-%m-{cron.nextcall.strftime('%d %H:%M:%S')}"
                    elif cron.interval_type == "weeks":
                        timestamp = f"%Y-%m-%d {cron.nextcall.strftime('%H:%M:%S')}"
                    elif cron.interval_type == "days":
                        timestamp = f"%Y-%m-%d {cron.nextcall.strftime('%H:%M:%S')}"
                    elif cron.interval_type == "hours":
                        timestamp = f"%Y-%m-%d %H:{cron.nextcall.strftime('%M:%S')}"
                    elif cron.interval_type == "minutes":
                        timestamp = f"%Y-%m-%d %H:%M:{cron.nextcall.strftime('%S')}"
                else:
                    timestamp = "%Y-%m-%d %H:%M:%S"

                nextcall_field = f"(datetime.now() + {str_timedelta}).strftime('{timestamp}')"
                lst_field.append(E.field({"name": "nextcall", "eval": nextcall_field}))
            else:
                lst_field.append(
                    E.field({"name": "nextcall"}, cron.nextcall.strftime("%Y-%m-%d %H:%M:%S"))
                )

            record_xml = E.record({"model": "ir.cron", "id": f"ir_cron_{i}"}, *lst_field)
            lst_record_xml.append(record_xml)

        module_file = E.odoo({}, *lst_record_xml)
        data_file_path = os.path.join(self.code_generator_data.data_path, "ir_cron.xml")
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(module_file, pretty_print=True)
        self.code_generator_data.write_file_binary(data_file_path, result, data_file=True)
