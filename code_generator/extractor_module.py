import logging
import os
import glob
import ast
from .extractor_module_file import ExtractorModuleFile

_logger = logging.getLogger(__name__)


class ExtractorModule:
    def __init__(self, module, model_model, view_file_sync_model):
        self.is_enabled = False
        self.working_directory = module.path_sync_code
        self.view_file_sync_model = view_file_sync_model
        self.module = module
        self.model = model_model
        self.model_id = module.env["ir.model"].search(
            [("model", "=", model_model)], limit=1
        )
        self.dct_model = view_file_sync_model.dct_model
        self.py_filename = ""
        if not module.template_module_path_generated_extension:
            _logger.warning(
                f"The variable template_module_path_generated_extension is"
                f" empty."
            )
            return
        if not self.model_id:
            _logger.warning(f"Cannot found module {model_model}.")
            return

        relative_path_generated_module = (
            module.template_module_path_generated_extension.replace(
                "'", ""
            ).replace(", ", "/")
        )
        template_directory = os.path.normpath(
            os.path.join(
                module.path_sync_code,
                relative_path_generated_module,
                module.template_module_name,
            )
        )
        manifest_file_path = os.path.normpath(
            os.path.join(
                template_directory,
                "__manifest__.py",
            )
        )

        if module.template_module_id and os.path.isfile(manifest_file_path):
            with open(manifest_file_path, "r") as source:
                lst_line = source.readlines()
                i = 0
                for line in lst_line:
                    if line.startswith("{"):
                        break
                    i += 1
            str_line = "".join(lst_line[:i]).strip()
            module.template_module_id.header_manifest = str_line
            dct_data = ast.literal_eval("".join(lst_line[i:]).strip())
            external_dep = dct_data.get("external_dependencies")
            if external_dep:
                if type(external_dep) is dict:
                    for key, lst_value in external_dep.items():
                        if type(lst_value) is list:
                            for value in lst_value:
                                v = {
                                    "module_id": module.id,
                                    "depend": value,
                                    "application_type": key,
                                    "is_template": True,
                                }
                                self.module.env[
                                    "code.generator.module.external.dependency"
                                ].create(v)
                        else:
                            _logger.warning(
                                "Unknown value type external_dependencies"
                                f" in __manifest__ key {key}, value"
                                f" {value}."
                            )
                else:
                    _logger.warning(
                        "Unknown external_dependencies in __manifest__"
                        f" {external_dep}"
                    )

        elif not module.template_module_id:
            _logger.warning(
                "Missing template_module_id in module to extract information."
            )
        elif not os.path.isfile(manifest_file_path):
            _logger.warning(
                "Missing __manifest__.py file in directory"
                f" '{template_directory}' to extract information."
            )

        path_generated_module = os.path.normpath(
            os.path.join(
                module.path_sync_code,
                relative_path_generated_module,
                module.template_module_name,
                "**",
                "*.py",
            )
        )
        lst_py_file = glob.glob(path_generated_module)
        if not lst_py_file:
            return
        for py_file in lst_py_file:
            filename = py_file.split("/")[-1]
            if filename == "__init__.py":
                continue
            with open(py_file, "r") as source:
                f_lines = source.read()
                f_ast = ast.parse(f_lines)
                class_model_ast, next_model_ast = self.search_class_model(
                    f_ast
                )
                if class_model_ast:
                    extract_file = ExtractorModuleFile(
                        module,
                        filename,
                        f_lines,
                        class_model_ast,
                        self.dct_model,
                        self.model,
                        self.view_file_sync_model,
                        self.model_id,
                        next_model_ast,
                    )
                    extract_file.extract()

        self.is_enabled = True

    def search_class_model(self, f_ast):
        find_children = None
        for children in f_ast.body:
            if find_children:
                # children is next node
                return find_children, children
            # TODO check bases of class if equal models.Model for better performance
            # TODO check multiple class
            if type(children) == ast.ClassDef:
                # Detect good _name
                for node in children.body:
                    if (
                        type(node) is ast.Assign
                        and node.targets
                        and type(node.targets[0]) is ast.Name
                        and node.targets[0].id in ("_name", "_inherit")
                    ):
                        if (
                            type(node.value) is ast.Str
                            and node.value.s == self.model
                            or type(node.value) is ast.List
                            and self.model in [a.s for a in node.value.elts]
                        ):
                            find_children = children
                            break

        return find_children, None
