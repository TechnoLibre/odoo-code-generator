import re

import psycopg2
from odoo import _, models, fields, api
from odoo.exceptions import ValidationError
from collections import defaultdict
from odoo.models import MAGIC_COLUMNS
import uuid
import base64
import os
import unidecode

import logging

_logger = logging.getLogger(__name__)

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]
TABLEFIELDPROBLEM = (
    "A connection problem occur trying to obtain a table fields."
)
TABLEDATAPROBLEM = "A connection problem occur trying to obtain a table data."


class CodeGeneratorDbTable(models.Model):
    _name = "code.generator.db.table"
    _description = "Code Generator Db Table"

    m2o_db = fields.Many2one(
        "code.generator.db", "Db", required=True, ondelete="cascade"
    )

    o2m_columns = fields.One2many(
        comodel_name="code.generator.db.column",
        inverse_name="m2o_table",
        string="Columns",
        help="The list of related columns.",
    )

    name = fields.Char(string="Table", help="Table", required=True)

    table_type = fields.Selection(
        string="Table type",
        help="Table type",
        required=True,
        selection=[("table", "Tabla"), ("view", "Vista")],
    )

    nomenclator = fields.Boolean(
        string="Nomenclator?",
        help="Set if you want this table to be used as nomenclator",
    )

    new_rec_name = fields.Char(string="New rec name")

    new_description = fields.Char(string="New description")

    new_model_name = fields.Char(string="New model name")

    has_update = fields.Boolean(
        string="Has new data",
        compute="_compute_has_update",
        store=True,
    )

    delete = fields.Boolean(
        string="Delete", help="When enable, remove the table in generation."
    )

    _sql_constraints = [
        (
            "unique_db_table",
            "unique (m2o_db, name)",
            "The Db and name combination must be unique.",
        )
    ]

    @api.depends(
        "new_rec_name",
        "new_description",
        "new_model_name",
    )
    def _compute_has_update(self):
        for obj in self:
            obj.has_update = bool(
                obj.new_rec_name or obj.new_description or obj.new_model_name
            )
            # if obj.new_rec_name:
            #     # Remove temporary name field if exist
            #     for column_id in self.o2m_columns.filtered(
            #         lambda column: column.temporary_name_field
            #     ):
            #         if column_id.name != obj.new_rec_name:
            #             column_id.delete = True

    @api.multi
    def toggle_nomenclator(self):
        for table in self:
            table.nomenclator = not table.nomenclator

    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            result = super(CodeGeneratorDbTable, self).create(value)
            lst_fields = self.get_table_fields(
                result.name, result.m2o_db, mark_temporary_field=True
            )
            for field in lst_fields:
                column_value = {
                    "name": field[2].get("name"),
                    "required": field[2].get("required"),
                    "column_type": field[2].get("ttype"),
                    "description": field[2].get("field_description"),
                    "temporary_name_field": field[2].get(
                        "temporary_name_field"
                    ),
                    "m2o_table": result.id,
                }
                self.env["code.generator.db.column"].create(column_value)

    @api.model
    def _conform_model_created_data(self, model_created_fields):
        """
        Function to conform the data for a created model
        :param model_created_fields:
        :return:
        """

        def _inner_conform(t_data):
            d_data = dict()
            pos = 0
            for model_created_field in model_created_fields:
                d_data[model_created_field] = t_data[pos]
                pos += 1
            return d_data

        return _inner_conform

    @api.model
    def _get_model_name(self, module_name, model):
        """
        Util function to obtain a model name
        :param module_name:
        :param model:
        :return:
        """

        return (
            "%s_%s" % (module_name, model) if module_name != "comun" else model
        )

    @api.multi
    def generate_module(self, code_generator_id=None):
        """
        Function to generate a module
        :return:
        """

        dct_model_id = {}
        dct_model_result_data = {}

        l_module_tables = defaultdict(list)

        for table in self:

            name_splitted = table.name.split("_", maxsplit=1)

            if len(name_splitted) > 1:
                module_name, table_name = name_splitted[0], name_splitted[1]

            else:
                module_name, table_name = "comun", name_splitted[0]

            t_tname_m2o_db_nom = (table_name, table.m2o_db, table.nomenclator)
            l_module_tables[module_name].append(t_tname_m2o_db_nom)

        for module_name in l_module_tables.keys():

            if not l_module_tables[module_name]:
                continue

            module_name_caps = module_name.capitalize()
            if not code_generator_id:
                final_module_name = "%s_module_%s" % (
                    l_module_tables[module_name][0][1].database,
                    module_name,
                )

                module = self.env["code.generator.module"].search(
                    [("name", "=", final_module_name)]
                )
                if not module:
                    module = self.env["code.generator.module"].create(
                        dict(
                            shortdesc="Module %s" % module_name_caps,
                            name=final_module_name,
                            application=True,
                        )
                    )
            else:
                module = code_generator_id

            lst_model_dct = list(
                map(
                    lambda t_info: dict(
                        name="Model %s belonging to Module %s"
                        % (t_info[0].capitalize(), module_name_caps),
                        model=self.replace_in(
                            t_info[0].lower().replace("_", ".")
                        ),
                        field_id=self.get_table_fields(
                            self._get_model_name(module_name, t_info[0]),
                            t_info[1],
                            rec_name=self.env[
                                "code.generator.db.update.migration.model"
                            ]
                            .search(
                                [
                                    ("model_name", "=", t_info[0]),
                                    ("code_generator_id", "=", module.id),
                                ]
                            )
                            .new_rec_name,
                        ),
                        m2o_module=module.id,
                        nomenclator=t_info[2],
                    ),
                    l_module_tables[module_name],
                )
            )

            dct_model_dct = {a.get("model"): a for a in lst_model_dct}

            # Delete ignored field before computation
            ignored_field_ids = self.env[
                "code.generator.db.update.migration.field"
            ].search(
                [
                    ("ignore_field", "=", True),
                    ("code_generator_id", "=", module.id),
                ]
            )

            for ignored_field_id in ignored_field_ids:
                dct_model_to_ignore = dct_model_dct.get(
                    ignored_field_id.model_name
                )
                if not dct_model_to_ignore:
                    _logger.warning(
                        f"Ignore the field {ignored_field_id.field_name} from"
                        f" model {ignored_field_id.model_name} into ignored"
                        " list."
                    )
                    continue
                # Search field
                i = -1
                for _, _, dct_field in dct_model_to_ignore.get("field_id"):
                    i += 1
                    if ignored_field_id.field_name == dct_field.get("name"):
                        dct_model_to_ignore.get("field_id").pop(i)
                        break
                else:
                    _logger.warning(
                        f"Cannot find field {ignored_field_id.field_name} from"
                        f" model {ignored_field_id.model_name}"
                    )

            # Update model
            for model_name, dct_model in dct_model_dct.items():
                modif_model_id = self.env[
                    "code.generator.db.update.migration.model"
                ].search(
                    [
                        ("model_name", "=", model_name),
                        ("code_generator_id", "=", module.id),
                    ]
                )
                if len(modif_model_id):
                    if len(modif_model_id) > 1:
                        _logger.warning(
                            "Cannot support multiple update for model"
                            f" {dct_model.get('model')}"
                        )
                    else:
                        if modif_model_id.new_rec_name:
                            dct_model["rec_name"] = modif_model_id.new_rec_name
                        if modif_model_id.new_description:
                            dct_model[
                                "description"
                            ] = modif_model_id.new_description
                            dct_model["name"] = modif_model_id.new_description

                modif_field_ids = self.env[
                    "code.generator.db.update.migration.field"
                ].search(
                    [
                        ("model_name", "=", model_name),
                        ("code_generator_id", "=", module.id),
                    ]
                )
                dct_field = {}
                for modif_id in modif_field_ids:
                    if modif_id.field_name:
                        if modif_id.field_name in dct_field.keys():
                            _logger.warning(
                                "Cannot support multiple update field for"
                                f" model {dct_model.get('model')} and field"
                                f" {modif_id.field_name}"
                            )
                            continue
                        # Validate update field name exist from database
                        for _, _, dct_model_field in dct_model.get("field_id"):
                            if modif_id.field_name == dct_model_field.get(
                                "name"
                            ):
                                is_exist = True
                                break
                        else:
                            is_exist = False
                            if not modif_id.ignore_field:
                                _logger.warning(
                                    "Field name doesn't exist from update"
                                    " field for model"
                                    f" {dct_model.get('model')} and field"
                                    f" {modif_id.field_name}"
                                )

                        if is_exist:
                            dct_field[modif_id.field_name] = modif_id
                    else:
                        _logger.warning(
                            "Missing field name in update field for model"
                            f" {dct_model.get('model')} and field"
                            f" {modif_id.field_name}"
                        )

                i = -1
                for _, _, dct_model_field in dct_model.get("field_id"):
                    i += 1
                    # Force origin_name to simplify code
                    dct_model_field["origin_name"] = dct_model_field["name"]
                    update_info = dct_field.get(dct_model_field.get("name"))
                    if not update_info:
                        continue

                    if update_info.new_field_name:
                        dct_model_field["name"] = update_info.new_field_name

                    # Keep empty value
                    if update_info.new_help is not False:
                        if "help" in dct_model_field:
                            dct_model_field["origin_help"] = dct_model_field[
                                "help"
                            ]
                        dct_model_field["help"] = update_info.new_help

                    if update_info.new_change_required:
                        if "required" in dct_model_field:
                            dct_model_field[
                                "origin_required"
                            ] = dct_model_field["required"]
                        dct_model_field["required"] = update_info.new_required

                    if update_info.new_type:
                        dct_model_field["origin_type"] = dct_model_field[
                            "ttype"
                        ]
                        dct_model_field["ttype"] = update_info.new_type

                    if update_info.path_binary:
                        dct_model_field[
                            "path_binary"
                        ] = update_info.path_binary

                    if update_info.force_widget:
                        dct_model_field[
                            "force_widget"
                        ] = update_info.force_widget

                    if update_info.add_one2many:
                        model_related_id = dct_model_dct[
                            dct_model_field.get("relation")
                        ]

                        new_name_one2many = update_info.model_name
                        # update_field_one2many = dct_field.get(
                        #     new_name_one2many
                        # )

                        # Create new field
                        # TODO Validate no duplicate in model_related_id, loop on field_id, check name if not already exist
                        # TODO move this after, in a new loop, to have new result of modification
                        lst_field_name = [
                            a[2].get("name")
                            for a in model_related_id.get("field_id")
                        ]
                        j = 0
                        original_new_name_one2many = new_name_one2many
                        while new_name_one2many in lst_field_name:
                            j += 1
                            if j == 1:
                                new_name_one2many = (
                                    f"{original_new_name_one2many}_ids"
                                )
                            else:
                                new_name_one2many = (
                                    f"{original_new_name_one2many}_ids_{j}"
                                )

                        dct_one2many = {
                            "name": new_name_one2many,
                            # don't add origin_name to detect it's added
                            # "origin_name": new_name_one2many,
                            "field_description": (
                                new_name_one2many.replace("_", " ").title()
                            ),
                            "help": f"{new_name_one2many.title()} relation",
                            "ttype": "one2many",
                            "relation": update_info.model_name,
                            "relation_field": update_info.new_field_name,
                            # "comodel_name": update_info.model_name,
                            # "inverse_name": update_info.new_field_name,
                        }
                        tpl_field_one2many = (0, 0, dct_one2many)

                        model_related_id.get("field_id").append(
                            tpl_field_one2many
                        )

                    # Keep empty value
                    if update_info.new_string is not False:
                        if "field_description" in dct_model_field:
                            dct_model_field["origin_string"] = dct_model_field[
                                "field_description"
                            ]
                        dct_model_field[
                            "field_description"
                        ] = update_info.new_string
            (
                lst_model_dct,
                dct_complete_looping_model,
            ) = self._reorder_dependence_model(dct_model_dct)
            _logger.info(f"Create models.")
            models_created = self.env["ir.model"].create(lst_model_dct)
            for model_id in models_created:
                dct_model_id[model_id.model] = model_id
            models_nomenclator = models_created.filtered("nomenclator")
            # Create data for nomenclator field
            for seq, model_created in enumerate(models_nomenclator):
                _logger.info(f"Parse #{seq} - {model_created.name}")

                lst_struct_field_to_ignore = dct_complete_looping_model.get(
                    model_created.model
                )
                if lst_struct_field_to_ignore:
                    lst_field_to_ignore = [
                        a.get("field_1") for a in lst_struct_field_to_ignore
                    ]
                    lst_ignored_field = lst_field_to_ignore
                else:
                    lst_ignored_field = []

                ignored_field_ids = self.env[
                    "code.generator.db.update.migration.field"
                ].search(
                    [
                        ("ignore_field", "=", True),
                        ("model_name", "=", model_created.model),
                        ("code_generator_id", "=", module.id),
                    ]
                )

                if ignored_field_ids:
                    for ignored_field_id in ignored_field_ids:
                        lst_ignored_field.append(ignored_field_id.field_name)

                model_created_fields = model_created.field_id.filtered(
                    lambda field: field.name
                    not in MAGIC_FIELDS + ["name"] + lst_ignored_field
                    and field.ttype != "one2many"
                )
                origin_mapped_model_created_fields = (
                    model_created_fields.mapped("origin_name")
                )
                mapped_model_created_fields = model_created_fields.mapped(
                    "name"
                )

                foreign_table = self.filtered(
                    lambda t: t.name
                    == self._get_model_name(
                        module_name, model_created.model.replace(".", "_")
                    )
                )

                # sql_select_modify
                sql_select_modify_id = self.env[
                    "code.generator.db.update.migration.field"
                ].search(
                    [
                        ("sql_select_modify", "!=", False),
                        ("model_name", "=", model_created.model),
                        ("code_generator_id", "=", module.id),
                    ]
                )
                lst_query_replace = [
                    (a.field_name, a.sql_select_modify)
                    for a in sql_select_modify_id
                ]

                l_foreign_table_data = self.get_table_data(
                    foreign_table.name,
                    foreign_table.m2o_db,
                    origin_mapped_model_created_fields,
                    lst_query_replace=lst_query_replace,
                )

                lst_data = list(
                    map(
                        self._conform_model_created_data(
                            mapped_model_created_fields
                        ),
                        l_foreign_table_data,
                    )
                )
                # Update
                for i, name in enumerate(mapped_model_created_fields):
                    field_id = model_created_fields[i]

                    # compute_data_function
                    compute_data_function_ids = self.env[
                        "code.generator.db.update.migration.field"
                    ].search(
                        [
                            ("compute_data_function", "!=", False),
                            ("model_name", "=", model_created.model),
                            ("code_generator_id", "=", module.id),
                        ]
                    )
                    if compute_data_function_ids:
                        for (
                            compute_data_function_id
                        ) in compute_data_function_ids:
                            field_name = (
                                compute_data_function_id.new_field_name
                                if compute_data_function_id.new_field_name
                                else compute_data_function_id.field_name
                            )
                            try:
                                for data in lst_data:
                                    value = data.get(field_name)
                                    new_value = eval(
                                        compute_data_function_id.compute_data_function,
                                        data.copy(),
                                    )
                                    if new_value != value:
                                        data[field_name] = new_value
                            except Exception as e:
                                _logger.error(e)

                    if (
                        field_id.path_binary
                        and field_id.ttype == "binary"
                        and field_id.origin_type == "char"
                    ):
                        for data in lst_data:
                            if data and data.get(field_id.name):
                                # import path in binary
                                path_file = os.path.join(
                                    field_id.path_binary,
                                    data.get(field_id.name),
                                )
                                if os.path.isfile(path_file):
                                    new_data_binary = open(
                                        path_file,
                                        "rb",
                                    ).read()
                                    data[field_id.name] = base64.b64encode(
                                        new_data_binary
                                    )
                                else:
                                    _logger.error(
                                        f"Cannot add file path `{path_file}`"
                                        f" for model `{name}` and field"
                                        f" `{field_id.name}`"
                                    )

                    if field_id.ttype == "many2one":
                        relation_model = field_id.relation
                        relation_field = field_id.foreign_key_field_name
                        new_relation_field = self.search_new_field_name(
                            module, relation_model, relation_field
                        )
                        for data in lst_data:
                            # Update many2one
                            value = data[name]
                            if value is not None:
                                result_new_id = self.env[
                                    relation_model
                                ].search([(new_relation_field, "=", value)])
                                if len(result_new_id) > 1:
                                    raise ValueError(
                                        f"Model `{field_id.model}` with"
                                        f" field `{field_id.name}` is"
                                        " required, but cannot find"
                                        f" relation `{new_relation_field}` of"
                                        f" id `{value}`. Cannot associate"
                                        " multiple result, is your"
                                        " foreign configured correctly?"
                                    )
                                new_id = result_new_id.id
                                if new_id is False and field_id.required:
                                    raise ValueError(
                                        f"Model `{field_id.model}` with"
                                        f" field `{field_id.name}` is"
                                        " required, but cannot find"
                                        f" relation `{new_relation_field}` of"
                                        f" id `{value}`. Is it missing"
                                        " data?"
                                    )
                                data[name] = new_id
                results = self.env[model_created.model].sudo().create(lst_data)
                dct_model_result_data[model_created.model] = results

                # Generate xml_id for all nonmenclature
                for result in results:
                    second = False
                    if result._rec_name:
                        second = getattr(result, result._rec_name)
                    if second is False:
                        second = uuid.uuid1().int
                    # unidecode remove all accent
                    new_id = unidecode.unidecode(
                        f"{model_created.model.replace('.', '_')}_{second}"
                        .replace("-", "_")
                        .replace(" ", "_")
                        .replace(".", "_")
                        .replace("'", "_")
                        .replace("`", "_")
                        .replace("^", "_")
                        .lower()
                    )
                    new_id = new_id.strip("_")

                    while new_id.count("__"):
                        new_id = new_id.replace("__", "_")

                    # validate duplicate
                    origin_new_id = new_id
                    ir_model_data_id = self.env["ir.model.data"].search(
                        [("name", "=", new_id)]
                    )
                    i = 0
                    while ir_model_data_id:
                        i += 1
                        origin_new_id = f"{new_id}{i}"
                        ir_model_data_id = self.env["ir.model.data"].search(
                            [("name", "=", origin_new_id)]
                        )

                    self.env["ir.model.data"].create(
                        {
                            "name": origin_new_id,
                            "model": model_created.model,
                            "module": module.name,
                            "res_id": result.id,
                            "noupdate": True,
                        }
                    )

            # Create missing field to fix looping dependencies
            i = -1
            for (
                model_name,
                lst_dct_looping_value,
            ) in dct_complete_looping_model.items():
                i += 1
                _logger.info(
                    f"{i} - Adding missing field for model {model_name}."
                )
                # Adding field
                lst_added_field_name = []
                lst_added_field_origin_name = []
                for dct_looping_value in lst_dct_looping_value:
                    # TODO mettre la variable de la DB dans dct_looping_value au lieu de field_name
                    # modif_model_id = self.env[
                    #     "code.generator.db.update.migration.field"
                    # ].search(
                    #     [
                    #         (
                    #             "model_name",
                    #             "=",
                    #             dct_looping_value.get("model_1"),
                    #         ),
                    #         (
                    #             "new_field_name",
                    #             "=",
                    #             dct_looping_value.get("field_1"),
                    #         ),
                    #         ("code_generator_id", "=", module.id),
                    #     ]
                    # )

                    value_field = dct_looping_value.get("field_info_1").copy()
                    # TODO implement here modification
                    lst_added_field_name.append(value_field.get("name"))
                    lst_added_field_origin_name.append(
                        value_field.get("origin_name")
                    )
                    value_field["model_id"] = dct_model_id.get(
                        dct_looping_value.get("model_1")
                    ).id
                    self.env["ir.model.fields"].create(value_field)

                    # if modif_model_id and modif_model_id.add_one2many:
                    #     # TODO update this field
                    #     # TODO add one2many
                    #
                    #     # Find model
                    #     model_related_id = self.env["ir.model"].search([("model", "=", dct_looping_value.get("model_2"))])
                    #
                    #     # TODO validate name not exist
                    #     dct_one2many = {
                    #         "name": dct_looping_value.get("field_2")
                    #         + "_reverse",
                    #         "model_id": model_related_id.id,
                    #         # don't add origin_name to detect it's added
                    #         # "origin_name": new_name_one2many,
                    #         "field_description": (
                    #             f"{dct_looping_value.get('field_2').title()} relation"
                    #         ),
                    #         "ttype": "one2many",
                    #         "relation": dct_looping_value.get("model_1"),
                    #         "relation_field": dct_looping_value.get("field_1"),
                    #         # "comodel_name": update_info.model_name,
                    #         # "inverse_name": update_info.new_field_name,
                    #         # TODO add model
                    #     }
                    #     self.env["ir.model.fields"].create(dct_one2many)

                ir_model_info = self.env["ir.model"].search(
                    [("model", "=", model_name)]
                )
                if not ir_model_info.nomenclator:
                    continue

                # Reupdate after new fields
                lst_data_id = [
                    a.id for a in dct_model_result_data.get(model_name, [])
                ]
                new_list_model_result_data = self.env[model_name].browse(
                    lst_data_id
                )
                # Search missing data from databases
                foreign_table = self.filtered(
                    lambda t: t.name
                    == self._get_model_name(
                        module_name,
                        model_name,
                    )
                )

                # sql_select_modify
                sql_select_modify_id = self.env[
                    "code.generator.db.update.migration.field"
                ].search(
                    [
                        ("sql_select_modify", "!=", False),
                        ("model_name", "=", model_created.model),
                        ("code_generator_id", "=", module.id),
                    ]
                )
                lst_query_replace = [
                    (a.field_name, a.sql_select_modify)
                    for a in sql_select_modify_id
                ]

                l_foreign_table_data = self.get_table_data(
                    foreign_table.name,
                    foreign_table.m2o_db,
                    lst_added_field_origin_name,
                    lst_query_replace=lst_query_replace,
                )

                lst_data = list(
                    map(
                        self._conform_model_created_data(lst_added_field_name),
                        l_foreign_table_data,
                    )
                )
                if len(lst_data) != len(new_list_model_result_data):
                    _logger.error(
                        f"Cannot update data for model `{model_name}` and new"
                        f" fields {lst_added_field_name}, length is not the"
                        f" same. Expect size {len(lst_data)}, actual size"
                        f" {len(new_list_model_result_data)}"
                    )
                else:
                    dct_cache_id = {}

                    # Update data for missing field
                    for seq_data, result in enumerate(
                        new_list_model_result_data
                    ):
                        data_value = lst_data[seq_data]

                        # Transform data
                        cache_value = dct_cache_id.get(str(data_value))
                        if cache_value is None:
                            # Search field_id
                            for (
                                data_value_key,
                                data_value_value,
                            ) in data_value.items():
                                for field_id in ir_model_info.field_id:
                                    if not (
                                        field_id.name == data_value_key
                                        and field_id.ttype == "many2one"
                                    ):
                                        continue
                                    # TODO duplicated code
                                    relation_model = field_id.relation
                                    relation_field = (
                                        field_id.foreign_key_field_name
                                    )
                                    new_relation_field = (
                                        self.search_new_field_name(
                                            module,
                                            relation_model,
                                            relation_field,
                                        )
                                    )
                                    result_new_id = self.env[
                                        relation_model
                                    ].search(
                                        [
                                            (
                                                new_relation_field,
                                                "=",
                                                data_value_value,
                                            )
                                        ]
                                    )
                                    if len(result_new_id) > 1:
                                        raise ValueError(
                                            f"Model `{field_id.model}` with"
                                            f" field `{field_id.name}` is"
                                            " required, but cannot find"
                                            f" relation `{new_relation_field}`"
                                            f" of id `{value}`. Cannot"
                                            " associate multiple result, is"
                                            " your foreign configured"
                                            " correctly?"
                                        )
                                    new_id = result_new_id.id
                                    if new_id is False and field_id.required:
                                        raise ValueError(
                                            f"Model `{field_id.model}` with"
                                            f" field `{field_id.name}` is"
                                            " required, but cannot find"
                                            f" relation `{new_relation_field}`"
                                            f" of id `{value}`. Is it missing"
                                            " data?"
                                        )
                                    data_value[data_value_key] = new_id

                            dct_cache_id[str(data_value)] = data_value
                            new_data_value = data_value
                        else:
                            new_data_value = cache_value

                        status = result.write(new_data_value)
                        if not status:
                            _logger.error(
                                f"Error write value for model {model_name} and"
                                f" new fields {lst_added_field_name}."
                            )
            # Remove field at the end, because some field is needed by other field to do relation
            deleted_field_ids = self.env[
                "code.generator.db.update.migration.field"
            ].search(
                [("delete", "=", True), ("code_generator_id", "=", module.id)]
            )
            for ignored_field_id in deleted_field_ids:
                field_to_remove_id = self.env["ir.model.fields"].search(
                    [
                        ("model", "=", ignored_field_id.model_name),
                        ("name", "=", ignored_field_id.field_name),
                    ]
                )
                if field_to_remove_id:
                    if len(field_to_remove_id) > 1:
                        _logger.warning(
                            "Field multiple field when delete it in model"
                            f" `{ignored_field_id.model_name}` and field"
                            f" `{ignored_field_id.field_name}`"
                        )
                    field_to_remove_id.unlink()
        return module

    def get_db_query_4_columns(self, m2o_db, table_name, schema, database):
        """
        Function to obtain the SELECT query for a table columns
        :param m2o_db:
        :param table_name:
        :param schema:
        :param database:
        :return:
        """

        sgdb = m2o_db.m2o_dbtype.name

        query = """ SELECT * FROM {t_from} WHERE """.format(
            t_from="information_schema.columns"
        )

        if sgdb != "SQLServer":
            query += (
                " table_schema ="
                f" '{schema if sgdb == 'PostgreSQL' else database}' AND "
            )

        return query + f" table_name = '{table_name}' "

    @staticmethod
    def get_q_4constraints(table_name, column_name, fkey=False, sgdb=None):
        """
        Function to obtain the SELECT query for a table constraints
        :param table_name:
        :param column_name:
        :param fkey:
        :param sgdb:
        :return:
        """

        if fkey:
            if sgdb != "MySQL":
                return f""" SELECT ccu.table_name, ccu.COLUMN_NAME FROM {'information_schema.table_constraints'} AS tc
                JOIN {'information_schema.key_column_usage'} AS kcu ON tc.constraint_name = kcu.constraint_name
                JOIN {'information_schema.constraint_column_usage'} AS ccu ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{table_name}'
                AND kcu.column_name = '{column_name}' """

            else:
                return f""" SELECT kcu.referenced_table_name, kcu.REFERENCED_COLUMN_NAME FROM {'information_schema.table_constraints'} AS tc
                JOIN {'information_schema.key_column_usage'} AS kcu ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{table_name}'
                AND kcu.column_name = '{column_name}' """

        else:
            return f""" SELECT * FROM {'information_schema.table_constraints'} AS tc
            JOIN {'information_schema.key_column_usage'} AS kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = '{table_name}'
            AND kcu.column_name = '{column_name}' """

    @staticmethod
    def get_odoo_field_tuple_4insert(
        name, field_description, ttype, required=False, dct_new_info={}
    ):
        """
        Function to obtain the tuple for a insert operation (0, 0, {...})
        :param name:
        :param field_description:
        :param ttype:
        :param required:
        :param dct_new_info:
        :return:
        """

        dct_value = {
            **dict(
                name=unidecode.unidecode(name.lower()),
                field_description=field_description.replace("_", " "),
                ttype=ttype,
                required=required,
            ),
            **dct_new_info,
        }

        return 0, 0, dct_value

    @staticmethod
    def get_odoo_ttype(data_type):
        """
        Util function to adapt some filed types for Odoo
        :param data_type:
        :return:
        """

        odoo_ttype = data_type
        if (
            data_type == "smallint"
            or data_type == "int"
            or data_type == "bit"
            or data_type == "tinyint"
        ):
            odoo_ttype = "integer"

        elif data_type == "money":
            odoo_ttype = "monetary"

        elif data_type == "decimal" or data_type == "double":
            odoo_ttype = "float"

        elif data_type == "character varying" or data_type == "varchar":
            odoo_ttype = "char"

        elif (
            data_type == "timestamp with time zone"
            or data_type == "timestamp"
            or data_type == "time"
        ):
            odoo_ttype = "datetime"

        elif data_type == "date":
            odoo_ttype = "date"

        return odoo_ttype

    def get_table_fields(
        self,
        origin_table_name,
        m2o_db,
        rec_name="name",
        mark_temporary_field=False,
    ):
        """
        Function to obtain a table fields
        :param origin_table_name:
        :param m2o_db:
        :param rec_name:
        :param mark_temporary_field:
        :return:
        """

        try:
            sgdb = m2o_db.m2o_dbtype.name
            database = m2o_db.database
            cr = self.env["code.generator.db"].get_db_cr(
                sgdb=sgdb,
                database=database,
                host=m2o_db.host,
                port=m2o_db.port,
                user=m2o_db.user,
                password=m2o_db.password,
            )
            str_query_4_columns = self.get_db_query_4_columns(
                m2o_db, origin_table_name, m2o_db.schema, database
            )
            cr.execute(str_query_4_columns)

            l_fields = []
            having_column_name = False
            lst_column_info = cr.fetchall()
            for column_info in lst_column_info:

                column_name = column_info[3]

                if column_name == "name":
                    having_column_name = True

                # elif len(column_name) > 63:
                #     slice_column_name = column_name[:63]
                #     _logger.warning(
                #         f"Slice column {column_name} to"
                #         f" {slice_column_name} because length is upper than 63."
                #     )
                #     column_name = slice_column_name

                str_query_4_constraints = self.get_q_4constraints(
                    origin_table_name, column_name
                )
                cr.execute(str_query_4_constraints)
                if (
                    m2o_db.accept_primary_key or not cr.fetchone()
                ):  # if it is not a primary key

                    str_query_4_constraints_fkey = self.get_q_4constraints(
                        origin_table_name, column_name, fkey=True, sgdb=sgdb
                    )
                    cr.execute(str_query_4_constraints_fkey)
                    is_m2o = cr.fetchone()

                    t_odoo_field_4insert = self.get_odoo_field_tuple_4insert(
                        column_name,
                        column_name.capitalize(),
                        "many2one"
                        if is_m2o
                        else self.get_odoo_ttype(column_info[7]),
                        column_info[6] == "NO",
                    )

                    if is_m2o:  # It is a foreign key?
                        model_name = is_m2o[0]
                        column_name = is_m2o[1]
                        name_splitted = model_name.split("_", maxsplit=1)

                        if len(name_splitted) > 1:
                            module_name, table_name = (
                                name_splitted[0],
                                name_splitted[1],
                            )

                        else:
                            module_name, table_name = "comun", name_splitted[0]
                        t_odoo_field_4insert[2][
                            "relation"
                        ] = f"{table_name.replace('_', '.')}"
                        t_odoo_field_4insert[2][
                            "foreign_key_field_name"
                        ] = column_name.lower()

                    l_fields.append(t_odoo_field_4insert)

            if not having_column_name and (
                rec_name == "name" or rec_name is False
            ):
                # Force create field name if rec_name is "name" and missing name field
                dct_temp_info = {}
                if mark_temporary_field:
                    dct_temp_info["temporary_name_field"] = True
                l_fields.append(
                    self.get_odoo_field_tuple_4insert(
                        "name",
                        "Name",
                        "char",
                        dct_new_info=dct_temp_info,
                    )
                )

            return l_fields

        except psycopg2.OperationalError:
            raise ValidationError(TABLEFIELDPROBLEM)

    def get_table_data(
        self,
        table_name,
        m2o_db,
        model_created_fields,
        limit=None,
        lst_query_replace=[],
    ):
        """
        Function to obtain a table data
        :param table_name:
        :param m2o_db:
        :param model_created_fields:
        :param limit: int max to get data
        :param lst_query_replace: list of query to replace, tuple [0] string to replace, [1] new string
        :return:
        """

        if not table_name:
            raise ValueError(f"table name is empty.")

        port = self.env["code.generator.db"].get_port(m2o_db.port)
        try:
            cr = self.env["code.generator.db"].get_db_cr(
                sgdb=m2o_db.m2o_dbtype.name,
                database=m2o_db.database,
                host=m2o_db.host,
                port=port,
                user=m2o_db.user,
                password=m2o_db.password,
            )
            if False in model_created_fields:
                raise ValueError(
                    "One element is False in list of field"
                    f" {model_created_fields}"
                )
            query = (
                f" SELECT {','.join(model_created_fields)} FROM {table_name} "
            )
            if limit:
                query += f"LIMIT {limit} "

            for str_search, str_replace in lst_query_replace:
                query = query.replace(str_search, str_replace)

            cr.execute(query)

            return cr.fetchall()

        except psycopg2.OperationalError:
            raise ValidationError(TABLEDATAPROBLEM)

    @staticmethod
    def replace_in(string, regex="\d"):
        """
        Util function to replace some content in a string
        :param string:
        :param regex:
        :return:
        """
        return re.sub(regex, "", string)

    def search_new_field_name(self, module_id, model_name, old_field_name):
        update_ids = self.env[
            "code.generator.db.update.migration.field"
        ].search(
            [
                ("model_name", "=", model_name),
                ("field_name", "=", old_field_name),
                ("code_generator_id", "=", module_id.id),
            ]
        )
        if not update_ids:
            return old_field_name
        if len(update_ids) > 1:
            _logger.warning(
                "Multiple update database information for model"
                f" `{model_name}` field `{old_field_name}`"
            )
            update_ids = update_ids[0]
        result = update_ids.new_field_name
        if result is False:
            return old_field_name
        return result

    @staticmethod
    def _reorder_dependence_model(dct_model):
        lst_model_ordered = []
        dct_model_hold = {}
        dct_looping_model_unique = defaultdict(dict)
        dct_looping_model = defaultdict(dict)
        dct_complete_looping_model = defaultdict(list)
        dct_model_depend = defaultdict(dict)  # key field name, value is model
        for model_name, model_id in dct_model.items():
            contain_m2o = False
            for tpl_field_id in model_id.get("field_id"):
                field_id = tpl_field_id[2]
                if (
                    field_id.get("ttype") == "many2one"
                    and field_id.get("relation") in dct_model.keys()
                ):
                    contain_m2o = True
                    dct_model_depend[model_id.get("model")][
                        field_id.get("name")
                    ] = dct_model[field_id.get("relation")]

            if not contain_m2o:
                lst_model_ordered.append(model_id)
            else:
                dct_model_hold[model_id.get("model")] = model_id

        # Detect looping dependencies
        # Need a copy, the execution change dct_model_depend (for no reason...)
        # Loop on model
        for model_name, dct_model_id in dct_model_depend.copy().items():
            # Loop on fields
            for model_id in dct_model_id.values():
                model_id_name = model_id.get("model")
                lst_depend_child = dct_model_depend[model_id_name].items()
                for field_name, child_depend in lst_depend_child:
                    if child_depend.get("model") != model_name:
                        continue
                    already_add_depend = dct_looping_model.get(model_id_name)
                    # TODO problem with double iteration, second iteration override it
                    dct_looping_model[model_name][field_name] = model_id
                    if not already_add_depend:
                        dct_looping_model_unique[model_name][
                            field_name
                        ] = model_id
                        continue
                    # Find information about model 1
                    for (
                        already_field_name,
                        already_model,
                    ) in already_add_depend.items():
                        if already_model == child_depend:
                            break

                    for _, _, field_info in dct_model_hold.get(
                        model_id_name
                    ).get("field_id"):
                        if field_info.get("name") == field_name:
                            field_info_1 = field_info
                            break
                    else:
                        raise ValueError(
                            "Cannot find field"
                            f" {field_name} in model {model_id_name}"
                        )

                    for field_info in already_model.get("field_id"):
                        if field_info[2].get("name") == already_field_name:
                            field_info_2 = field_info[2]
                            break
                    else:
                        raise ValueError(
                            "Cannot find field"
                            f" {already_field_name} in model"
                            f" {model_name}"
                        )
                    dct_value = {
                        "model_1": model_id_name,
                        "field_1": field_name,
                        "field_info_1": field_info_1,
                        "dct_model_1": model_id,
                        "model_2": model_name,
                        "field_2": already_field_name,
                        "field_info_2": field_info_2,
                        "dct_model_2": child_depend,
                    }

                    if (
                        dct_value
                        not in dct_complete_looping_model[model_id_name]
                    ):
                        dct_complete_looping_model[model_id_name].append(
                            dct_value
                        )

        # Remove dependency to remove looping
        for model_name, dct_model_id in dct_looping_model.items():
            for model_id in dct_model_id.values():
                for (
                    field_name,
                    dct_model_id,
                ) in dct_model_depend[model_name].items():
                    if dct_model_id == model_id:
                        del dct_model_depend[model_name][field_name]
                        if not dct_model_depend[model_name]:
                            del dct_model_depend[model_name]
                        break

        i = 0
        max_i = len(dct_model_hold) + 1
        while dct_model_hold and i < max_i:
            i += 1
            for model_name, model_id in dct_model_hold.items():
                lst_depend = dct_model_depend.get(model_name)
                if not lst_depend:
                    lst_model_ordered.append(model_id)
                    del dct_model_depend[model_name]
                    del dct_model_hold[model_name]
                    break
                # check if all depend is already in list
                is_all_in = True
                for depend_id in lst_depend.values():
                    if depend_id not in lst_model_ordered:
                        is_all_in = False
                        break

                if is_all_in:
                    lst_model_ordered.append(model_id)
                    del dct_model_hold[model_name]
                    break

        if dct_model_hold:
            _logger.error(
                f"Cannot reorder all table dependency: {dct_model_hold}"
            )
        # Remove field from model
        for (
            model_name,
            lst_field_looping,
        ) in dct_complete_looping_model.items():
            for dct_field_looping in lst_field_looping:
                str_field_name = dct_field_looping.get("field_1")
                for model_ordered in lst_model_ordered:
                    is_find = False
                    no_field = -1
                    for tpl_field in model_ordered.get("field_id"):
                        no_field += 1
                        if tpl_field[2].get("name") == str_field_name:
                            model_ordered.get("field_id").pop(no_field)
                            is_find = True
                            break
                    if is_find:
                        break
        return lst_model_ordered, dct_complete_looping_model
