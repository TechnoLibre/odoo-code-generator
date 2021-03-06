from odoo import _, api, models, fields, SUPERUSER_ID
from logging import getLogger
import re

logger = getLogger(__name__)

try:
    from pdfminer.pdfparser import PDFParser  # pylint: disable=W0404
    from pdfminer.pdfdocument import PDFDocument  # pylint: disable=W0404
    from pdfminer.pdfpage import PDFPage  # pylint: disable=W0404
    from pdfminer.pdfinterp import PDFResourceManager  # pylint: disable=W0404
    from pdfminer.pdfinterp import PDFPageInterpreter  # pylint: disable=W0404
    from pdfminer.layout import LAParams  # pylint: disable=W0404
    from pdfminer.converter import PDFPageAggregator  # pylint: disable=W0404
    import pdfminer  # pylint: disable=W0404
except ImportError:
    logger.debug('Can not import pdfminer')

# TODO Update keys for your Webfetcher
PDF_PATH = ""
LST_MODEL_FONT = []
LST_FIELD_FONT = []
LST_HELP_FONT = []
LST_DATA_FONT = []
DEBUG_LOGGER = False
NB_SKIP_PAGE = 0
PDF_PASSWORD = ""

lst_menu_line = []


class Working:
    """
    Order
    1. Model
    2. Field
    3. Help
    4. Data

    Field can not exist, and last can be help.
    """

    def __init__(self):
        self.last_line = ""

        self.reset()
        self.lst_result = []

    def reset(self):
        self.lst_model = []
        self.lst_field = []
        self.lst_help = []
        self.lst_data = []

    def check_data(self):
        if self.lst_data:
            value = {
                "help": "\n".join(self.lst_help),
                "field": "\n".join(self.lst_field),
                "model": "\n".join(self.lst_model),
                "data": "\n".join(self.lst_data),
            }
            self.lst_result.append(value)
            self.lst_data = []
            return True
        return False

    def add_model(self, line):
        self.check_data()
        self.reset()
        self.last_line = line
        self.lst_model.append(line)

    def add_field(self, line):
        status = self.check_data()
        if status or self.lst_help:
            self.lst_field = []
            self.lst_help = []

        self.last_line = line
        self.lst_field.append(line)

        while len(self.lst_field) > 1:
            if self.lst_field[0] in lst_menu_line:
                self.lst_field.pop(0)

    def add_help(self, line):
        status = self.check_data()
        if status:
            self.lst_field = []
            self.lst_help = []
        self.last_line = line
        self.lst_help.append(line)

    def add_data(self, line):
        self.last_line = line
        self.lst_data.append(line)

    def get_result(self):
        return self.lst_result


def createPDFDoc():
    fp = open(PDF_PATH, 'rb')
    parser = PDFParser(fp)
    document = PDFDocument(parser, password=PDF_PASSWORD)
    # Check if the document allows text extraction. If not, abort.
    if not document.is_extractable:
        raise Exception("Not extractable")
    return document


def find_url(string):
    # findall() has been used
    # with valid conditions for urls in string
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+" \
            r"\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex, string)
    return [x[0] for x in url]


def createDeviceInterpreter():
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    return device, interpreter


def parse_obj(objs, work, first_page):
    for obj in objs:
        if isinstance(obj, pdfminer.layout.LTTextBox):
            for o in obj._objs:
                if not isinstance(o, pdfminer.layout.LTTextLine):
                    continue
                origin_text = o.get_text()
                if first_page:
                    clean_text = origin_text[:origin_text.find(".")].strip()
                    lst_menu_line.append(clean_text)
                    continue

                text = origin_text.strip()
                if not text:
                    work.add_data("")
                last_fontname = ""
                for c in o._objs:
                    if isinstance(c, pdfminer.layout.LTChar) and c.fontname != last_fontname:
                        last_fontname = c.fontname
                        tpl_info = (c.fontname, round(c.size, 2))
                        if tpl_info in LST_MODEL_FONT:
                            text_type = "MODEL"
                            work.add_model(text)
                        elif tpl_info in LST_FIELD_FONT:
                            text_type = "FIELD"
                            work.add_field(text)
                        elif tpl_info in LST_HELP_FONT:
                            text_type = "HELP"
                            work.add_help(text)
                        elif tpl_info in LST_DATA_FONT:
                            text_type = "DATA"
                            work.add_data(text)
                        else:
                            text_type = "UNKNOWN"
                            logger.warning("Cannot find this type of text.")
                        if DEBUG_LOGGER:
                            logger.info(f"type '{text_type}' text '{text}' fontname '{c.fontname}' "
                                        f"size '{round(c.size, 2)}'")
        # if it's a container, recurse
        elif isinstance(obj, pdfminer.layout.LTFigure):
            parse_obj(obj._objs, work)
        else:
            pass


