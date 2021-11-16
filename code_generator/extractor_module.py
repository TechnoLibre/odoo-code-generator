import logging
import os
import glob
import ast
import astor


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
                class_model_ast = self.search_class_model(f_ast)
                if class_model_ast:
                    extract_file = ExtractModuleFile(
                        module,
                        filename,
                        f_lines,
                        class_model_ast,
                        self.dct_model,
                        self.model,
                        self.view_file_sync_model,
                        self.model_id,
                    )
                    extract_file.extract()

        self.is_enabled = True

    def search_class_model(self, f_ast):
        for children in f_ast.body:
            # TODO check bases of class if equal models.Model for better performance
            # TODO check multiple class
            if type(children) == ast.ClassDef:
                # Detect good _name
                for node in children.body:
                    if (
                        type(node) is ast.Assign
                        and node.targets
                        and type(node.targets[0]) is ast.Name
                        and node.targets[0].id == "_name"
                        and node.value.s == self.model
                        and type(node.value) is ast.Str
                    ):
                        return children


class ExtractModuleFile:
    def __init__(
        self,
        module,
        filename,
        f_lines,
        class_model_ast,
        dct_model,
        model,
        view_file_sync_model,
        model_id,
    ):
        self.module = module
        self.py_filename = filename
        self.lst_line = f_lines.split("\n")
        self.class_model_ast = class_model_ast
        self.dct_model = dct_model
        self.model = model
        self.view_file_sync_model = view_file_sync_model
        self.model_id = model_id

    def extract(self):
        self.search_field()
        # Fill method
        self.search_import()
        self.search_method()

    def extract_lambda(self, node):
        result = astor.to_source(node).strip().replace("\n", "")
        if result[0] == "(" and result[-1] == ")":
            result = result[1:-1]
        return result

    def _fill_search_field(self, ast_obj, var_name=""):
        ast_obj_type = type(ast_obj)
        if ast_obj_type is ast.Str:
            result = ast_obj.s
        elif ast_obj_type is ast.Lambda:
            result = self.extract_lambda(ast_obj)
        elif ast_obj_type is ast.NameConstant:
            result = ast_obj.value
        elif ast_obj_type is ast.Num:
            result = ast_obj.n
        elif ast_obj_type is ast.Name:
            result = ast_obj.id
        elif ast_obj_type is ast.Attribute:
            # Support -> fields.Date.context_today
            parent_node = ast_obj
            lst_call_lambda = []
            while hasattr(parent_node, "value"):
                lst_call_lambda.insert(0, parent_node.attr)
                parent_node = parent_node.value
            lst_call_lambda.insert(0, parent_node.id)
            result = ".".join(lst_call_lambda)
        elif ast_obj_type is ast.List:
            result = [
                self._fill_search_field(a, var_name) for a in ast_obj.elts
            ]
        elif ast_obj_type is ast.Dict:
            result = {
                self._fill_search_field(k, var_name): self._fill_search_field(
                    ast_obj.values[i], var_name
                )
                for (i, k) in enumerate(ast_obj.keys)
            }
        elif ast_obj_type is ast.Tuple:
            result = tuple(
                [self._fill_search_field(a, var_name) for a in ast_obj.elts]
            )
        else:
            result = None
            _logger.error(
                f"Cannot support keyword of variable {var_name} type"
                f" {ast_obj_type} in filename {self.py_filename}."
            )
        return result

    def search_field(self):
        if self.dct_model[self.model]:
            dct_field = self.dct_model[self.model]
        else:
            dct_field = {}
            self.dct_model[self.model] = dct_field
        lst_var_name_check = []

        sequence = -1
        for node in self.class_model_ast.body:
            sequence += 1
            if (
                type(node) is ast.Assign
                and type(node.value) is ast.Call
                and node.value.func.value.id == "fields"
            ):
                var_name = node.targets[0].id
                d = {
                    "type": node.value.func.attr,
                    "code_generator_sequence": sequence,
                }
                for keyword in node.value.keywords:
                    value = self._fill_search_field(keyword.value, var_name)
                    # Waste to stock None value
                    if value is not None:
                        d[keyword.arg] = value
                if (
                    self.view_file_sync_model
                    and self.view_file_sync_model.module_attr
                ):
                    dct_module_attr = (
                        self.view_file_sync_model.module_attr.get(self.model)
                    )
                    if dct_module_attr:
                        dct_field_module_attr = dct_module_attr.get(var_name)
                        if dct_field_module_attr:
                            for (
                                attr_key,
                                attr_value,
                            ) in dct_field_module_attr.items():
                                d[attr_key] = attr_value

                if var_name in dct_field:
                    dct_field[var_name].update(d)
                else:
                    dct_field[var_name] = d
                lst_var_name_check.append(var_name)
        # Remove item not from this list
        lst_var_name_to_delete = list(
            set(dct_field.keys()).difference(set(lst_var_name_check))
        )
        for var_name_to_delete in lst_var_name_to_delete:
            del dct_field[var_name_to_delete]

    def _extract_decorator(self, decorator_list):
        str_decorator = ""
        for dec in decorator_list:
            if type(dec) is ast.Attribute:
                v = f"@{dec.value.id}.{dec.attr}"
            elif type(dec) is ast.Call:
                args = [
                    f'\\"{self._fill_search_field(a)}\\"' for a in dec.args
                ]
                str_arg = ", ".join(args)
                v = f"@{dec.func.value.id}.{dec.func.attr}({str_arg})"
            elif type(dec) is ast.Name:
                v = f"@{dec.id}"
            else:
                _logger.warning(f"Decorator type {type(dec)} not supported.")
                v = None

            if v:
                if str_decorator:
                    str_decorator += f";{v}"
                else:
                    str_decorator = v
        return str_decorator

    def _write_exact_argument(self, value):
        str_args = ""
        if type(value) is ast.arg:
            if hasattr(value, "is_vararg") and value.is_vararg:
                str_args += "*"
            if hasattr(value, "is_kwarg") and value.is_kwarg:
                str_args += "**"
            str_args += value.arg
            if value.annotation:
                str_args += f": {value.annotation.id}"
        else:
            v = self._fill_search_field(value)
            if type(v) is str:
                str_args += f"='{v}'"
            else:
                str_args += f"={v}"
        return str_args

    def _extract_argument(self, ast_argument):
        dct_args = {}
        # Need to regroup different element in order
        # Create dict with all element
        if ast_argument.args:
            for arg in ast_argument.args:
                dct_args[(arg.lineno, arg.col_offset)] = arg
        if ast_argument.defaults:
            for arg in ast_argument.defaults:
                dct_args[(arg.lineno, arg.col_offset)] = arg
        if ast_argument.kwonlyargs:
            for arg in ast_argument.kwonlyargs:
                dct_args[(arg.lineno, arg.col_offset)] = arg
        if ast_argument.kw_defaults:
            for arg in ast_argument.kw_defaults:
                dct_args[(arg.lineno, arg.col_offset)] = arg
        if ast_argument.vararg:
            arg = ast_argument.vararg
            arg.is_vararg = True
            dct_args[(arg.lineno, arg.col_offset)] = arg
        if ast_argument.kwarg:
            arg = ast_argument.kwarg
            arg.is_kwarg = True
            dct_args[(arg.lineno, arg.col_offset)] = arg

        # Regroup all extra associated with arg
        str_args = ""
        lst_key_sorted = sorted(dct_args.keys())
        lst_group_arg = []
        last_lst_item = []
        for key in lst_key_sorted:
            value = dct_args[key]
            if type(value) is ast.arg:
                # new item
                last_lst_item = [value]
                lst_group_arg.append(last_lst_item)
            else:
                last_lst_item.append(value)

        # Recreate string of argument
        for lst_value in lst_group_arg[:-1]:
            for value in lst_value:
                str_args += self._write_exact_argument(value)
            str_args += ", "
        last_value = lst_group_arg[-1]
        if last_value:
            for value in last_value:
                str_args += self._write_exact_argument(value)
        return str_args

    def _get_nb_line_multiple_string(
        self, item, lst_line, i_lineno, extra_size=2
    ):
        str_size = len(item.s)
        line_size = len(lst_line[i_lineno - 1].strip())
        if line_size != str_size + extra_size:
            # Try detect multiline string with pending technique like
            # """test1"""
            # """test2"""
            # This will be """test1test2"""
            # or
            # "test1"
            # "test2"
            # This will be "test1test2"
            # So if next line is bigger size then full string, it's the end of multiple string line
            i = 0
            line_size += len(lst_line[i_lineno + i].strip())
            while line_size < str_size + extra_size:
                i += 1
            i_lineno += i + 1
        return i_lineno

    def _get_recursive_lineno(self, item, set_lineno, lst_line):
        if hasattr(item, "lineno"):
            lineno = getattr(item, "lineno")
            if lineno:
                i_lineno = item.lineno
                if type(item) is ast.Str:
                    if "\n" in item.s:
                        # -1 to ignore last \n
                        i_lineno = item.lineno - item.s.count("\n")
                    elif lst_line[i_lineno - 1][-3:] == '"""':
                        i_lineno = self._get_nb_line_multiple_string(
                            item, lst_line, i_lineno, extra_size=6
                        )
                    elif lst_line[i_lineno - 1][-1] == '"':
                        i_lineno = self._get_nb_line_multiple_string(
                            item, lst_line, i_lineno
                        )
                set_lineno.add(i_lineno)

        # Do recursive search, search last line of code
        lst_attr = [
            "body",
            "finalbody",
            "orelse",
            "handlers",
            "test",
            "right",
            "left",
            "value",
            "exc",
            "ctx",
            "func",
            "args",
            "elts",
        ]
        for attr in lst_attr:
            if not hasattr(item, attr):
                continue
            lst_attr_item = getattr(item, attr)
            if not lst_attr_item:
                continue
            if type(lst_attr_item) is list:
                for attr_item in lst_attr_item:
                    if attr_item:
                        self._get_recursive_lineno(
                            attr_item, set_lineno, lst_line
                        )
            elif type(lst_attr_item) in (
                ast.Compare,
                ast.Call,
                ast.Str,
                ast.Num,
                ast.Attribute,
                ast.JoinedStr,
                ast.BinOp,
                ast.NameConstant,
                ast.Name,
                ast.arguments,
                ast.Load,
                ast.List,
                ast.ListComp,
                ast.IfExp,
                ast.Subscript,
                ast.UnaryOp,
                ast.BoolOp,
                ast.Dict,
                ast.Tuple,
                bool,
            ):
                # Check type, but in fact, can accept all type.
                # This check is only to understand what style of code we read
                self._get_recursive_lineno(lst_attr_item, set_lineno, lst_line)
            else:
                try:
                    self._get_recursive_lineno(
                        lst_attr_item, set_lineno, lst_line
                    )
                    _logger.warning(
                        f"From get recursive '{attr}' unknown type, add type"
                        f" '{type(lst_attr_item)}'"
                    )
                except Exception as e:
                    _logger.warning(
                        f"From get recursive '{attr}' unknown type"
                        f" {type(lst_attr_item)}."
                    )

    def _get_min_max_no_line(self, node, lst_line):
        # hint node.name == ""
        set_lineno = set()
        lst_body = []
        if len(node.body) > 1:
            lst_body.append(node.body[0])
            lst_body.append(node.body[-1])
        else:
            lst_body.append(node.body[0])
        for body in lst_body:
            self._get_recursive_lineno(body, set_lineno, lst_line)
        return min(set_lineno), max(set_lineno)

    def search_import(self):
        # get all line until meet "class "
        i = 0
        for line in self.lst_line:
            if line.startswith("class "):
                break
            i += 1
        else:
            _logger.warning(
                "Don't know what to do when missing class in python file..."
            )

        str_code = "\n".join(self.lst_line[:i])
        str_code = str_code.strip()
        if "'''" in str_code:
            str_code = str_code.replace("'''", "\\'''")
        if "\\n" in str_code:
            str_code = str_code.replace("\\n", "\\\\n")
        d = {
            "m2o_model": self.model_id.id,
            "m2o_module": self.module.id,
            "code": str_code,
            "name": "header",
            "is_templated": True,
        }
        if not self.module.env["code.generator.model.code.import"].search(
            [
                ("m2o_model", "=", self.model_id.id),
                ("m2o_module", "=", self.module.id),
                ("code", "=", str_code),
            ],
            limit=1,
        ):
            self.module.env["code.generator.model.code.import"].create(d)

    def search_method(self):
        sequence = -1
        lst_body = [a for a in self.class_model_ast.body]
        for i in range(len(lst_body)):
            node = lst_body[i]
            if i + 1 < len(lst_body):
                next_node = lst_body[i + 1]
            else:
                next_node = None
            if type(node) is ast.Assign:
                if node.targets:
                    if node.targets[0].id == "_description":
                        value = self._fill_search_field(node.value)
                        self.model_id.description = value
                    elif node.targets[0].id == "_inherit":
                        value = self._fill_search_field(node.value)
                        if type(value) is list:
                            model_id = self.module.env["ir.model"].search(
                                [("model", "in", value)]
                            )
                        else:
                            model_id = self.module.env["ir.model"].search(
                                [("model", "=", value)]
                            )
                        if not model_id:
                            _logger.warning(f"Cannot identify model {value}.")
                        else:
                            self.model_id.add_model_inherit(model_id)
                    elif node.targets[0].id == "_sql_constraints":
                        lst_value = self._fill_search_field(node.value)
                        constraint_ids = self.module.env[
                            "ir.model.constraint"
                        ].search(
                            [
                                (
                                    "module",
                                    "=",
                                    self.module.template_module_id.id,
                                )
                            ]
                        )
                        model_name = self.model_id.model.replace(".", "_")
                        for value in lst_value:
                            name = value[0]
                            db_name = f"{model_name}_{name}"
                            definition = value[1]
                            message = value[2]
                            _logger.warning(
                                "Ignore next error about ALTER TABLE DROP"
                                " CONSTRAINT."
                            )
                            constraint_id = constraint_ids.search(
                                [("name", "=", db_name)]
                            )
                            if constraint_id:
                                constraint_id.definition = definition
                                constraint_id.message = message
            elif type(node) is ast.FunctionDef:
                sequence += 1
                d = {
                    "m2o_model": self.model_id.id,
                    "m2o_module": self.module.id,
                    "name": node.name,
                    "sequence": sequence,
                    "is_templated": True,
                }
                if node.args:
                    d["param"] = self._extract_argument(node.args)
                if node.returns:
                    d["returns"] = node.returns.id
                if node.decorator_list:
                    str_decorator = self._extract_decorator(
                        node.decorator_list
                    )
                    d["decorator"] = str_decorator
                no_line_min, no_line_max = self._get_min_max_no_line(
                    node, self.lst_line
                )
                # Ignore this no_line_max, bug some times.
                # no_line_min = min([a.lineno for a in node.body])
                if next_node:
                    no_line_max = next_node.lineno - 1
                else:
                    # TODO this will bug with multiple class
                    no_line_max = len(self.lst_line)
                codes = ""
                for line in self.lst_line[no_line_min - 1 : no_line_max]:
                    if line.startswith(" " * 8):
                        str_line = line[8:]
                    else:
                        str_line = line
                    codes += f"{str_line}\n"
                # codes = "\n".join(self.lst_line[no_line_min - 1:no_line_max])
                if "'''" in codes:
                    codes = codes.replace("'''", "\\'''")
                if "\\n" in codes:
                    codes = codes.replace("\\n", "\\\\n")
                d["code"] = codes.strip()
                self.module.env["code.generator.model.code"].create(d)
