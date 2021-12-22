import copy
import logging
import os
import shutil
import subprocess
from collections import defaultdict

import html5print
import xmlformatter
from code_writer import CodeWriter

_logger = logging.getLogger(__name__)


class CodeGeneratorData:
    def __init__(self, module, path):
        self._lst_models_init_imports = []
        self._lst_wizards_init_imports = []
        self._lst_controllers_init_imports = []
        self._lst_path_file = set()
        self._dct_data_depend = defaultdict(list)
        self._dct_data_metadata_file = defaultdict(list)
        self._path = path
        self._module_name = module.name.lower().strip()
        self._module_path = os.path.join(path, self._module_name)
        self._data_path = "data"
        self._demo_path = "demo"
        self._tests_path = "tests"
        self._i18n_path = "i18n"
        self._migrations_path = "migrations"
        self._readme_path = "readme"
        self._components_path = "components"
        self._models_path = "models"
        self._css_path = os.path.join("static", "src", "scss")
        self._security_path = "security"
        self._views_path = "views"
        self._wizards_path = "wizards"
        self._controllers_path = "controllers"
        self._reports_path = "report"
        self._static_description_path = os.path.join("static", "description")
        self._lst_manifest_data_files = []
        self._dct_import_dir = defaultdict(list)
        self._dct_extra_module_init_path = defaultdict(list)
        self._dct_view_id = {}
        # Copy not_supported_files first and permit code to overwrite it
        self.copy_not_supported_files(module)

    def copy_not_supported_files(self, module):
        # TODO this is an hack to get code_generator module to search not_supported_files
        # TODO refactor this and move not_supported_files in models, this is wrong conception
        if not module.icon:
            return

        origin_path = os.path.normpath(
            os.path.join(module.icon, "..", "..", "..", "not_supported_files")
        )
        if os.path.isdir(origin_path):
            for root, dirs, files in os.walk(origin_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.join(
                        root[len(origin_path) + 1 :], file
                    )
                    _, ext = os.path.splitext(relative_path)
                    is_data_file = ext == ".xml"
                    self.copy_file(
                        file_path, relative_path, data_file=is_data_file
                    )

    @staticmethod
    def os_make_dirs(path, exist_ok=True):
        """
        Util function to wrap the makedirs method
        :param path:
        :param exist_ok:
        :return:
        """
        os.makedirs(path, exist_ok=exist_ok)

    @property
    def lst_path_file(self):
        return list(self._lst_path_file)

    @property
    def dct_data_depend(self):
        return self._dct_data_depend

    @property
    def dct_data_metadata_file(self):
        return self._dct_data_metadata_file

    @property
    def module_path(self):
        return self._module_path

    @property
    def data_path(self):
        return self._data_path

    @property
    def demo_path(self):
        return self._demo_path

    @property
    def tests_path(self):
        return self._tests_path

    @property
    def i18n_path(self):
        return self._i18n_path

    @property
    def migrations_path(self):
        return self._migrations_path

    @property
    def readme_path(self):
        return self._readme_path_path

    @property
    def components_path(self):
        return self._components_path

    @property
    def models_path(self):
        return self._models_path

    @property
    def css_path(self):
        return self._css_path

    @property
    def security_path(self):
        return self._security_path

    @property
    def views_path(self):
        return self._views_path

    @property
    def wizards_path(self):
        return self._wizards_path

    @property
    def controllers_path(self):
        return self._controllers_path

    @property
    def reports_path(self):
        return self._reports_path

    @property
    def static_description_path(self):
        return self._static_description_path

    @property
    def dct_view_id(self):
        return self._dct_view_id

    @property
    def lst_manifest_data_files(self):
        return self._lst_manifest_data_files

    @property
    def lst_import_dir(self):
        return list(self._dct_import_dir.keys())

    @staticmethod
    def subprocess_cmd(command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        return proc_stdout

    def add_view_id(self, name, str_id):
        self._dct_view_id[name] = str_id

    def add_module_init_path(self, component, import_line):
        self._dct_extra_module_init_path[component].append(import_line)

    def _get_lst_files_data_depends(self, lst_meta):
        set_files = set()
        for meta in lst_meta:
            for file_name, lst_key in self.dct_data_metadata_file.items():
                if meta in lst_key:
                    set_files.add(file_name)
                    break
            else:
                _logger.error(f"Cannot find key {meta}.")
        return list(set_files)

    def reorder_manifest_data_files(self):
        lst_manifest = []
        dct_hold_file = {}
        for manifest_data in self._lst_manifest_data_files:
            if manifest_data in self.dct_data_depend.keys():
                # find dependence and report until order is right
                lst_meta = self.dct_data_depend.get(manifest_data)
                lst_files_depends = self._get_lst_files_data_depends(lst_meta)
                if manifest_data in lst_files_depends:
                    # Remove itself depends
                    lst_files_depends.remove(manifest_data)
                if lst_files_depends:
                    dct_hold_file[manifest_data] = lst_files_depends
                else:
                    lst_manifest.append(manifest_data)
            else:
                lst_manifest.append(manifest_data)

        i = 0
        max_i = len(dct_hold_file) + 1
        origin_dct_hold_file = copy.deepcopy(dct_hold_file)
        while dct_hold_file and i < max_i:
            i += 1
            for new_ele, lst_depend in dct_hold_file.items():
                final_index = -1
                for depend in lst_depend:
                    try:
                        index = lst_manifest.index(depend)
                    except ValueError:
                        # element not in list, continue
                        final_index = -1
                        break
                    if index > final_index:
                        final_index = index
                if final_index >= 0:
                    lst_manifest.insert(final_index + 1, new_ele)
                    del dct_hold_file[new_ele]
                    # Need to break or crash on loop because dict has change
                    break
        if dct_hold_file:
            _logger.error(
                f"Cannot reorder all manifest file: '{dct_hold_file}', origin"
                f" '{origin_dct_hold_file}'"
            )
            # Try to solve it
            for new_ele, lst_depend in dct_hold_file.items():
                lst_manifest.append(new_ele)
        self._lst_manifest_data_files = lst_manifest

    def copy_directory(self, source_directory_path, directory_path):
        """
        Copy only directory without manipulation
        :param source_directory_path:
        :param directory_path:
        :return:
        """
        absolute_path = os.path.join(
            self._path, self._module_name, directory_path
        )
        # self.check_mkdir_and_create(absolute_path, is_file=False)
        status = shutil.copytree(source_directory_path, absolute_path)

    def copy_file(
        self,
        source_file_path,
        file_path,
        data_file=False,
        search_and_replace=None,
    ):
        # TODO if no search_and_replace, use system copy instead of read file and write
        # TODO problem, we need to add the filename in the system when calling write_file_*
        # TODO or document it why using this technique
        with open(source_file_path, "rb") as file_source:
            content = file_source.read()

        if search_and_replace:
            # switch binary to string
            content = content.decode("utf-8")
            for search, replace in search_and_replace:
                content = content.replace(search, replace)
            self.write_file_str(file_path, content, data_file=data_file)
        else:
            self.write_file_binary(file_path, content, data_file=data_file)

    def write_file_lst_content(
        self,
        file_path,
        lst_content,
        data_file=False,
        insert_first=False,
        empty_line_end_of_file=True,
    ):
        """
        Function to create a file with some content
        :param file_path:
        :param lst_content:
        :param data_file:
        :param insert_first:
        :param empty_line_end_of_file:
        :return:
        """

        str_content = "\n".join(lst_content)
        if empty_line_end_of_file and str_content and str_content[-1] != "\n":
            str_content += "\n"

        content = str_content.encode("utf-8")

        try:
            self.write_file_binary(
                file_path,
                content,
                data_file=data_file,
                insert_first=insert_first,
            )
        except Exception as e:
            _logger.error(e)
            raise e

    def write_file_str(
        self, file_path, content, mode="w", data_file=False, insert_first=False
    ):
        """
        Function to create a file with some binary content
        :param file_path:
        :param content:
        :param mode:
        :param data_file:
        :param insert_first:
        :return:
        """
        self.write_file_binary(
            file_path,
            content,
            mode=mode,
            data_file=data_file,
            insert_first=insert_first,
        )

    def write_file_binary(
        self,
        file_path,
        content,
        mode="wb",
        data_file=False,
        insert_first=False,
    ):
        """
        Function to create a file with some binary content
        :param file_path:
        :param content:
        :param mode:
        :param data_file: Will be add in manifest
        :param insert_first:
        :return:
        """

        # file_path suppose to be a relative path
        if file_path[0] == "/":
            _logger.warning(f"Path {file_path} not suppose to start with '/'.")
            file_path = file_path[1:]

        absolute_path = os.path.join(self._path, self._module_name, file_path)
        self._lst_path_file.add(absolute_path)

        if data_file and file_path not in self._lst_manifest_data_files:
            if insert_first:
                self._lst_manifest_data_files.insert(0, file_path)
            else:
                self._lst_manifest_data_files.append(file_path)

        self._check_import_python_file(file_path)

        self.check_mkdir_and_create(absolute_path)

        with open(absolute_path, mode) as file:
            file.write(content)

    @staticmethod
    def _split_path_all(path):
        all_parts = []
        while 1:
            parts = os.path.split(path)
            if parts[0] == path:  # sentinel for absolute paths
                all_parts.insert(0, parts[0])
                break
            elif parts[1] == path:  # sentinel for relative paths
                all_parts.insert(0, parts[1])
                break
            else:
                path = parts[0]
                all_parts.insert(0, parts[1])
        return all_parts

    def _check_import_python_file(self, file_path):
        if file_path and file_path[-3:] == ".py":
            dir_name = os.path.dirname(file_path)
            if dir_name == "tests":
                # Ignore tests python file
                return
            if len(self._split_path_all(dir_name)) > 1:
                # This is a odoo limitation, but we can support it if need it
                _logger.warning(
                    "You add python file more depth of 1 directory."
                )
                return
            python_module_name = os.path.splitext(os.path.basename(file_path))[
                0
            ]
            self._dct_import_dir[dir_name].append(python_module_name)

    @staticmethod
    def check_mkdir_and_create(file_path, is_file=True):
        if is_file:
            path_dir = os.path.dirname(file_path)
        else:
            path_dir = file_path
        CodeGeneratorData.os_make_dirs(path_dir)

    def sync_code(self, directory, name):
        try:
            # if not os.path.isdir(path_sync_code):
            #     osmakedirs(path_sync_code)
            path_sync_code = os.path.join(directory, name)
            if os.path.isdir(path_sync_code):
                shutil.rmtree(path_sync_code)
            shutil.copytree(self._module_path, path_sync_code)
        except Exception as e:
            _logger.error(e)

    def generate_python_init_file(self, cg_module):
        for component, lst_module in self._dct_import_dir.items():
            init_path = os.path.join(component, "__init__.py")
            if not component:
                lst_module = [a for a in self._dct_import_dir.keys() if a]

            lst_module.sort()

            cw = CodeWriter()

            if cg_module.license == "AGPL-3":
                cw.emit(
                    "# License AGPL-3.0 or later"
                    " (https://www.gnu.org/licenses/agpl)"
                )
                cw.emit()
            elif cg_module.license == "LGPL-3":
                cw.emit(
                    "# License LGPL-3.0 or later"
                    " (https://www.gnu.org/licenses/lgpl)"
                )
                cw.emit()
            else:
                _logger.warning(f"License {cg_module.license} not supported.")

            if component:
                for module in lst_module:
                    cw.emit(f"from . import {module}")
            elif lst_module:
                cw.emit(f"from . import {', '.join(lst_module)}")
            for extra_import in self._dct_extra_module_init_path.get(
                component, []
            ):
                cw.emit(extra_import)
            self.write_file_str(init_path, cw.render())

    def flake8_check(self):
        workspace_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        flake8_bin = os.path.join(workspace_path, ".venv", "bin", "flake8")
        config_path = os.path.join(workspace_path, ".flake8")
        cpu_count = os.cpu_count()
        try:
            out = subprocess.check_output(
                [
                    flake8_bin,
                    "-j",
                    str(cpu_count),
                    f"--config={config_path}",
                    self.module_path,
                ]
            )
            result = out
        except subprocess.CalledProcessError as e:
            result = e.output.decode()

        if result:
            _logger.warning(result)

    def pylint_check(self):
        workspace_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        cpu_count = os.cpu_count()
        try:
            out = subprocess.check_output(
                [
                    f"{workspace_path}/.venv/bin/pylint",
                    "-j",
                    str(cpu_count),
                    "--load-plugins=pylint_odoo",
                    "-e",
                    "odoolint",
                    self.module_path,
                ]
            )
            result = out
        except subprocess.CalledProcessError as e:
            result = e.output.decode()

        if result:
            _logger.warning(result)

    def auto_format(self):
        workspace_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        max_col = 79
        use_prettier = True
        use_format_black = True  # Else, oca-autopep8
        use_clean_import_isort = True
        use_html5print = False
        enable_xml_formatter = False  # Else, prettier-xml
        # Manual format with def with programmer style
        for path_file in self.lst_path_file:
            relative_path = path_file[len(self.module_path) + 1 :]
            if path_file.endswith(".py"):
                # TODO not optimal, too many write for nothing
                if not use_format_black:
                    lst_line_write = []
                    has_change = False
                    with open(path_file, "r") as source:
                        for line in source.readlines():
                            if (
                                line.lstrip().startswith("def ")
                                or line.lstrip().startswith("return ")
                            ) and len(line) > max_col - 1:
                                has_change = True
                                next_tab_space = line.find("(") + 1
                                first_cut = max_col
                                first_cut = line.rfind(", ", 0, first_cut) + 1
                                first_part = line[:first_cut]
                                last_part = line[first_cut:].lstrip()
                                str_line = (
                                    f"{first_part}\n{' ' * next_tab_space}{last_part}"
                                )
                                lst_line_write.append(str_line[:-1])
                            else:
                                lst_line_write.append(line[:-1])
                    if has_change:
                        self.write_file_lst_content(
                            relative_path, lst_line_write
                        )

            elif path_file.endswith(".js"):
                if use_prettier:
                    cmd = f"prettier --write --tab-width 4 {path_file}"
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)
                elif use_html5print:
                    with open(path_file, "r") as source:
                        lines = source.read()
                        try:
                            lines_out = html5print.JSBeautifier.beautify(
                                lines, 4
                            )
                            self.write_file_str(relative_path, lines_out)
                        except Exception as e:
                            _logger.error(e)
                            _logger.error(f"Check file {path_file}")
                else:
                    cmd = (
                        f"cd {workspace_path};."
                        f" .venv/bin/activate;css-html-prettify.py {path_file}"
                    )
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.warning(result)

            elif path_file.endswith(".scss") or path_file.endswith(".css"):
                if use_prettier:
                    cmd = f"prettier --write {path_file}"
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)
                elif use_html5print:
                    with open(path_file, "r") as source:
                        lines = source.read()
                        try:
                            lines_out = html5print.CSSBeautifier.beautify(
                                lines, 2
                            )
                            self.write_file_str(relative_path, lines_out)
                        except Exception as e:
                            _logger.error(e)
                            _logger.error(f"Check file {path_file}")
                else:
                    cmd = (
                        f"cd {workspace_path};."
                        f" .venv/bin/activate;css-html-prettify.py {path_file}"
                    )
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.warning(result)

            elif path_file.endswith(".html"):
                if use_prettier:
                    cmd = f"prettier --write {path_file}"
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)
                elif use_html5print:
                    with open(path_file, "r") as source:
                        lines = source.read()
                        try:
                            lines_out = html5print.HTMLBeautifier.beautify(
                                lines, 4
                            )
                            self.write_file_str(relative_path, lines_out)
                        except Exception as e:
                            _logger.error(e)
                            _logger.error(f"Check file {path_file}")
                else:
                    cmd = (
                        f"cd {workspace_path};."
                        f" .venv/bin/activate;css-html-prettify.py {path_file}"
                    )
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.warning(result)

            elif path_file.endswith(".xml"):
                if use_prettier and not enable_xml_formatter:
                    cmd = (
                        "prettier --xml-whitespace-sensitivity ignore"
                        " --prose-wrap always --tab-width 4"
                        " --no-bracket-spacing --print-width 120 --write"
                        f" {path_file}"
                    )
                    result = self.subprocess_cmd(cmd)
                    if result:
                        _logger.info(result)

        # Optimize import python
        if use_clean_import_isort:
            cmd = (
                f"cd {workspace_path};./.venv/bin/isort --profile black -l 79"
                f" {self.module_path}"
            )
            result = self.subprocess_cmd(cmd)

            if result:
                _logger.info(str(result))

        # Automatic format
        # TODO check diff before and after format to auto improvement of generation
        if use_format_black:
            cmd = (
                f"cd {workspace_path};./.venv/bin/black -l"
                f" {max_col} --experimental-string-processing -t py37"
                f" {self.module_path}"
            )
            result = self.subprocess_cmd(cmd)

            if result:
                _logger.warning(result)
        else:
            maintainer_path = os.path.join(
                workspace_path, "script", "OCA_maintainer-tools"
            )
            cpu_count = os.cpu_count()
            cmd = (
                f"cd {maintainer_path};. env/bin/activate;cd"
                f" {workspace_path};oca-autopep8 -j{cpu_count}"
                f" --max-line-length {max_col} -ari {self.module_path}"
            )
            result = self.subprocess_cmd(cmd)

            if result:
                _logger.warning(result)

        if enable_xml_formatter:
            formatter = xmlformatter.Formatter(
                indent="4",
                indent_char=" ",
                selfclose=True,
                correct=True,
                preserve=["pre"],
                blanks=True,
            )
            for path_file in self.lst_path_file:
                if path_file.endswith(".xml"):
                    relative_path = path_file[len(self.module_path) + 1 :]
                    self.write_file_binary(
                        relative_path, formatter.format_file(path_file)
                    )