def transform_text_to_html(text):
    text_ready = text.replace("\n", "<br/>")
    lst_url = find_url(text_ready)
    for url in lst_url:
        html_url = f"<a href='{url}'>{url}</a>"
        text_ready = text_ready.replace(url, html_url)
    result = f"<p>{text_ready}<\p>"
    # Search url
    return result


def post_init_hook(cr, e):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        # Read PDF and create data from different font and size
        document = createPDFDoc()
        device, interpreter = createDeviceInterpreter()
        pages = PDFPage.create_pages(document)
        work = Working()
        count_skip = -1
        while True:
            try:
                page_result = next(pages)
                count_skip += 1
                if NB_SKIP_PAGE > count_skip:
                    continue
                interpreter.process_page(page_result)
                layout = device.get_result()

                parse_obj(layout._objs, work, count_skip == 0)
            except StopIteration:
                break
        lst_result = work.get_result()

        # Search all needed model and fields
        ir_model_ids = env["ir.model"].search([]).filtered(lambda field: "business.plan." in field.model)
        dct_result_model_ids = {}
        ir_model_field_ids = env["ir.model.fields"].search([("model_id.id", "in", ir_model_ids.ids)])
        # dct_model_title = {a.name: a for a in ir_model_ids}
        dct_field_title = {a.field_description: a for a in ir_model_field_ids}
        dct_mapped_help_field = {}

        # Hack from help, separate by " -- "
        for field_id in ir_model_field_ids:
            help_str = field_id.help
            if not help_str:
                continue
            if " -- " in help_str:
                help_str = help_str[:help_str.find(" -- ")].strip()
            dct_mapped_help_field[help_str] = field_id
        logger.info(f"Find {len(lst_result)} result to match.")

        # Find a match
        lst_match = []
        # Match result with model
        for result in lst_result:
            # TODO search by translation, fr and en in same time
            help_str = result.get("help")
            field_str = result.get("field")
            ir_help_fields_id = dct_mapped_help_field.get(help_str)
            ir_field_fields_id = dct_field_title.get(field_str)
            if ir_help_fields_id:
                lst_match.append((ir_help_fields_id, result))
            elif ir_field_fields_id:
                lst_match.append((ir_field_fields_id, result))
            else:
                logger.warning(f"Cannot find match for {result}")

        # Create a business plan
        next_id_business_plan = env["business.plan"].search([])
        next_id = 1
        if next_id_business_plan:
            next_id = next_id_business_plan[-1].id + 1
        business_plan_id = env["business.plan"].create({
            "name": f"Business Plan {next_id}",
        })

        logger.info(f"Find {len(lst_match)} match.")
        for match in lst_match:
            # Create sub section of business plan
            field_id = match[0]
            result_model_id = field_id.model_id
            result = match[1]
            model_id = dct_result_model_ids.get(result_model_id)
            data_txt = transform_text_to_html(result.get("data"))
            value = {
                field_id.name: data_txt
            }
            if not model_id:
                value["name"] = f"{result_model_id.name} {next_id}"
                value["business_plan_id"] = [(4, business_plan_id.id)]
                model_id = env[result_model_id.model].create(value)
                dct_result_model_ids[result_model_id] = model_id
            else:
                model_id.write(value)

        logger.debug("End of writing business plan.")
