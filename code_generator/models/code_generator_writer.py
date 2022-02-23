import ast
import base64
import glob
import io
import logging
import os
import shutil
import tempfile
import uuid
from collections import defaultdict

import unidecode
from code_writer import CodeWriter
from lxml import etree as ET
from lxml.builder import E
from PIL import Image

from odoo import api, fields, models
from odoo.models import MAGIC_COLUMNS
from odoo.tools.misc import mute_logger

from ..code_generator_data import CodeGeneratorData
from ..extractor_controller import ExtractorController
from ..extractor_module import ExtractorModule
from ..extractor_view import ExtractorView
from ..python_controller_writer import PythonControllerWriter

_logger = logging.getLogger(__name__)

UNDEFINEDMESSAGE = "Restriction message not yet define."
MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]
MODULE_NAME = "code_generator"
BLANK_LINE = [""]
BREAK_LINE_OFF = "\n"
BREAK_LINE = ["\n"]
XML_VERSION_HEADER = '<?xml version="1.0" encoding="utf-8"?>' + BREAK_LINE_OFF
XML_VERSION = ['<?xml version="1.0" encoding="utf-8"?>']
XML_VERSION_STR = '<?xml version="1.0"?>\n'
XML_ODOO_OPENING_TAG = ["<odoo>"]
XML_HEAD = XML_VERSION + XML_ODOO_OPENING_TAG
XML_ODOO_CLOSING_TAG = ["</odoo>"]
FROM_ODOO_IMPORTS = ["from odoo import _, api, models, fields"]
MODEL_HEAD = FROM_ODOO_IMPORTS + BREAK_LINE
FROM_ODOO_IMPORTS_SUPERUSER = [
    "from odoo import _, api, models, fields, SUPERUSER_ID"
]
MODEL_SUPERUSER_HEAD = FROM_ODOO_IMPORTS_SUPERUSER + BREAK_LINE


