import io
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from odoo import http
from odoo.http import content_disposition, request


def _get_l_map(fn, collection):
    """
    Util function to get a list of a map operation
    :param fn:
    :param collection:
    :return:
    """

    return list(map(fn, collection))


class CodeGeneratorZipFile(ZipFile):
    """
    Code Generator ZipFile class
    """

    def write_end_record_without_closing(self):
        """
        Util function to write the 'end records' of a  Zip file without call the close method
        :return:
        """

        with self._lock:
            if self._seekable:
                self.fp.seek(self.start_dir)
            self._write_end_record()


class CodeGeneratorController(http.Controller):
    @http.route(
        "/code_generator/<string:module_ids>", auth="user", type="http"
    )
    def code_generator(self, module_ids, **kwargs):
        """
        Function to export into code
        :param module_ids:
        :param kwargs:
        :return:
        """

        modules = request.env["code.generator.module"].browse(
            _get_l_map(lambda pk: int(pk), module_ids.split(","))
        )

        id_code_generator_ids = modules.ids

        value = {"code_generator_ids": id_code_generator_ids}
        code_generator_writer = request.env["code.generator.writer"].create(
            value
        )

        bytesio = io.BytesIO()
        zipy = CodeGeneratorZipFile(
            bytesio, mode="w", compression=ZIP_DEFLATED
        )

        # Parameter
        lst_path_file = code_generator_writer.get_list_path_file()
        rootdir = code_generator_writer.rootdir
        basename = code_generator_writer.basename

        # Create ZIP
        for path_file in lst_path_file:
            zipy.write(path_file)

        assert zipy.testzip() is None

        bytesio.seek(0)

        zipy.write_end_record_without_closing()

        response = request.make_response(
            zipy.fp.getvalue(),
            headers=[
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET"),
                (
                    "Content-Disposition",
                    content_disposition("%s.zip" % basename),
                ),
                ("Content-Type", "application/zip"),
            ],
        )

        zipy.close()

        shutil.rmtree(rootdir, ignore_errors=True)

        return response
