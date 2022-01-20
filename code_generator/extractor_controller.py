import glob
import logging
import os
from collections import defaultdict
from xml.dom import Node, minidom

from pyjsparser import parse

_logger = logging.getLogger(__name__)


class ExtractorController:
    def __init__(self, module, model_model, model_extractor):
        self._module = module
        self._model_extractor = model_extractor
        self.env = module.env
        model_name = model_model.replace(".", "_")
        self.code_generator_id = None
        self.model_id = self.env["ir.model"].search(
            [("model", "=", model_model)]
        )
        self.dct_model = defaultdict(dict)
        self.dct_field = defaultdict(dict)
        self.module_attr = defaultdict(dict)
        self.var_model_name = f"model_{model_name}"
        self.var_model = model_model
        self._parse_controller()

    def _parse_controller(self):
        module = self._module
        lst_model_name = module.template_model_name.split(";")

        snippet_xml_ids = [
            a
            for a in self.env["ir.ui.view"].search(
                [
                    (
                        "arch_fs",
                        "=",
                        f"{module.template_module_name}/views/snippets.xml",
                    ),
                    ("inherit_id.key", "=", "website.snippets"),
                ]
            )
        ]
        if snippet_xml_ids:
            if len(snippet_xml_ids) == 1:
                item_found_snippet_type = None
                my_xml = minidom.parseString(snippet_xml_ids[0].arch_db)
                lst_xpath = my_xml.getElementsByTagName("xpath")
                if lst_xpath:
                    for xml_dom in lst_xpath:
                        for attr, str_item in xml_dom.attributes.items():
                            if attr == "expr":
                                if "snippet_structure" in str_item:
                                    module.template_generate_website_snippet_type = (
                                        "structure"
                                    )
                                    item_found_snippet_type = xml_dom
                                elif "snippet_effect" in str_item:
                                    module.template_generate_website_snippet_type = (
                                        "effect"
                                    )
                                    item_found_snippet_type = xml_dom
                                elif "snippet_feature" in str_item:
                                    module.template_generate_website_snippet_type = (
                                        "feature"
                                    )
                                    item_found_snippet_type = xml_dom
                                elif "snippet_content" in str_item:
                                    module.template_generate_website_snippet_type = (
                                        "content"
                                    )
                                    item_found_snippet_type = xml_dom
                if item_found_snippet_type:
                    lst_field_name = [
                        a.name for a in self._model_extractor.model_id.field_id
                    ]
                    if not module.template_module_path_generated_extension:
                        return
                    relative_path_generated_module = module.template_module_path_generated_extension.replace(
                        "'", ""
                    ).replace(
                        ", ", "/"
                    )
                    path_generated_module = os.path.normpath(
                        os.path.join(
                            module.path_sync_code,
                            relative_path_generated_module,
                            module.template_module_name,
                            "static",
                            "src",
                            "js",
                            f"website.{module.template_module_name}.animation.js",
                        )
                    )
                    lst_js_file = glob.glob(path_generated_module)
                    is_in_list = False
                    # TODO optimize, this is call for each model, but it's a unique result
                    for js_file in lst_js_file:
                        with open(js_file, "r") as f:
                            js_code = f.read()
                            token_js = parse(js_code)
                            lst_field_founded_name = []
                            self.recursive_search_field_text(
                                token_js, lst_field_founded_name
                            )
                            # validate all the field exist in this model. If true, we find it! Suppose by default yes
                            is_in_list = bool(
                                lst_field_founded_name and lst_field_name
                            )
                            for field_name in lst_field_founded_name:
                                if field_name not in lst_field_name:
                                    is_in_list = False
                                    break
                    if is_in_list:
                        if (
                            module.template_generate_website_snippet_generic_model
                        ):
                            _logger.warning(
                                "Not supported multiple model in portal"
                                " controller about snippet."
                            )
                        else:
                            module.template_generate_website_snippet_generic_model = (
                                self.var_model
                            )
            else:
                _logger.warning("Not support extraction multiple snippet.")

    def recursive_search_field_text(self, token, lst_field_name):
        if not token:
            return
        if type(token) is dict:
            if token.get("type") == "Program":
                return self.recursive_search_field_text(
                    token.get("body"), lst_field_name
                )
            elif token.get("type") == "ExpressionStatement":
                return self.recursive_search_field_text(
                    token.get("expression"), lst_field_name
                )
            elif token.get("type") == "CallExpression":
                self.recursive_search_field_text(
                    token.get("arguments"), lst_field_name
                )
                return self.recursive_search_field_text(
                    token.get("callee"), lst_field_name
                )
            elif token.get("type") == "FunctionExpression":
                return self.recursive_search_field_text(
                    token.get("body"), lst_field_name
                )
            elif token.get("type") == "BlockStatement":
                return self.recursive_search_field_text(
                    token.get("body"), lst_field_name
                )
            elif token.get("type") == "AssignmentExpression":
                self.recursive_search_field_text(
                    token.get("right"), lst_field_name
                )
                self.recursive_search_field_text(
                    token.get("left"), lst_field_name
                )
                return
            elif token.get("type") == "ObjectExpression":
                return self.recursive_search_field_text(
                    token.get("properties"), lst_field_name
                )
            elif token.get("type") == "Literal":
                if token.get("value").startswith(".") and token.get(
                    "value"
                ).endswith("_value"):
                    # Detect self.$(".demo_binary_image_value").text(data["demo_binary_image"]);
                    field_name = token.get("value")[1:-6]
                    lst_field_name.append(field_name)
                return
            elif token.get("type") == "Property":
                return self.recursive_search_field_text(
                    token.get("value"), lst_field_name
                )
            elif token.get("type") == "VariableDeclaration":
                return self.recursive_search_field_text(
                    token.get("declarations"), lst_field_name
                )
            elif token.get("type") == "MemberExpression":
                self.recursive_search_field_text(
                    token.get("property"), lst_field_name
                )
                return self.recursive_search_field_text(
                    token.get("object"), lst_field_name
                )
            elif token.get("type") == "VariableDeclarator":
                return self.recursive_search_field_text(
                    token.get("init"), lst_field_name
                )
            elif token.get("type") == "IfStatement":
                return self.recursive_search_field_text(
                    token.get("consequent"), lst_field_name
                )
            elif token.get("type") == "EmptyStatement":
                return
            elif token.get("type") == "ThisExpression":
                return
            elif token.get("type") == "ReturnStatement":
                return
            elif token.get("type") == "Identifier":
                return
            else:
                # Not supported token type
                return
        elif type(token) is list:
            for token_item in token:
                self.recursive_search_field_text(token_item, lst_field_name)
            return
