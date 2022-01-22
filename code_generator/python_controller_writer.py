import logging
from collections import defaultdict

from code_writer import CodeWriter

_logger = logging.getLogger(__name__)


class PythonControllerWriter:
    # TODO this can be move in code_generator_data
    def __init__(self, module, code_generator_data):
        self._module = module
        self._code_generator_data = code_generator_data
        self.dct_cb = defaultdict(list)

    def add_controller(
        self,
        filename,
        lst_header,
        cb_write_function,
        inherit_class="http.Controller",
        enable_logger=False,
    ):
        self.dct_cb[filename].append(
            (lst_header, cb_write_function, inherit_class, enable_logger)
        )

    def generate(self):
        for file_path, lst_info in self.dct_cb.items():
            cw = CodeWriter()
            lst_header = [b for a in lst_info for b in a[0]]
            # Fix divergence import
            try:
                index_pos = lst_header.index("import odoo.http as http")
                lst_header.pop(index_pos)
                lst_header.append("from odoo import http")
            except:
                pass

            set_header = set(lst_header)
            lst_cb = [a[1] for a in lst_info]
            enable_logger = any([a[3] for a in lst_info])
            lst_inherit_class = list(set([a[2] for a in lst_info]))

            if len(lst_inherit_class) > 1:
                _logger.error(
                    "Cannot support multiple class in the same python file:"
                    f" '{lst_inherit_class}', filepath: '{file_path}'"
                )
                continue
            str_inherit_class = lst_inherit_class[0]

            for line in set_header:
                cw.emit(line)

            if enable_logger:
                cw.emit("import logging")
                cw.emit("_logger = logging.getLogger(__name__)")

            cw.emit(
                "class"
                f" {self._module.name.replace('_', ' ').title().replace(' ', '')}Controller({str_inherit_class}):"
            )

            with cw.indent():
                for cb in lst_cb:
                    cb(self._module, cw)

            out = cw.render()

            l_model = out.split("\n")

            self._code_generator_data.write_file_lst_content(
                file_path, l_model
            )