class CodeGeneratorWriter(models.Model):
    _name = "code.generator.writer"
    _description = "Code Generator Writer"

    basename = fields.Char(string="Base name")

    code_generator_ids = fields.Many2many(
        comodel_name="code.generator.module",
        string="Code Generator",
    )

    list_path_file = fields.Char(
        string="List path file",
        help="Value are separated by ;",
    )

    rootdir = fields.Char(string="Root dir")

    @staticmethod
    def _fmt_underscores(word):
        return word.lower().replace(".", "_")

    @staticmethod
    def _fmt_camel(word):
        return word.replace(".", "_").title().replace("_", "")

    @staticmethod
    def _fmt_title(word):
        return word.replace(".", " ").title()

    @staticmethod
    def _get_l_map(fn, collection):
        """
        Util function to get a list of a map operation
        :param fn:
        :param collection:
        :return:
        """

        return list(map(fn, collection))

    def _get_class_name(self, model):
        """
        Util function to get a model class name representation from a model name (code.generator -> CodeGenerator)
        :param model:
        :return:
        """

        result = []
        bypoint = model.split(".")
        for byp in bypoint:
            result += byp.split("_")
        return "".join(self._get_l_map(lambda e: e.capitalize(), result))

    @staticmethod
    def _lower_replace(string, replacee=" ", replacer="_"):
        """
        Util function to replace and get the lower content of a string
        :param string:
        :return:
        """

        v = (
            str(string)
            .lower()
            .replace(replacee, replacer)
            .replace("-", "_")
            .replace(".", "_")
            .replace("'", "_")
            .replace("`", "_")
            .replace("^", "_")
        )
        new_v = v.strip("_")

        while new_v.count("__"):
            new_v = new_v.replace("__", "_")
        return unidecode.unidecode(new_v)

    def _get_model_model(self, model_model, replacee="."):
        """
        Util function to get a model res_id-like representation (code.generator -> code_generator)
        :param model_model:
        :param replacee:
        :return:
        """
        return self._lower_replace(model_model, replacee=replacee)

    @staticmethod
    def _get_python_class_4inherit(model):
        """
        Util function to get the Python Classes for inheritance
        :param model:
        :return:
        """

        class_4inherit = (
            "models.TransientModel"
            if model.transient
            else (
                "models.AbstractModel" if model._abstract else "models.Model"
            )
        )
        if model.m2o_inherit_py_class.name:
            class_4inherit += ", %s" % model.m2o_inherit_py_class.name

        return class_4inherit

    def _get_odoo_ttype_class(self, ttype):
        """
        Util function to get a field class name from a field type (char -> Char, many2one -> Many2one)
        :param ttype:
        :return:
        """

        return f"fields.{self._get_class_name(ttype)}"

    @staticmethod
    def _get_starting_spaces(compute_line):
        """
        Util function to count the starting spaces of a string
        :param compute_line:
        :return:
        """

        space_counter = 0
        for character in compute_line:
            if character.isspace():
                space_counter += 1

            else:
                break

        return space_counter

    @staticmethod
    def _set_limit_4xmlid(xmlid):
        """
        Util function to truncate (to 64 characters) an xml_id
        :param xmlid:
        :return:
        """

        # if 64 - len(xmlid) < 0:
        #     new_xml_id = "%s..." % xmlid[: 61 - len(xmlid)]
        #     _logger.warning(
        #         f"Slice xml_id {xmlid} to {new_xml_id} because length is upper"
        #         " than 63."
        #     )
        # else:
        #     new_xml_id = xmlid
        # return new_xml_id
        return xmlid

    @staticmethod
    def _prepare_compute_constrained_fields(l_fields):
        """

        :param l_fields:
        :return:
        """

        counter = 1
        prepared = ""
        for field in l_fields:
            prepared += "'%s'%s" % (
                field,
                ", " if counter < len(l_fields) else "",
            )
            counter += 1

        return prepared

    def _get_model_constrains(self, cw, model, module):
        """
        Function to obtain the model constrains
        :param model:
        :return:
        """

        if model.o2m_server_constrains:

            cw.emit()

            for sconstrain in model.o2m_server_constrains:
                l_constrained = self._get_l_map(
                    lambda e: e.strip(), sconstrain.constrained.split(",")
                )

                cw.emit(
                    f"@api.constrains({self._prepare_compute_constrained_fields(l_constrained)})"
                )
                cw.emit(f"def _check_{'_'.join(l_constrained)}(self):")

                l_code = sconstrain.txt_code.split("\n")
                with cw.indent():
                    for line in l_code:
                        cw.emit(line.rstrip())
                # starting_spaces = 2
                # for line in l_code:
                #     if self._get_starting_spaces(line) == 2:
                #         starting_spaces += 1
                #     l_model_constrains.append('%s%s' % (TAB4 * starting_spaces, line.strip()))
                #     starting_spaces = 2

                cw.emit()

            cw.emit()

        constraints_id = None
        if model.o2m_constraints:
            # TODO how to use this way? binding model not working
            constraints_id = model.o2m_constraints
        elif module.o2m_model_constraints:
            constraints_id = module.o2m_model_constraints

        if constraints_id:
            lst_constraint = []
            for constraint in constraints_id:
                constraint_name = constraint.name.replace(
                    "%s_" % self._get_model_model(model.model), ""
                )
                constraint_definition = constraint.definition
                constraint_message = (
                    constraint.message
                    if constraint.message
                    else UNDEFINEDMESSAGE
                )

                lst_constraint.append(
                    f"('{constraint_name}', '{constraint_definition}',"
                    f" '{constraint_message}')"
                )

            cw.emit()
            cw.emit_list(
                lst_constraint, ("[", "]"), before="_sql_constraints = "
            )
            cw.emit()

    def _set_static_description_file(self, module, application_icon):
        """
        Function to set the static descriptions files
        :param module:
        :param application_icon:
        :return:
        """

        static_description_icon_path = os.path.join(
            self.code_generator_data.static_description_path, "icon.png"
        )
        static_description_icon_code_generator_path = os.path.join(
            self.code_generator_data.static_description_path,
            "code_generator_icon.png",
        )
        # TODO hack to force icon or True
        if module.icon_child_image or module.icon_real_image:
            if module.icon_real_image:
                self.code_generator_data.write_file_binary(
                    static_description_icon_path,
                    base64.b64decode(module.icon_real_image),
                )
            if module.icon_child_image:
                self.code_generator_data.write_file_binary(
                    static_description_icon_code_generator_path,
                    base64.b64decode(module.icon_child_image),
                )
        else:
            # elif module.icon_image:

            # TODO use this when fix loading picture, now temporary disabled and force use icon from menu
            # self.code_generator_data.write_file_binary(static_description_icon_path,
            # base64.b64decode(module.icon_image))
            # TODO temp solution with icon from menu
            icon_path = ""
            if module.icon and os.path.isfile(module.icon):
                with open(module.icon, "rb") as file:
                    content = file.read()
                icon_path = module.icon
            else:
                if application_icon:
                    icon_path = application_icon[
                        application_icon.find(",") + 1 :
                    ]
                    # icon_path = application_icon.replace(",", "/")
                else:
                    icon_path = "static/description/icon_new_application.png"
                icon_path = os.path.normpath(
                    os.path.join(os.path.dirname(__file__), "..", icon_path)
                )
                with open(icon_path, "rb") as file:
                    content = file.read()
            if (
                module.template_module_id
                and module.template_module_id.icon_image
            ):
                if not icon_path:
                    _logger.error("Icon path is empty.")
                    return ""
                if not os.path.exists(icon_path):
                    _logger.error(f"Icon path {icon_path} doesn't exist.")
                    return ""
                # It's a template generator
                minimal_size_width = 350
                # Add logo in small corner
                logo = Image.open(
                    io.BytesIO(
                        base64.b64decode(module.template_module_id.icon_image)
                    )
                )
                icon = Image.open(icon_path)
                # Change original size for better quality
                if logo.width < minimal_size_width:
                    new_h = int(logo.height / logo.width * minimal_size_width)
                    new_w = minimal_size_width
                    logo = logo.resize((new_w, new_h), Image.ANTIALIAS)
                ratio = 0.3
                w = int(logo.width * ratio)
                if icon.width != icon.height:
                    h = int(logo.height / logo.width * w)
                else:
                    h = w
                size = w, h
                icon.thumbnail(size, Image.ANTIALIAS)
                x = logo.width - w
                logo.paste(icon, (x, 0))
                img_byte_arr = io.BytesIO()
                logo.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                # image = base64.b64decode(module.template_module_id.icon_image)
                self.code_generator_data.write_file_binary(
                    static_description_icon_path, img_byte_arr
                )
                module.icon_real_image = base64.b64encode(img_byte_arr)
                code_generator_image = base64.b64decode(
                    module.template_module_id.icon_image
                )
                module.icon_child_image = module.template_module_id.icon_image
                self.code_generator_data.write_file_binary(
                    static_description_icon_code_generator_path,
                    code_generator_image,
                )
            else:
                self.code_generator_data.write_file_binary(
                    static_description_icon_path, content
                )
                module.icon_real_image = base64.b64encode(content)
        # else:
        #     static_description_icon_path = ""

        return static_description_icon_path

    @staticmethod
    def _get_from_rec_name(record, model):
        """
        Util function to handle the _rec_name / rec_name access
        :param record:
        :param model:
        :return:
        """

        return (
            getattr(record, model._rec_name)
            if getattr(record, model._rec_name)
            else getattr(record, model.rec_name)
        )

    def set_module_init_file_extra(self, module):
        pass

    def set_module_translator(self, module_name, module_path):
        module_id = self.env["ir.module.module"].search(
            [("name", "=", module_name), ("state", "=", "installed")]
        )
        if not module_id:
            return

        i18n_path = os.path.join(module_path, "i18n")
        data = CodeGeneratorData(module_id, module_path)
        data.check_mkdir_and_create(i18n_path, is_file=False)

        # Create pot
        export = self.env["base.language.export"].create(
            {"format": "po", "modules": [(6, 0, [module_id.id])]}
        )

        export.act_getfile()
        po_file = export.data
        data = base64.b64decode(po_file).decode("utf-8")
        translation_file = os.path.join(i18n_path, f"{module_name}.pot")

        with open(translation_file, "w") as file:
            file.write(data)

        # Create po
        # TODO get this info from configuration/module
        # lst_lang = [
        #     ("fr_CA", "fr_CA"),
        #     ("fr_FR", "fr"),
        #     ("en_US", "en"),
        #     ("en_CA", "en_CA"),
        # ]
        lst_lang = [("fr_CA", "fr_CA")]
        for lang_local, lang_ISO in lst_lang:
            translation_file = os.path.join(i18n_path, f"{lang_ISO}.po")

            if not self.env["ir.translation"].search(
                [("lang", "=", lang_local)]
            ):
                with mute_logger("odoo.addons.base.models.ir_translation"):
                    self.env["base.language.install"].create(
                        {"lang": lang_local, "overwrite": True}
                    ).lang_install()
                self.env["base.update.translations"].create(
                    {"lang": lang_local}
                ).act_update()

            # Load existing translations
            # translations = self.env["ir.translation"].search([
            #     ('lang', '=', lang),
            #     ('module', '=', module_name)
            # ])

            export = self.env["base.language.export"].create(
                {
                    "lang": lang_local,
                    "format": "po",
                    "modules": [(6, 0, [module_id.id])],
                }
            )
            export.act_getfile()
            po_file = export.data
            data = base64.b64decode(po_file).decode("utf-8").strip() + "\n"

            # Special replace for lang fr_CA
            if lang_ISO in ["fr_CA", "fr", "en", "en_CA"]:
                data = data.replace(
                    '"Plural-Forms: \\n"',
                    '"Plural-Forms: nplurals=2; plural=(n > 1);\\n"',
                )

            with open(translation_file, "w") as file:
                file.write(data)

    def copy_missing_file(
        self, module_name, module_path, template_dir, lst_file_extra=None
    ):
        """
        This function will create and copy file into template module.
        :param module_name:
        :param module_path:
        :param template_dir:
        :param lst_file_extra:
        :return:
        """
        # TODO bad conception, this method not suppose to be here, move this before generate code
        module_id = self.env["ir.module.module"].search(
            [("name", "=", module_name), ("state", "=", "installed")]
        )
        if not module_id:
            return

        template_copied_dir = os.path.join(template_dir, "not_supported_files")

        # Copy i18n files
        i18n_po_path = os.path.join(module_path, "i18n", "*.po")
        i18n_pot_path = os.path.join(module_path, "i18n", "*.pot")
        target_i18n_path = os.path.join(template_copied_dir, "i18n")
        lst_file = glob.glob(i18n_po_path) + glob.glob(i18n_pot_path)
        if lst_file:
            CodeGeneratorData.os_make_dirs(target_i18n_path)
            for file_name in lst_file:
                shutil.copy(file_name, target_i18n_path)

        # Copy readme file
        readme_file_path = os.path.join(module_path, "README.rst")
        target_readme_file_path = os.path.join(template_copied_dir)
        shutil.copy(readme_file_path, target_readme_file_path)

        # Copy readme dir
        readme_dir_path = os.path.join(module_path, "readme")
        target_readme_dir_path = os.path.join(template_copied_dir, "readme")
        shutil.copytree(readme_dir_path, target_readme_dir_path)

        # Copy tests dir
        tests_dir_path = os.path.join(module_path, "tests")
        target_tests_dir_path = os.path.join(template_copied_dir, "tests")
        shutil.copytree(tests_dir_path, target_tests_dir_path)

        if lst_file_extra:
            for file_extra in lst_file_extra:
                # Special if existing, mail_message_subtype.xml
                mail_data_xml_path = os.path.join(module_path, file_extra)
                target_mail_data_xml_path = os.path.join(
                    template_copied_dir, file_extra
                )
                if os.path.isfile(mail_data_xml_path):
                    CodeGeneratorData.check_mkdir_and_create(
                        target_mail_data_xml_path
                    )
                    shutil.copy(mail_data_xml_path, target_mail_data_xml_path)

    def _set_manifest_file(self, module):
        """
        Function to set the module manifest file
        :param module:
        :return:
        """

        lang = "en_US"

        cw = CodeWriter()

        has_header = False
        if module.header_manifest:
            lst_header = module.header_manifest.split("\n")
            for line in lst_header:
                s_line = line.strip()
                if s_line:
                    cw.emit(s_line)
                    has_header = True
        if has_header:
            cw.emit()

        with cw.block(delim=("{", "}")):
            cw.emit(f"'name': '{module.shortdesc}',")

            if module.category_id:
                cw.emit(
                    "'category':"
                    f" '{module.category_id.with_context(lang=lang).name}',"
                )

            if module.summary and module.summary != "false":
                cw.emit(f"'summary': '{module.summary}',")

            if module.description:
                description = module.description.strip()
                lst_description = description.split("\n")
                if len(lst_description) == 1:
                    cw.emit(f"'description': '{description}',")
                else:
                    cw.emit("'description': '''")
                    for desc in lst_description:
                        cw.emit_raw(desc)
                    cw.emit("''',")

            if module.installed_version:
                cw.emit(f"'version': '{module.installed_version}',")

            if module.author:
                author = module.author.strip()
                lst_author = author.split(",")
                if len(lst_author) == 1:
                    cw.emit(f"'author': '{author}',")
                else:
                    cw.emit(f"'author': (")
                    with cw.indent():
                        for auth in lst_author[:-1]:
                            s_auth = auth.strip()
                            cw.emit(f"'{s_auth}, '")
                    cw.emit(f"'{lst_author[-1].strip()}'),")

            if module.contributors:
                cw.emit(f"'contributors': '{module.contributors}',")

            # if module.maintener:
            #     cw.emit(f"'maintainers': '{module.maintener}',")

            if module.license != "LGPL-3":
                cw.emit(f"'license': '{module.license}',")

            if module.sequence != 100:
                cw.emit(f"'sequence': {module.sequence},")

            if module.website:
                cw.emit(f"'website': '{module.website}',")

            if module.auto_install:
                cw.emit(f"'auto_install': True,")

            if module.demo:
                cw.emit(f"'demo': True,")

            if module.application:
                cw.emit(f"'application': True,")

            if module.dependencies_id:
                lst_depend = module.dependencies_id.mapped(
                    lambda did: f"'{did.depend_id.name}'"
                )
                cw.emit_list(
                    lst_depend, ("[", "]"), before="'depends': ", after=","
                )

            if module.external_dependencies_id and [
                a for a in module.external_dependencies_id if not a.is_template
            ]:
                with cw.block(
                    before="'external_dependencies':",
                    delim=("{", "}"),
                    after=",",
                ):
                    dct_depend = defaultdict(list)
                    for depend in module.external_dependencies_id:
                        if depend.is_template:
                            continue
                        dct_depend[depend.application_type].append(
                            f"'{depend.depend}'"
                        )
                    for application_type, lst_value in dct_depend.items():
                        cw.emit_list(
                            lst_value,
                            ("[", "]"),
                            before=f"'{application_type}': ",
                            after=",",
                        )

            lst_data = self._get_l_map(
                lambda dfile: f"'{dfile}'",
                self.code_generator_data.lst_manifest_data_files,
            )
            if lst_data:
                cw.emit_list(
                    lst_data, ("[", "]"), before="'data': ", after=","
                )

            cw.emit(f"'installable': True,")

            self.set_manifest_file_extra(cw, module)

        manifest_file_path = "__manifest__.py"
        self.code_generator_data.write_file_str(
            manifest_file_path, cw.render()
        )

    def set_manifest_file_extra(self, cw, module):
        pass

    def _get_id_view_model_data(self, record, model=None, is_internal=False):
        """
        Function to obtain the model data from a record
        :param record:
        :param is_internal: if False, add module name for external reference
        :return:
        """

        # special trick for some record
        xml_id = getattr(record, "xml_id")
        if xml_id:
            if is_internal:
                return xml_id.split(".")[1]
            return xml_id

        if model:
            record_model = model
        else:
            record_model = record.model

        ir_model_data = self.env["ir.model.data"].search(
            [
                ("model", "=", record_model),
                ("res_id", "=", record.id),
            ]
        )
        if not ir_model_data:
            return

        if is_internal:
            return ir_model_data[0].name
        return f"{ir_model_data[0].module}.{ir_model_data[0].name}"

    def _get_ir_model_data(self, record, give_a_default=False, module_name=""):
        """
        Function to obtain the model data from a record
        :param record:
        :param give_a_default:
        :param module_name:
        :return:
        """

        ir_model_data = self.env["ir.model.data"].search(
            [
                # TODO: Opción por valorar
                # ('module', '!=', '__export__'),
                ("model", "=", record._name),
                ("res_id", "=", record.id),
            ]
        )

        if ir_model_data:
            if module_name and module_name == ir_model_data[0].module:
                result = ir_model_data[0].name
            else:
                result = f"{ir_model_data[0].module}.{ir_model_data[0].name}"
        elif give_a_default:
            if record._rec_name:
                rec_name_v = getattr(record, record._rec_name)
                if not rec_name_v:
                    rec_name_v = uuid.uuid1().int
                second = self._lower_replace(rec_name_v)
            else:
                second = uuid.uuid1().int
            result = self._set_limit_4xmlid(
                f"{self._get_model_model(record._name)}_{second}"
            )
            # Check if name already exist
            model_data_exist = self.env["ir.model.data"].search(
                [("name", "=", result)]
            )
            new_result = result
            i = 0
            while model_data_exist:
                i += 1
                new_result = f"{result}_{i}"
                model_data_exist = self.env["ir.model.data"].search(
                    [("name", "=", new_result)]
                )

            self.env["ir.model.data"].create(
                {
                    "name": new_result,
                    "model": record._name,
                    "module": module_name,
                    "res_id": record.id,
                    "noupdate": True,  # If it's False, target record (res_id) will be removed while module update
                }
            )
            result = new_result
        else:
            result = False

        # Need to limit to 128 char, else can crash like when loading i18n po and id is too long
        if type(result) is str:
            # Remove strange char
            # TODO find another way to remove not alpha numeric char, but accept '_'
            result = (
                result.replace(",", "")
                .replace("'", "")
                .replace('"', "")
                .replace("(", "")
                .replace(")", "")
            )
            # TODO maybe check duplicate
            return result[:120]
        return result

    def _get_group_data_name(self, group):
        """
        Function to obtain the res_id-like group name (Code Generator / Manager -> code_generator_manager)
        :param group:
        :return:
        """

        return (
            self._get_ir_model_data(group)
            if self._get_ir_model_data(group)
            else self._lower_replace(group.name.replace(" /", ""))
        )

    def _get_model_data_name(self, model, module_name=""):
        """
        Function to obtain the res_id-like model name (code.generator.module -> code_generator_module)
        :param model:
        :return:
        """

        return (
            self._get_ir_model_data(model, module_name=module_name)
            if self._get_ir_model_data(model, module_name=module_name)
            else "model_%s" % self._get_model_model(model.model)
        )

    def _get_view_data_name(self, view):
        """
        Function to obtain the res_id-like view name
        :param view:
        :return:
        """

        return (
            self._get_ir_model_data(view)
            if self._get_ir_model_data(view)
            else "%s_%sview" % (self._get_model_model(view.model), view.type)
        )

    def _get_action_data_name(
        self, action, server=False, creating=False, module=None
    ):
        """
        Function to obtain the res_id-like action name
        :param action:
        :param server:
        :param creating:
        :return:
        """

        if not creating and self._get_ir_model_data(
            action, module_name=module.name
        ):
            action_name = self._get_ir_model_data(
                action, module_name=module.name
            )
            if not module or "." not in action_name:
                return action_name
            lst_action = action_name.split(".")
            if module.name == lst_action[0]:
                # remove internal name
                return lst_action[1]
            # link is external
            return action_name

        else:
            model = (
                getattr(action, "res_model")
                if not server
                else getattr(action, "model_id").model
            )
            model_model = self._get_model_model(model)
            action_type = "action_window" if not server else "server_action"

            new_action_name = action.name
            # TODO No need to support limit of 64, why this code?
            # new_action_name = self._set_limit_4xmlid(
            #     "%s" % action.name[: 64 - len(model_model) - len(action_type)]
            # )

            result_name = f"{model_model}_{self._lower_replace(new_action_name)}_{action_type}"

            # if new_action_name != action.name:
            #     _logger.warning(
            #         f"Slice action name {action.name} to"
            #         f" {new_action_name} because length is upper than 63."
            #         f" Result: {result_name}."
            #     )

            return result_name

    def _get_action_act_url_name(self, action):
        """
        Function to obtain the res_id-like action name
        :param action:
        :return:
        """
        return f"action_{self._lower_replace(action.name)}"

    def _get_menu_data_name(
        self, menu, ignore_module=False, ignore_module_name=None, module=None
    ):
        """
        Function to obtain the res_id-like menu name
        :param menu:
        :return:
        """

        menu_name = self._get_ir_model_data(menu, module_name=module.name)
        if menu_name:
            if "." in menu_name:
                module_name, menu_name_short = menu_name.split(".")
                if ignore_module or (
                    ignore_module_name and ignore_module_name == module_name
                ):
                    return menu_name_short
            return menu_name
        return self._lower_replace(menu.name)

    def _set_model_xmldata_file(self, module, model, model_model):
        """
        Function to set the module data file
        :param module:
        :param model:
        :param model_model:
        :return:
        """

        expression_export_data = model.expression_export_data
        search = (
            []
            if not expression_export_data
            else [ast.literal_eval(expression_export_data)]
        )
        # Search with active_test to support when active is False
        nomenclador_data = (
            self.env[model.model]
            .sudo()
            .with_context(active_test=False)
            .search(search)
        )
        if not nomenclador_data:
            return

        lst_data_xml = []
        lst_id = []
        lst_depend = []
        lst_field_id_blacklist = [
            a.m2o_fields.id
            for a in model.m2o_module.o2m_nomenclator_blacklist_fields
        ]
        lst_field_id_whitelist = [
            a.m2o_fields.id
            for a in model.m2o_module.o2m_nomenclator_whitelist_fields
        ]
        for record in nomenclador_data:

            f2exports = model.field_id.filtered(
                lambda field: field.name not in MAGIC_FIELDS
            )
            lst_field = []
            for rfield in f2exports:
                # whitelist check
                if (
                    lst_field_id_whitelist
                    and rfield.id not in lst_field_id_whitelist
                ):
                    continue
                # blacklist check
                if rfield.id in lst_field_id_blacklist:
                    continue
                record_value = getattr(record, rfield.name)
                child = None
                if record_value or (
                    not record_value
                    and rfield.ttype == "boolean"
                    and rfield.default == "True"
                ):
                    delete_node = False
                    if rfield.ttype == "many2one":
                        ref = self._get_ir_model_data(
                            record_value,
                            give_a_default=True,
                            module_name=module.name,
                        )
                        if not ref:
                            # This will cause an error at installation
                            _logger.error(
                                "Cannot find reference for field"
                                f" {rfield.name} model {model_model}"
                            )
                            continue
                        child = E.field({"name": rfield.name, "ref": ref})

                        if "." not in ref:
                            lst_depend.append(ref)

                    elif rfield.ttype == "one2many":
                        # TODO do we need to export one2many relation data, it's better to export many2one
                        # TODO maybe check if many2one is exported or export this one
                        continue
                        # field_eval = ", ".join(
                        #     record_value.mapped(
                        #         lambda rvalue: "(4, ref('%s'))"
                        #         % self._get_ir_model_data(
                        #             rvalue, give_a_default=True, module_name=module.name
                        #         )
                        #     )
                        # )
                        # child = E.field(
                        #     {"name": rfield.name, "eval": f"[{field_eval}]"}
                        # )

                    elif rfield.ttype == "many2many":
                        # TODO add dependencies id in lst_depend
                        field_eval = ", ".join(
                            record_value.mapped(
                                lambda rvalue: "ref(%s)"
                                % self._get_ir_model_data(
                                    rvalue,
                                    give_a_default=True,
                                    module_name=module.name,
                                )
                            )
                        )
                        child = E.field(
                            {
                                "name": rfield.name,
                                "eval": f"[(6,0, [{field_eval}])]",
                            }
                        )

                    elif rfield.ttype == "binary":
                        # Transform binary in string and remove b''
                        child = E.field(
                            {"name": rfield.name},
                            str(record_value)[2:-1],
                        )
                    elif rfield.ttype == "boolean":
                        # Don't show boolean if same value of default
                        if str(record_value) != rfield.default:
                            child = E.field(
                                {"name": rfield.name},
                                str(record_value),
                            )
                        else:
                            delete_node = True
                    elif rfield.related == "view_id.arch" or (
                        rfield.name == "arch" and rfield.model == "ir.ui.view"
                    ):
                        root = ET.fromstring(record_value)
                        child = E.field(
                            {"name": rfield.name, "type": "xml"}, root
                        )

                    else:
                        child = E.field(
                            {"name": rfield.name}, str(record_value)
                        )

                    if not delete_node and child is not None:
                        lst_field.append(child)

            # TODO delete this comment, check why no need anymore rec_name
            # rec_name_v = self._get_from_rec_name(record, model)
            # if rec_name_v:
            #     rec_name_v = self._lower_replace(rec_name_v)
            #     id_record = self._set_limit_4xmlid(f"{model_model}_{rec_name_v}")
            # else:
            #     rec_name_v = uuid.uuid1().int
            id_record = self._get_ir_model_data(
                record, give_a_default=True, module_name=module.name
            )
            lst_id.append(id_record)
            record_xml = E.record(
                {"id": id_record, "model": model.model}, *lst_field
            )
            lst_data_xml.append(record_xml)

        # TODO find when is noupdate and not noupdate
        # <data noupdate="1">
        xml_no_update = E.data({"noupdate": "1"}, *lst_data_xml)
        module_file = E.odoo({}, xml_no_update)
        data_file_path = os.path.join(
            self.code_generator_data.data_path, f"{model_model}.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_file, pretty_print=True
        )
        self.code_generator_data.write_file_binary(
            data_file_path, result, data_file=True
        )

        abs_path_file = os.path.join("data", f"{model_model}.xml")

        self.code_generator_data.dct_data_metadata_file[abs_path_file] = lst_id
        if lst_depend:
            self.code_generator_data.dct_data_depend[
                abs_path_file
            ] = lst_depend

    def _set_module_menus(self, module):
        """
        Function to set the module menus file
        :param module:
        :return:
        """

        application_icon = None
        menus = module.with_context({"ir.ui.menu.full_list": True}).o2m_menus
        if not menus:
            return ""

        # Group by parent_id
        lst_menu_root = menus.filtered(lambda x: not x.parent_id).sorted(
            key=lambda x: self._get_menu_data_name(x, module=module).split(
                "."
            )[-1]
        )
        lst_menu_item = menus.filtered(lambda x: x.parent_id and x.child_id)
        lst_menu_last_child = menus.filtered(lambda x: not x.child_id).sorted(
            key=lambda x: self._get_menu_data_name(x, module=module).split(
                "."
            )[-1]
        )
        nb_root = len(lst_menu_root)
        nb_item = len(lst_menu_item)
        nb_last_child = len(lst_menu_last_child)
        has_add_root = False
        has_item = False
        has_last_child = False

        # Order by id_name
        lst_menu = [a for a in lst_menu_root]

        # Be sure parent is added
        lst_menu_item = [a for a in lst_menu_item]

        while lst_menu_item:
            lst_menu_to_order = []
            len_start = len(lst_menu_item)
            for menu_item in lst_menu_item[:]:
                # Remove item and add it
                if menu_item.parent_id in lst_menu:
                    lst_menu_item.remove(menu_item)
                    lst_menu_to_order.append(menu_item)

            if lst_menu_to_order:
                lst_menu_ordered = sorted(
                    lst_menu_to_order,
                    key=lambda x: self._get_menu_data_name(
                        x, module=module
                    ).split(".")[-1],
                )
                for menu_ordered in lst_menu_ordered:
                    lst_menu.append(menu_ordered)

            len_end = len(lst_menu_item)
            if len_start == len_end:
                # Find no parent
                for menu_item in lst_menu_item:
                    lst_menu.append(menu_item)

        # Order by id_name
        for menu_child in lst_menu_last_child:
            lst_menu.append(menu_child)

        lst_menu_xml = []

        for i, menu in enumerate(lst_menu):

            menu_id = self._get_menu_data_name(
                menu, ignore_module=True, module=module
            )
            dct_menu_item = {"id": menu_id}
            if menu.name != menu_id:
                dct_menu_item["name"] = menu.name

            if not menu.ignore_act_window:
                try:
                    menu.action
                except Exception as e:
                    # missing action on menu
                    _logger.error(
                        f"Missing action window on menu {menu.name}."
                    )
                    continue

                if menu.action:
                    dct_menu_item["action"] = self._get_action_data_name(
                        menu.action, module=module
                    )

            if not menu.active:
                dct_menu_item["active"] = "False"

            if len(lst_menu) == 1 and menu.sequence != 10 or len(lst_menu) > 1:
                dct_menu_item["sequence"] = str(menu.sequence)

            if menu.parent_id:
                dct_menu_item["parent"] = self._get_menu_data_name(
                    menu.parent_id,
                    ignore_module_name=module.name,
                    module=module,
                )

            if menu.groups_id:
                dct_menu_item["groups"] = self._get_m2m_groups(menu.groups_id)

            if menu.web_icon:
                # TODO move application_icon in code_generator_data
                application_icon = menu.web_icon
                # ignore actual icon, force a new icon
                new_icon = f"{module.name},static/description/icon.png"
                dct_menu_item["web_icon"] = new_icon
                if new_icon != menu.web_icon:
                    _logger.warning(
                        f"Difference between menu icon '{menu.web_icon}' and"
                        f" new icon '{new_icon}'"
                    )

            if not has_add_root and nb_root:
                has_add_root = True
                lst_menu_xml.append(ET.Comment("end line"))
                lst_menu_xml.append(ET.Comment("Root menu"))

            if not has_item and nb_item and i >= nb_root:
                has_item = True
                lst_menu_xml.append(ET.Comment("end line"))
                lst_menu_xml.append(ET.Comment("Sub menu"))

            if not has_last_child and nb_last_child and i >= nb_root + nb_item:
                has_last_child = True
                lst_menu_xml.append(ET.Comment("end line"))
                lst_menu_xml.append(ET.Comment("Child menu"))

            menu_xml = E.menuitem(dct_menu_item)
            lst_menu_xml.append(ET.Comment("end line"))
            lst_menu_xml.append(menu_xml)

        lst_menu_xml.append(ET.Comment("end line"))
        module_menus_file = E.odoo({}, *lst_menu_xml)
        menu_file_path = os.path.join(
            self.code_generator_data.views_path, "menu.xml"
        )
        result = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            module_menus_file, pretty_print=True
        )

        new_result = result.decode().replace("  <!--end line-->\n", "\n")[:-1]

        self.code_generator_data.write_file_str(
            menu_file_path, new_result, data_file=True
        )

        return application_icon

    @staticmethod
    def _setup_xml_indent(content, indent=0, is_end=False):
        # return "\n".join([f"{'    ' * indent}{a}" for a in content.split("\n")])
        str_content = content.rstrip().replace("\n", f"\n{'  ' * indent}")
        super_content = f"\n{'  ' * indent}{str_content}"
        if is_end:
            super_content += f"\n{'  ' * 1}"
        else:
            super_content += f"\n{'  ' * (indent - 1)}"
        return super_content

    @staticmethod
    def _change_xml_2_to_4_spaces(content):
        new_content = ""
        # Change 2 space for 4 space
        for line in content.split("\n"):
            # count first space
            if line.strip():
                new_content += (
                    f'{"  " * (len(line) - len(line.lstrip()))}{line.strip()}\n'
                )
            else:
                new_content += "\n"
        return new_content

    def _set_model_xmlview_file(self, module, model, model_model):
        """
        Function to set the model xml files
        :param module:
        :param model:
        :param model_model:
        :return:
        """

        # view_ids = model.view_ids
        # TODO model.view_ids not working when add inherit view from wizard... what is different? Force values
        view_ids = self.env["ir.ui.view"].search([("model", "=", model.model)])
        act_window_ids = self.env["ir.actions.act_window"].search(
            [("res_model", "=", model.model)]
        )
        server_action_ids = model.o2m_server_action

        # Remove all field when in inherit if not in whitelist
        is_whitelist = any([a.is_show_whitelist_write_view for a in view_ids])
        view_filtered_ids = view_ids.filtered(
            lambda field: field.name not in MAGIC_FIELDS
            and not field.is_hide_blacklist_write_view
            and (
                not is_whitelist
                or (is_whitelist and field.is_show_whitelist_write_view)
            )
        )

        if not (view_filtered_ids or act_window_ids or server_action_ids):
            return

        dct_replace = {}
        dct_replace_template = {}
        lst_id = []
        lst_item_xml = []
        lst_item_template = []

        #
        # Views
        #
        for view in view_filtered_ids:

            view_type = view.type

            lst_view_type = list(
                dict(
                    self.env["code.generator.view"]
                    ._fields["view_type"]
                    .selection
                ).keys()
            )
            if view_type in lst_view_type:

                str_id_system = self._get_id_view_model_data(
                    view, model="ir.ui.view", is_internal=True
                )
                if not str_id_system:
                    str_id = f"{model_model}_view_{view_type}"
                else:
                    str_id = str_id_system
                if str_id in lst_id:
                    count_id = lst_id.count(str_id)
                    str_id += str(count_id)
                lst_id.append(str_id)

                self.code_generator_data.add_view_id(view.name, str_id)

                lst_field = []

                if view.name:
                    lst_field.append(E.field({"name": "name"}, view.name))

                lst_field.append(E.field({"name": "model"}, view.model))

                if view.key:
                    lst_field.append(E.field({"name": "key"}, view.key))

                if view.priority != 16:
                    lst_field.append(
                        E.field({"name": "priority"}, str(view.priority))
                    )

                if view.inherit_id:
                    lst_field.append(
                        E.field(
                            {
                                "name": "inherit_id",
                                "ref": self._get_view_data_name(
                                    view.inherit_id
                                ),
                            }
                        )
                    )

                    if view.mode == "primary":
                        lst_field.append(E.field({"name": "mode"}, "primary"))

                if not view.active:
                    lst_field.append(
                        E.field({"name": "active", "eval": False})
                    )

                if view.arch_db:
                    uid = str(uuid.uuid1())
                    str_arch_db = (
                        view.arch_db
                        if not view.arch_db.startswith(XML_VERSION_STR)
                        else view.arch_db[len(XML_VERSION_STR) :]
                    )
                    # TODO retransform xml to format correctly
                    str_data_begin = "<data>\n"
                    str_data_end = "</data>\n"
                    if str_arch_db.startswith(
                        str_data_begin
                    ) and str_arch_db.endswith(str_data_end):
                        str_arch_db = str_arch_db[
                            len(str_data_begin) : -len(str_data_end)
                        ]
                    dct_replace[uid] = self._setup_xml_indent(
                        str_arch_db, indent=3
                    )
                    lst_field.append(
                        E.field({"name": "arch", "type": "xml"}, uid)
                    )

                if view.groups_id:
                    lst_field.append(
                        self._get_m2m_groups_etree(view.groups_id)
                    )

                info = E.record(
                    {"id": str_id, "model": "ir.ui.view"}, *lst_field
                )
                lst_item_xml.append(ET.Comment("end line"))
                lst_item_xml.append(info)

            elif view_type == "qweb":
                template_value = {"id": view.key, "name": view.name}
                if view.inherit_id:
                    template_value["inherit_id"] = view.inherit_id.key

                uid = str(uuid.uuid1())
                dct_replace_template[uid] = self._setup_xml_indent(
                    view.arch, indent=2, is_end=True
                )
                info = E.template(template_value, uid)
                # lst_item_xml.append(ET.Comment("end line"))
                # lst_item_xml.append(info)
                lst_item_template.append(ET.Comment("end line"))
                lst_item_template.append(info)

            else:
                _logger.error(
                    f"View type {view_type} of {view.name} not supported."
                )

        #
        # Action Windows
        #
        for act_window in act_window_ids:
            # Use descriptive method when contain this attributes, not supported in simplify view
            use_complex_view = bool(
                act_window.groups_id
                or act_window.help
                or act_window.multi
                or not act_window.auto_search
                or act_window.filter
                or act_window.search_view_id
                or act_window.usage
            )

            record_id = self._get_id_view_model_data(
                act_window, model="ir.actions.act_window", is_internal=True
            )
            if not record_id:
                record_id = self._get_action_data_name(
                    act_window, creating=True
                )

            has_menu = bool(
                module.with_context({"ir.ui.menu.full_list": True}).o2m_menus
            )
            # TODO if not complex, search if associate with a menu. If the menu is not generated, don't generate is act_window
            if use_complex_view:
                lst_field = []

                if act_window.name:
                    lst_field.append(
                        E.field({"name": "name"}, act_window.name)
                    )

                if act_window.res_model or act_window.m2o_res_model:
                    lst_field.append(
                        E.field(
                            {"name": "res_model"},
                            act_window.res_model
                            or act_window.m2o_res_model.model,
                        )
                    )

                if act_window.binding_model_id:
                    binding_model = self._get_model_data_name(
                        act_window.binding_model_id, module_name=module.name
                    )
                    lst_field.append(
                        E.field(
                            {"name": "binding_model_id", "ref": binding_model}
                        )
                    )

                if act_window.view_id:
                    lst_field.append(
                        E.field(
                            {
                                "name": "view_id",
                                "ref": self._get_view_data_name(
                                    act_window.view_id
                                ),
                            }
                        )
                    )

                if act_window.domain != "[]" and act_window.domain:
                    lst_field.append(
                        E.field({"name": "domain"}, act_window.domain)
                    )

                if act_window.context != "{}":
                    lst_field.append(
                        E.field({"name": "context"}, act_window.context)
                    )

                if act_window.src_model or act_window.m2o_src_model:
                    lst_field.append(
                        E.field(
                            {"name": "src_model"},
                            act_window.src_model
                            or act_window.m2o_src_model.model,
                        )
                    )

                if act_window.target != "current":
                    lst_field.append(
                        E.field({"name": "target"}, act_window.target)
                    )

                if (
                    act_window.view_mode != "tree,form"
                    and act_window.view_mode != "form,tree"
                ):
                    lst_field.append(
                        E.field({"name": "view_mode"}, act_window.view_mode)
                    )

                if act_window.view_type != "form":
                    lst_field.append(
                        E.field({"name": "view_type"}, act_window.view_type)
                    )

                if act_window.usage:
                    lst_field.append(E.field({"name": "usage", "eval": True}))

                if act_window.limit != 80 and act_window.limit != 0:
                    lst_field.append(
                        E.field({"name": "limit"}, str(act_window.limit))
                    )

                if act_window.search_view_id:
                    lst_field.append(
                        E.field(
                            {
                                "name": "search_view_id",
                                "ref": self._get_view_data_name(
                                    act_window.search_view_id
                                ),
                            }
                        )
                    )

                if act_window.filter:
                    lst_field.append(E.field({"name": "filter", "eval": True}))

                if not act_window.auto_search:
                    lst_field.append(
                        E.field({"name": "auto_search", "eval": False})
                    )

                if act_window.multi:
                    lst_field.append(E.field({"name": "multi", "eval": True}))

                if act_window.help:
                    lst_field.append(
                        E.field(
                            {"name": "name", "type": "html"}, act_window.help
                        )
                    )

                if act_window.groups_id:
                    lst_field.append(
                        self._get_m2m_groups_etree(act_window.groups_id)
                    )

                info = E.record(
                    {"id": record_id, "model": "ir.actions.act_window"},
                    *lst_field,
                )
                lst_item_xml.append(ET.Comment("end line"))
                lst_item_xml.append(info)
            elif has_menu:
                dct_act_window = {"id": record_id}

                if act_window.name:
                    dct_act_window["name"] = act_window.name

                if act_window.res_model or act_window.m2o_res_model:
                    dct_act_window["res_model"] = (
                        act_window.res_model or act_window.m2o_res_model.model
                    )

                if act_window.binding_model_id:
                    # TODO replace ref
                    pass

                if act_window.view_id:
                    # TODO replace ref
                    pass

                if act_window.domain != "[]" and act_window.domain:
                    dct_act_window["domain"] = (
                        act_window.res_model or act_window.m2o_res_model.model
                    )

                if act_window.context != "{}":
                    dct_act_window["context"] = act_window.context

                if act_window.src_model or act_window.m2o_src_model:
                    dct_act_window["src_model"] = (
                        act_window.src_model or act_window.m2o_src_model.model
                    )

                if act_window.target != "current":
                    dct_act_window["target"] = act_window.target

                if act_window.view_mode != "tree,form":
                    dct_act_window["view_mode"] = act_window.view_mode

                if act_window.view_type != "form":
                    dct_act_window["view_type"] = act_window.view_type

                if act_window.usage:
                    # TODO replace ref
                    pass

                if act_window.limit != 80 and act_window.limit != 0:
                    dct_act_window["limit"] = str(act_window.limit)

                if act_window.search_view_id:
                    # TODO replace ref
                    pass

                if act_window.filter:
                    # TODO replace ref
                    pass

                if not act_window.auto_search:
                    # TODO replace ref
                    pass

                if act_window.multi:
                    # TODO replace ref
                    pass

                if act_window.help:
                    # TODO how add type html and contents?
                    pass

                if act_window.groups_id:
                    # TODO check _get_m2m_groups_etree
                    pass

                info = E.act_window(dct_act_window)
                lst_item_xml.append(ET.Comment("end line"))
                lst_item_xml.append(info)

        #
        # Server Actions
        #
        for server_action in server_action_ids:

            lst_field = [
                E.field({"name": "name"}, server_action.name),
                E.field(
                    {
                        "name": "model_id",
                        "ref": self._get_model_data_name(
                            server_action.model_id, module_name=module.name
                        ),
                    }
                ),
                E.field(
                    {
                        "name": "binding_model_id",
                        "ref": self._get_model_data_name(
                            model, module_name=module.name
                        ),
                    }
                ),
            ]

            if server_action.state == "code":
                lst_field.append(E.field({"name": "state"}, "code"))

                lst_field.append(E.field({"name": "code"}, server_action.code))

            else:
                lst_field.append(E.field({"name": "state"}, "multi"))

                if server_action.child_ids:
                    child_obj = ", ".join(
                        server_action.child_ids.mapped(
                            lambda child: "ref(%s)"
                            % self._get_action_data_name(child, server=True)
                        )
                    )
                    lst_field.append(
                        E.field(
                            {
                                "name": "child_ids",
                                "eval": f"[(6,0, [{child_obj}])]",
                            }
                        )
                    )

            record_id = self._get_id_view_model_data(
                server_action, model="ir.actions.server", is_internal=True
            )
            if not record_id:
                record_id = self._get_action_data_name(
                    server_action, server=True, creating=True
                )
            info = E.record(
                {"id": record_id, "model": "ir.actions.server"}, *lst_field
            )
            lst_item_xml.append(ET.Comment("end line"))

            if server_action.comment:
                lst_item_xml.append(
                    ET.Comment(text=f" {server_action.comment} ")
                )

            lst_item_xml.append(info)

        lst_item_xml.append(ET.Comment("end line"))
        root = E.odoo({}, *lst_item_xml)

        content = XML_VERSION_HEADER.encode("utf-8") + ET.tostring(
            root, pretty_print=True
        )
        str_content = content.decode()

        str_content = str_content.replace("  <!--end line-->\n", "\n")
        for key, value in dct_replace.items():
            str_content = str_content.replace(key, value)
        str_content = self._change_xml_2_to_4_spaces(str_content)[:-1]

        wizards_path = self.code_generator_data.wizards_path
        views_path = self.code_generator_data.views_path
        xml_file_path = os.path.join(
            wizards_path if model.transient else views_path,
            f"{model_model}.xml",
        )
        self.code_generator_data.write_file_str(
            xml_file_path, str_content, data_file=True
        )

        if dct_replace_template:
            root_template = E.odoo({}, *lst_item_template)
            content_template = XML_VERSION_HEADER.encode(
                "utf-8"
            ) + ET.tostring(root_template, pretty_print=True)
            str_content_template = content_template.decode()

            str_content_template = str_content_template.replace(
                "  <!--end line-->\n", "\n"
            )
            for key, value in dct_replace_template.items():
                str_content_template = str_content_template.replace(key, value)
            str_content_template = self._change_xml_2_to_4_spaces(
                str_content_template
            )[:-1]

            views_path = self.code_generator_data.views_path
            xml_file_path = os.path.join(
                views_path,
                f"{module.name}_templates.xml",
            )
            self.code_generator_data.write_file_str(
                xml_file_path, str_content_template, data_file=True
            )

    def _set_model_xmlreport_file(self, module, model, model_model):
        """

        :param module:
        :param model:
        :param model_model:
        :return:
        """

        if not model.o2m_reports:
            return

        l_model_report_file = XML_HEAD + BLANK_LINE

        for report in model.o2m_reports:

            l_model_report_file.append(
                '<template id="%s">' % report.report_name
            )

            str_arch_db = (
                report.m2o_template.arch_db
                if not report.m2o_template.arch_db.startswith(XML_VERSION_STR)
                else report.m2o_template.arch_db[len(XML_VERSION_STR) :]
            )
            l_model_report_file.append(
                f'<field name="arch" type="xml">{str_arch_db}</field>'
            )

            l_model_report_file.append("</template>\n")

            l_model_report_file.append(
                '<record model="ir.actions.report" id="%s_actionreport">'
                % report.report_name
            )

            l_model_report_file.append(
                '<field name="model">%s</field>' % report.model
            )

            l_model_report_file.append(
                '<field name="name">%s</field>' % report.report_name
            )

            l_model_report_file.append(
                '<field name="file">%s</field>' % report.report_name
            )

            l_model_report_file.append(
                '<field name="string">%s</field>' % report.name
            )

            l_model_report_file.append(
                '<field name="report_type">%s</field>' % report.report_type
            )

            if report.print_report_name:
                l_model_report_file.append(
                    '<field name="print_report_name">%s</field>'
                    % report.print_report_name
                )

            if report.multi:
                l_model_report_file.append(
                    '<field name="multi">%s</field>' % report.multi
                )

            if report.attachment_use:
                l_model_report_file.append(
                    '<field name="attachment_use">%s</field>'
                    % report.attachment_use
                )

            if report.attachment:
                l_model_report_file.append(
                    '<field name="attachment">%s</field>' % report.attachment
                )

            if report.binding_model_id:
                l_model_report_file.append(
                    '<field name="binding_model_id" ref="%s" />'
                    % self._get_model_data_name(
                        report.binding_model_id, module_name=module.name
                    )
                )

            if report.groups_id:
                l_model_report_file.append(
                    self._get_m2m_groups(report.groups_id)
                )

            l_model_report_file.append("</record>")

            l_model_report_file += XML_ODOO_CLOSING_TAG

        xmlreport_file_path = os.path.join(
            self.code_generator_data.reports_path, f"{model_model}.xml"
        )
        self.code_generator_data.write_file_lst_content(
            xmlreport_file_path, l_model_report_file, data_file=True
        )

    def _get_rec_name_inherit_model(self, model):
        # search in inherit
        lst_rec_name_inherit = []
        for inherit_model in model.inherit_model_ids:
            model_inherit_id = inherit_model.depend_id
            if model_inherit_id.id != model.id:
                lst_rec_name_inherit.append(
                    self._get_rec_name_inherit_model(model_inherit_id)
                )
        result_rec_name = None
        new_rec_name = self.env[model.model]._rec_name
        if new_rec_name and new_rec_name != "name":
            result_rec_name = new_rec_name
        elif model.rec_name and model.rec_name != "name":
            result_rec_name = model.rec_name
        # Ignore rec_name if same of inherit parent
        if lst_rec_name_inherit and result_rec_name:
            if result_rec_name in lst_rec_name_inherit:
                return None
        return result_rec_name

    def _set_model_py_file(self, module, model, model_model):
        """
        Function to set the model files
        :param model:
        :param model_model:
        :return:
        """

        key_special_endline = str(uuid.uuid1())

        cw = CodeWriter()

        code_ids = model.o2m_codes.filtered(
            lambda x: not x.is_templated
        ).sorted(key=lambda x: x.sequence)
        code_import_ids = model.o2m_code_import.filtered(
            lambda x: not x.is_templated
        ).sorted(key=lambda x: x.sequence)
        if code_import_ids:
            for code in code_import_ids:
                for code_line in code.code.split("\n"):
                    cw.emit(code_line)
        else:
            # search api or contextmanager
            # TODO ignore api, because need to search in code
            has_context_manager = False
            lst_import = MODEL_HEAD
            for code_id in code_ids:
                if (
                    code_id.decorator
                    and "@contextmanager" in code_id.decorator
                ):
                    has_context_manager = True
            if has_context_manager:
                lst_import.insert(1, "from contextlib import contextmanager")

            for line in lst_import:
                str_line = line.strip()
                cw.emit(str_line)

            if (
                model.m2o_inherit_py_class.name
                and model.m2o_inherit_py_class.module
            ):
                cw.emit(
                    f"from {model.m2o_inherit_py_class.module} import"
                    f" {model.m2o_inherit_py_class.name}"
                )

        cw.emit()
        cw.emit(
            "class"
            f" {self._get_class_name(model.model)}({self._get_python_class_4inherit(model)}):"
        )

        with cw.indent():
            """
            _name
            _table =
            _description
            _auto = False
            _log_access = False
            _order = ""
            _rec_name = ""
            _foreign_keys = []
            """
            # Force unique inherit
            lst_inherit = sorted(
                list(set([a.depend_id.model for a in model.inherit_model_ids]))
            )

            add_name = False
            if model.model not in lst_inherit:
                add_name = True
                cw.emit(f"_name = '{model.model}'")

            if lst_inherit:
                if len(lst_inherit) == 1:
                    str_inherit = f"'{lst_inherit[0]}'"
                else:
                    str_inherit_internal = '", "'.join(lst_inherit)
                    str_inherit = f'["{str_inherit_internal}"]'
                cw.emit(f"_inherit = {str_inherit}")

            if model.description:
                new_description = model.description.replace("'", "\\'")
                cw.emit(f"_description = '{new_description}'")
            elif not lst_inherit or add_name:
                cw.emit(f"_description = '{model.name}'")
            rec_name = self._get_rec_name_inherit_model(model)
            if rec_name:
                cw.emit(f"_rec_name = '{rec_name}'")

            # TODO _order, _local_fields, _period_number, _inherits, _log_access, _auto, _parent_store
            # TODO _parent_name

            self._get_model_constrains(cw, model, module)

            self._get_model_fields(cw, model)

            # code_ids = self.env["code.generator.model.code"].search(
            #     [("m2o_module", "=", module.id)]
            # )

            # Add function
            for code in code_ids:
                cw.emit()
                if code.decorator:
                    for line in code.decorator.split(";"):
                        if line:
                            cw.emit(line)
                return_v = "" if not code.returns else f" -> {code.returns}"
                cw.emit(f"def {code.name}({code.param}){return_v}:")

                code_traited = code.code.replace("\\\n", key_special_endline)
                code_traited = code_traited.replace("\\'", "\\\\'")
                code_traited = code_traited.replace("\b", "\\b")
                with cw.indent():
                    for code_line in code_traited.split("\n"):
                        if key_special_endline in code_line:
                            code_line = code_line.replace(
                                key_special_endline, "\\\\n"
                            )
                        cw.emit(code_line)

        if model.transient:
            pypath = self.code_generator_data.wizards_path
        elif model.o2m_reports and self.env[model.model]._abstract:
            pypath = self.code_generator_data.reports_path
        else:
            pypath = self.code_generator_data.models_path

        model_file_path = os.path.join(pypath, f"{model_model}.py")

        self.code_generator_data.write_file_str(model_file_path, cw.render())

        return model_file_path

    def _set_module_security(self, module, l_model_rules, l_model_csv_access):
        """
        Function to set the module security file
        :param module:
        :param l_model_rules:
        :param l_model_csv_access:
        :return:
        """
        l_model_csv_access.insert(
            0,
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink",
        )

        if module.o2m_groups or l_model_rules:
            l_module_security = ["<data>\n"]

            for group in module.o2m_groups:

                l_module_security += [
                    '<record model="res.groups" id="%s">'
                    % self._get_group_data_name(group)
                ]
                l_module_security += [
                    '<field name="name">%s</field>' % group.name
                ]

                if group.comment:
                    l_module_security += [
                        '<field name="comment">%s</field>' % group.comment
                    ]

                if group.implied_ids:
                    l_module_security += [
                        '<field name="implied_ids" eval="[%s]"/>'
                        % ", ".join(
                            group.implied_ids.mapped(
                                lambda g: "(4, ref('%s'))"
                                % self._get_group_data_name(g)
                            )
                        )
                    ]

                l_module_security += ["</record>\n"]

            l_module_security += l_model_rules

            l_module_security += ["</data>"]

            module_name = module.name.lower().strip()
            security_file_path = os.path.join(
                self.code_generator_data.security_path, f"{module_name}.xml"
            )
            self.code_generator_data.write_file_lst_content(
                security_file_path,
                XML_HEAD + l_module_security + XML_ODOO_CLOSING_TAG,
                data_file=True,
                insert_first=True,
            )

        if len(l_model_csv_access) > 1:
            model_access_file_path = os.path.join(
                self.code_generator_data.security_path, "ir.model.access.csv"
            )
            self.code_generator_data.write_file_lst_content(
                model_access_file_path,
                l_model_csv_access,
                data_file=True,
                insert_first=True,
            )

    def _get_model_access(self, module, model):
        """
        Function to obtain the model access
        :param model:
        :return:
        """

        l_model_csv_access = []

        for access in model.access_ids:
            access_name = access.name

            access_model_data = self.env["ir.model.data"].search(
                [
                    ("module", "=", module.name),
                    ("model", "=", "ir.model.access"),
                    ("res_id", "=", access.id),
                ]
            )

            access_id = (
                access_model_data[0].name
                if access_model_data
                else self._lower_replace(access_name)
            )

            access_model = self._get_model_model(access.model_id.model)

            access_group = (
                self._get_group_data_name(access.group_id)
                if access.group_id
                else ""
            )

            access_read, access_create, access_write, access_unlink = (
                1 if access.perm_read else 0,
                1 if access.perm_create else 0,
                1 if access.perm_write else 0,
                1 if access.perm_unlink else 0,
            )

            l_model_csv_access.append(
                "%s,%s,model_%s,%s,%s,%s,%s,%s"
                % (
                    access_id,
                    access_name,
                    access_model,
                    access_group,
                    access_read,
                    access_create,
                    access_write,
                    access_unlink,
                )
            )

        return l_model_csv_access

    def _get_model_rules(self, module, model):
        """
        Function to obtain the model rules
        :param model:
        :return:
        """

        l_model_rules = []

        for rule in model.rule_ids:

            if rule.name:
                l_model_rules.append(
                    '<record model="ir.rule" id="%s">'
                    % self._lower_replace(rule.name)
                )
                l_model_rules.append(
                    '<field name="name">%s</field>' % rule.name
                )

            else:
                l_model_rules.append(
                    '<record model="ir.rule" id="%s_rrule_%s">'
                    % (
                        self._get_model_data_name(
                            rule.model_id, module_name=module.name
                        ),
                        rule.id,
                    )
                )

            l_model_rules.append(
                '<field name="model_id" ref="%s"/>'
                % self._get_model_data_name(
                    rule.model_id, module_name=module.name
                )
            )

            if rule.domain_force:
                l_model_rules.append(
                    '<field name="domain_force">%s</field>' % rule.domain_force
                )

            if not rule.active:
                l_model_rules.append('<field name="active" eval="False" />')

            if rule.groups:
                l_model_rules.append(self._get_m2m_groups(rule.groups))

            if not rule.perm_read:
                l_model_rules.append('<field name="perm_read" eval="False" />')

            if not rule.perm_create:
                l_model_rules.append(
                    '<field name="perm_create" eval="False" />'
                )

            if not rule.perm_write:
                l_model_rules.append(
                    '<field name="perm_write" eval="False" />'
                )

            if not rule.perm_unlink:
                l_model_rules.append(
                    '<field name="perm_unlink" eval="False" />'
                )

            l_model_rules.append("</record>\n")

        return l_model_rules

    def _get_m2m_groups(self, m2m_groups):
        """

        :param m2m_groups:
        :return:
        """

        return '<field name="groups_id" eval="[(6,0, [%s])]" />' % ", ".join(
            m2m_groups.mapped(
                lambda g: "ref(%s)" % self._get_group_data_name(g)
            )
        )

    def _get_m2m_groups_etree(self, m2m_groups):
        """

        :param m2m_groups:
        :return:
        """

        var = ", ".join(
            m2m_groups.mapped(
                lambda g: "ref(%s)" % self._get_group_data_name(g)
            )
        )
        return E.field({"name": "groups_id", "eval": f"[(6,0, [{var}])]"})

    def _get_model_fields(self, cw, model):
        """
        Function to obtain the model fields
        :param model:
        :return:
        """

        # TODO detect if contain code_generator_sequence, else order by name
        f2exports = model.field_id.filtered(
            lambda field: field.name not in MAGIC_FIELDS
        ).sorted(key=lambda r: r.code_generator_sequence)

        if model.inherit_model_ids:
            is_whitelist = any(
                [a.is_show_whitelist_model_inherit_call() for a in f2exports]
            )
            if is_whitelist:
                f2exports = f2exports.filtered(
                    lambda field: field.name not in MAGIC_FIELDS
                    and not field.is_hide_blacklist_model_inherit
                    and (
                        not is_whitelist
                        or (
                            is_whitelist
                            and field.is_show_whitelist_model_inherit_call()
                        )
                    )
                )
            else:
                father_ids = self.env["ir.model"].browse(
                    [a.depend_id.id for a in model.inherit_model_ids]
                )
                set_unique_field = set()
                for father_id in father_ids:
                    fatherfieldnames = father_id.field_id.filtered(
                        lambda field: field.name not in MAGIC_FIELDS
                    ).mapped("name")
                    set_unique_field.update(fatherfieldnames)
                f2exports = f2exports.filtered(
                    lambda field: field.name not in list(set_unique_field)
                )

        # Force field name first
        field_rec_name = model.rec_name if model.rec_name else model._rec_name
        if not field_rec_name:
            field_rec_name = "name"
        lst_field_rec_name = f2exports.filtered(
            lambda field: field.name == field_rec_name
        )
        if lst_field_rec_name:
            lst_field_not_name = f2exports.filtered(
                lambda field: field.name != field_rec_name
            )
            lst_id = lst_field_rec_name.ids + lst_field_not_name.ids
            f2exports = self.env["ir.model.fields"].browse(lst_id)

        for f2export in f2exports:
            # Check odoo/odoo/fields.py in documentation
            cw.emit()
            extra_info = (
                self.env[f2export.model]
                .fields_get(f2export.name)
                .get(f2export.name)
            )
            dct_field_attribute = {}

            code_generator_compute = f2export.get_code_generator_compute()

            # TODO use if cannot find information
            # field_selection = self.env[f2export.model].fields_get(f2export.name).get(f2export.name)

            # Respect sequence in list, order listed by human preference
            if f2export.ttype in ("selection", "reference"):
                str_selection = f2export.get_selection()
                if str_selection:
                    dct_field_attribute["selection"] = str_selection

            if f2export.ttype in ["many2one", "one2many", "many2many"]:
                if f2export.relation:
                    dct_field_attribute["comodel_name"] = f2export.relation

                if f2export.ttype == "one2many" and f2export.relation_field:
                    dct_field_attribute[
                        "inverse_name"
                    ] = f2export.relation_field

                if f2export.ttype == "many2many":
                    # elif f2export.relation_table.startswith("x_"):
                    #     # TODO why ignore relation when start name with x_? Is it about x_name?
                    #     # A relation who begin with x_ is an automated relation, ignore it
                    #     ignored_relation = True
                    if (
                        f2export.relation_table
                        and f"{f2export.model.replace('.', '_')}_id"
                        != f2export.column1
                        and f"{f2export.relation.replace('.', '_')}_id"
                        != f2export.column2
                        and f"{f2export.model.replace('.', '_')}_{f2export.relation.replace('.', '_')}"
                        != f2export.relation_table
                    ):
                        dct_field_attribute[
                            "relation"
                        ] = f2export.relation_table
                        dct_field_attribute["column1"] = f2export.column1
                        dct_field_attribute["column2"] = f2export.column2

                domain_info = extra_info.get("domain")
                if f2export.domain and f2export.domain != "[]":
                    dct_field_attribute["domain"] = f2export.domain
                elif domain_info and domain_info != "[]":
                    dct_field_attribute["domain"] = domain_info

                if (
                    f2export.ttype == "many2one"
                    and f2export.on_delete
                    and f2export.on_delete != "set null"
                ):
                    dct_field_attribute["ondelete"] = f2export.on_delete

            if (
                f2export.field_description
                and f2export.name.replace("_", " ").title()
                != f2export.field_description
            ):
                dct_field_attribute["string"] = f2export.field_description

            if (
                f2export.ttype == "char" or f2export.ttype == "reference"
            ) and f2export.size != 0:
                dct_field_attribute["size"] = f2export.size

            if f2export.related:
                dct_field_attribute["related"] = f2export.related

            if f2export.readonly and not code_generator_compute:
                # TODO force readonly at false when inherit and origin is True
                # Note that a computed field without an inverse method is readonly by default.
                dct_field_attribute["readonly"] = True

            if f2export.required:
                dct_field_attribute["required"] = True

            if f2export.index:
                dct_field_attribute["index"] = True

            if f2export.track_visibility:
                if f2export.track_visibility in ("onchange", "always"):
                    dct_field_attribute[
                        "track_visibility"
                    ] = f2export.track_visibility
                    # TODO is it the good place for this?
                    # lst_depend_model = [
                    #     "mail.thread",
                    #     "mail.activity.mixin",
                    # ]
                    # f2export.model_id.add_model_inherit(lst_depend_model)
                else:
                    _logger.warning(
                        "Cannot support track_visibility value"
                        f" {f2export.track_visibility}, only support"
                        " 'onchange' and 'always'."
                    )

            # Get default value
            default_lambda = f2export.get_default_lambda()
            if default_lambda:
                dct_field_attribute["default"] = default_lambda
            else:
                default_value = None
                if f2export.default:
                    default_value = f2export.default
                else:
                    dct_default_value = self.env[model.model].default_get(
                        [f2export.name]
                    )
                    if dct_default_value:
                        default_value = dct_default_value.get(f2export.name)
                if default_value:
                    # TODO support default = None
                    if f2export.ttype == "boolean" and (
                        default_value == "True" or default_value is True
                    ):
                        dct_field_attribute["default"] = True
                    elif f2export.ttype == "boolean" and (
                        default_value == "False" or default_value is False
                    ):
                        # TODO Only if the field inherit, else None it
                        dct_field_attribute["default"] = False
                    elif f2export.ttype == "integer":
                        dct_field_attribute["default"] = int(default_value)
                    elif f2export.ttype in (
                        "char",
                        "selection",
                        "text",
                        "html",
                    ):
                        dct_field_attribute["default"] = default_value
                    else:
                        _logger.warning(
                            f"Not supported default type '{f2export.ttype}',"
                            f" field name '{f2export.name}', model"
                            f" '{f2export.model_id.model}', value"
                            f" '{default_value}'"
                        )
                        dct_field_attribute["default"] = default_value

            # TODO support states

            if f2export.groups:
                dct_field_attribute["groups"] = f2export.groups.mapped(
                    lambda g: self._get_group_data_name(g)
                )

            compute = f2export.compute and f2export.depends

            if code_generator_compute:
                dct_field_attribute["compute"] = code_generator_compute
            elif compute:
                dct_field_attribute["compute"] = f"_compute_{f2export.name}"

            if (
                f2export.ttype == "one2many" or f2export.related or compute
            ) and f2export.copied:
                dct_field_attribute["copy"] = True

            # TODO support oldname

            # TODO support group_operator

            # TODO support inverse

            # TODO support search

            # TODO support store
            if f2export.store and code_generator_compute:
                dct_field_attribute["store"] = True
            elif not f2export.store and not code_generator_compute:
                # By default, a computed field is not stored to the database, and is computed on-the-fly.
                dct_field_attribute["store"] = False

            # TODO support compute_sudo

            if f2export.translate:
                dct_field_attribute["translate"] = True

            if not f2export.selectable and f2export.ttype == "one2many":
                dct_field_attribute["selectable"] = False

            # TODO support digits, check dp.get_precision('Account')

            if f2export.help:
                dct_field_attribute["help"] = f2export.help.replace("\\'", '"')

            # Ignore it, by default it's copy=False
            # elif f2export.ttype != 'one2many' and not f2export.related and not compute and not f2export.copied:
            #     dct_field_attribute["copy"] = False

            lst_attribute_to_filter = []
            if (
                f2export.code_generator_ir_model_fields_ids
                and f2export.code_generator_ir_model_fields_ids.filter_field_attribute
            ):
                # Filter list of attribute
                lst_attribute_to_filter = f2export.code_generator_ir_model_fields_ids.filter_field_attribute.split(
                    ";"
                )
                lst_attribute_to_filter = [
                    a.strip() for a in lst_attribute_to_filter if a.strip()
                ]

            has_endline = False
            lst_first_field_attribute = []
            lst_field_attribute = []
            lst_last_field_attribute = []
            for key, value in dct_field_attribute.items():
                if (
                    lst_attribute_to_filter
                    and key not in lst_attribute_to_filter
                ):
                    continue
                if type(value) is str:
                    # TODO find another solution than removing \n, this cause error with cw.CodeWriter
                    copy_value = value.replace("'", "\\'")
                    value = value.replace("\n", " ").replace("'", "\\'")
                    if key == "comodel_name":
                        lst_first_field_attribute.append(f"{key}='{value}'")
                    elif key == "ondelete":
                        lst_last_field_attribute.append(f"{key}='{value}'")
                    else:
                        if key == "default":
                            if (
                                value.startswith("lambda")
                                or value.startswith("date")
                                or value.startswith("datetime")
                            ):
                                # Exception for lambda
                                lst_field_attribute.append(f"{key}={value}")
                            else:
                                if "\n" in copy_value:
                                    has_endline = True
                                    lst_field_attribute.append(
                                        f"{key}='''{copy_value}'''"
                                    )
                                else:
                                    lst_field_attribute.append(
                                        f"{key}='{copy_value}'"
                                    )
                        else:
                            lst_field_attribute.append(f"{key}='{value}'")
                elif type(value) is list:
                    # TODO find another solution than removing \n, this cause error with cw.CodeWriter
                    new_value = str(value).replace("\n", " ")
                    lst_field_attribute.append(f"{key}={new_value}")
                else:
                    lst_field_attribute.append(f"{key}={value}")

            lst_field_attribute = (
                lst_first_field_attribute
                + lst_field_attribute
                + lst_last_field_attribute
            )

            if not has_endline:
                cw.emit_list(
                    lst_field_attribute,
                    ("(", ")"),
                    before=(
                        f"{f2export.name} ="
                        f" {self._get_odoo_ttype_class(f2export.ttype)}"
                    ),
                )
            else:
                cw.emit(
                    f"{f2export.name} ="
                    f" {self._get_odoo_ttype_class(f2export.ttype)}("
                )
                with cw.indent():
                    for item in lst_field_attribute:
                        if "\n" in item:
                            lst_item = item.split("\n")
                            cw.emit(f"{lst_item[0]}")
                            i_last = len(lst_item) - 2
                            for i, inter_item in enumerate(lst_item[1:]):
                                if i == i_last:
                                    cw.emit_raw(f"{inter_item},\n")
                                else:
                                    cw.emit_raw(f"{inter_item}\n")
                        else:
                            cw.emit(f"{item},")
                cw.emit(")")

            if compute:
                cw.emit()
                l_depends = self._get_l_map(
                    lambda e: e.strip(), f2export.depends.split(",")
                )

                cw.emit(
                    f"@api.depends({self._prepare_compute_constrained_fields(l_depends)})"
                )
                cw.emit(f"def _compute_{f2export.name}(self):")

                l_compute = f2export.compute.split("\n")
                # starting_spaces = 2
                # for line in l_compute:
                #     if self._get_starting_spaces(line) == 2:
                #         starting_spaces += 1
                #     l_model_fields.append('%s%s' % (TAB4 * starting_spaces, line.strip()))
                for line in l_compute:
                    with cw.indent():
                        cw.emit(line.rstrip())

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create log of code generator writer
        :return:
        """
        new_list = []
        for vals in vals_list:
            new_list.append(self.generate_writer(vals))

        return super(CodeGeneratorWriter, self).create(new_list)

    def get_lst_file_generate(self, module, python_controller_writer):
        l_model_csv_access = []
        l_model_rules = []

        module.view_file_sync = {}
        module.module_file_sync = {}

        if module.template_model_name or module.template_inherit_model_name:
            i = -1
            lst_model = f"{module.template_model_name};{module.template_inherit_model_name}".split(
                ";"
            )
            for model in lst_model:
                i += 1
                model = model.strip()
                if model:
                    module.view_file_sync[model] = ExtractorView(
                        module, model, i
                    )
                    module.module_file_sync[model] = ExtractorModule(
                        module, model, module.view_file_sync[model]
                    )
                    # TODO no need to keep memory
                    ExtractorController(
                        module, model, module.module_file_sync[model]
                    )

        for model in module.o2m_models:

            model_model = self._get_model_model(model.model)

            if not module.nomenclator_only:
                # Wizard
                self._set_model_py_file(module, model, model_model)
                self._set_model_xmlview_file(module, model, model_model)

                # Report
                self._set_model_xmlreport_file(module, model, model_model)

            parameters = self.env["ir.config_parameter"].sudo()
            s_data2export = parameters.get_param(
                "code_generator.s_data2export", default="nomenclator"
            )
            if s_data2export != "nomenclator" or (
                s_data2export == "nomenclator" and model.nomenclator
            ):
                self._set_model_xmldata_file(module, model, model_model)

            if not module.nomenclator_only:
                l_model_csv_access += self._get_model_access(module, model)

                l_model_rules += self._get_model_rules(module, model)

        l_model_csv_access = sorted(
            list(set(l_model_csv_access)),
            key=lambda x: x,
        )

        if not module.nomenclator_only:
            application_icon = self._set_module_menus(module)

            self.set_xml_data_file(module)

            self.set_xml_views_file(module)

            self.set_module_python_file(module)

            self.set_module_css_file(module)

            self._set_module_security(
                module, l_model_rules, l_model_csv_access
            )

            self._set_static_description_file(module, application_icon)

            # TODO info Moved in template module
            # self.set_module_translator(module)

        python_controller_writer.generate()

        self.set_extra_get_lst_file_generate(module)

        self.code_generator_data.reorder_manifest_data_files()

        self._set_manifest_file(module)

        self.set_module_init_file_extra(module)

        self.code_generator_data.generate_python_init_file(module)

        self.code_generator_data.auto_format()
        if module.enable_pylint_check:
            # self.code_generator_data.flake8_check()
            self.code_generator_data.pylint_check()

    def set_xml_data_file(self, module):
        pass

    def set_xml_views_file(self, module):
        pass

    def set_module_css_file(self, module):
        pass

    def set_module_python_file(self, module):
        pass

    def set_extra_get_lst_file_generate(self, module):
        pass

    @api.multi
    def generate_writer(self, vals):
        modules = self.env["code.generator.module"].browse(
            vals.get("code_generator_ids")
        )

        # path = tempfile.gettempdir()
        path = tempfile.mkdtemp()
        _logger.info(f"Temporary path for code generator: {path}")
        morethanone = len(modules.ids) > 1
        if morethanone:
            # TODO validate it's working
            path += "/modules"
            CodeGeneratorData.os_make_dirs(path)

        # TODO is it necessary? os.chdir into sync_code to be back to normal
        # os.chdir(path=path)

        basename = (
            "modules" if morethanone else modules[0].name.lower().strip()
        )
        vals["basename"] = basename
        rootdir = (
            path
            if morethanone
            else path + "/" + modules[0].name.lower().strip()
        )
        vals["rootdir"] = rootdir

        for module in modules:
            # TODO refactor this to share variable in another class,
            #  like that, self.code_generator_data will be associate to a class of generation of module
            self.code_generator_data = CodeGeneratorData(module, path)
            python_controller_writer = PythonControllerWriter(
                module, self.code_generator_data
            )
            self.get_lst_file_generate(module, python_controller_writer)

            if module.enable_sync_code:
                self.code_generator_data.sync_code(
                    module.path_sync_code, module.name
                )

        vals["list_path_file"] = ";".join(
            self.code_generator_data.lst_path_file
        )

        return vals

    def get_list_path_file(self):
        return self.list_path_file.split(";")
