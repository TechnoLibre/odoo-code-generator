import re

import psycopg2
from odoo import _, models, fields, api
from odoo.exceptions import ValidationError
from collections import defaultdict
from odoo.models import MAGIC_COLUMNS
import time
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

    # TODO obsolete, check code_generator_db
    module_name = fields.Char(string="Module", help="Module name")

    module_display_name = fields.Char(
        help="Module name to display", compute="_compute_model_name"
    )

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

    model_name = fields.Char(
        help="Will be name if no new_model_name, else new_model_name",
        compute="_compute_model_name",
    )

    has_update = fields.Boolean(
        string="Has new data",
        compute="_compute_has_update",
        store=True,
    )

    order_extract_data = fields.Integer(
        help=(
            "The order to extract data, to support many2one dependancy."
            " Piority to minimum value > 1, 0 is ignored."
        ),
    )

    has_many2one_dependency = fields.Boolean(
        help="At True when has a column type many2one."
    )

    has_looping_many2one_dependency = fields.Boolean(
        help="At True when has a column type many2one looping between."
    )

    # table_many2one_dependencies_ids = fields.Many2many(
    #     string="Depend table",
    #     relation="table_many2many_rel",
    #     comodel_name="code.generator.db.table",
    # )
    #
    # table_looping_many2one_dependencies_ids = fields.Many2many(
    #     string="Depend looping table",
    #     relation="table_looping_many2many_rel",
    #     comodel_name="code.generator.db.table",
    # )

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

    @api.depends("name", "new_model_name")
    def _compute_model_name(self):
        for obj in self:
            obj.model_name = (
                obj.new_model_name
                if obj.new_model_name
                else obj.name.replace("_", ".").lower()
            )
            obj.module_display_name = obj.model_name.replace(".", " ").title()

    @api.multi
    def toggle_nomenclator(self):
        for table in self:
            table.nomenclator = not table.nomenclator

    def update_table(
        self,
        table_name,
        new_model_name=None,
        new_description=None,
        new_rec_name=None,
        delete=False,
        nomenclator=False,
    ):
        table_id = self.search([("name", "=", table_name)])
        if not table_id:
            _logger.error(f"Cannot update table {table_name}.")
            return
        if delete:
            table_id.delete = True
            for column_id in table_id.o2m_columns:
                column_id.ignore_field = True
                column_id.delete = True
        if new_model_name:
            table_id.new_model_name = new_model_name
        if new_rec_name:
            table_id.new_rec_name = new_rec_name
        if new_description:
            table_id.new_description = new_description
        if nomenclator:
            table_id.nomenclator = True

    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            result = super(CodeGeneratorDbTable, self).create(value)
            lst_fields = self.get_table_fields(
                result.name, result.m2o_db, mark_temporary_field=True
            )
            for field in lst_fields:
                dct_field = field[2]
                column_value = {
                    "name": dct_field.get("name"),
                    "required": dct_field.get("required"),
                    "column_type": dct_field.get("ttype"),
                    "description": dct_field.get("field_description"),
                    "temporary_name_field": dct_field.get(
                        "temporary_name_field"
                    ),
                    "m2o_table": result.id,
                }
                if dct_field.get("relation"):
                    column_value["relation"] = dct_field.get("relation")
                if dct_field.get("relation_column"):
                    column_value["relation_column"] = dct_field.get(
                        "relation_column"
                    )
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

    @api.multi
    def generate_module(self, code_generator_id=None):
        """
        Function to generate a module
        :return:
        """
        lst_module = []
        dct_module = {}
        dct_module_table = defaultdict(list)
        for table in self:
            if table.delete:
                continue
            dct_module_table[table.module_name].append(table)

        for module_name, lst_table in dct_module_table.items():
            module_name_caps = module_name.capitalize()
            if not code_generator_id:
                final_module_name = "%s_module_%s" % (
                    lst_table[0].m2o_db.database,
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
            dct_module[module_name] = module
            lst_module.append(module)

        before_time = time.process_time()
        for module_name, lst_table in dct_module_table.items():
            table_ids = self.browse([a.id for a in lst_table])
            self._compute_table(
                dct_module.get(module_name), module_name, table_ids
            )
        after_time = time.process_time()
        _logger.info(
            "DEBUG time execution generate_module db_table"
            f" {after_time - before_time}"
        )
        return lst_module

    def _compute_table(self, cg_module_id, module_name, table_ids):
        # Not supported
        # Double link
        # Double data link

        # Update relation name
        self.update_relation_many2one(table_ids)

        # Reorder many2one dependency
        self.reorder_many2one_dependency(table_ids)

        # Create model and field, ready for creation
        lst_model_dct = [
            self.create_ir_model_field_value(cg_module_id, table)
            for table in table_ids.sorted(key=lambda a: a.order_extract_data)
        ]
        self.add_one2many(table_ids, lst_model_dct)

        _logger.info("Creating all ir.model...")

        models_created = self.env["ir.model"].create(lst_model_dct)

        # Migrate data
        table_nomenclator_ids = table_ids.filtered("nomenclator").sorted(
            key=lambda a: a.order_extract_data
        )
        for seq, table_id in enumerate(table_nomenclator_ids):
            _logger.info(f"Parse #{seq} - {table_id.name}")
            self.generate_data(table_id)

        # Delete field, after compute stuff
        _logger.info("Delete fields after compute with it.")
        before_time = time.process_time()

        for model_id in models_created:
            field_ids = model_id.field_id.filtered(
                lambda x: x.db_columns_ids.delete
            )
            field_ids.unlink()

        after_time = time.process_time()
        _logger.info(
            "DEBUG time execution _compute_table unlinks"
            f" {after_time - before_time}"
        )
        _logger.info(f"End of migration for module {module_name}")

    @staticmethod
    def create_ir_model_field_value(cg_module_id, table):
        """
        Create ir.model.field value from code.generator.db.table
        :param cg_module_id: code.generator module
        :param table: code.generator.db.table
        :return:
        """
        lst_field = []
        for field in table.o2m_columns:
            dct_field = {}
            if field.ignore_field:
                continue
            # TODO skip delete if no many2one refer on this value (nomenclator), if ask to be delete

            # Ignore create field name if no need anymore
            if (
                field.temporary_name_field
                and table.new_rec_name
                and table.new_rec_name != field.field_name
            ):
                # Delete this column, we don't need that!
                field.unlink()
                continue
            # New data for model
            dct_field["name"] = field.field_name
            dct_field["field_description"] = field.field_description
            dct_field["ttype"] = field.field_type
            dct_field["required"] = field.field_required
            dct_field["db_columns_ids"] = field.id
            if field.force_widget:
                dct_field["force_widget"] = field.force_widget

            if field.new_help:
                dct_field["help"] = field.new_help
            if field.new_default_value:
                dct_field["default"] = field.new_default_value
            if field.relation_table_id:
                # Don't share field.relation, it's the relation with the table_name
                dct_field["relation"] = field.relation_table_id.model_name

            lst_field.append((0, 0, dct_field))

        dct_model = {
            "name": table.module_display_name,
            "m2o_module": cg_module_id.id,
            "nomenclator": table.nomenclator,
            "field_id": lst_field,
            "model": table.model_name,
        }
        if table.new_rec_name:
            dct_model["rec_name"] = table.new_rec_name
        if table.new_description:
            dct_model["description"] = table.new_description
        return dct_model

    def generate_data(self, table_id):
        # Get columns to fetch data
        column_nomenclator_ids = table_id.o2m_columns.filtered(
            lambda a: not a.ignore_field
            and a.ir_model_field_id.ttype != "one2many"
            and not a.temporary_name_field
        )
        lst_column_name = column_nomenclator_ids.mapped("name")
        lst_field_name = column_nomenclator_ids.mapped("field_name")

        # Get column to compute data
        column_compute_ids = column_nomenclator_ids.filtered(
            lambda a: a.compute_data_function
        )
        column_binary_char_ids = column_nomenclator_ids.filtered(
            lambda a: a.path_binary
            and a.field_type == "binary"
            and a.column_type == "char"
        )
        column_many2one_ids = column_nomenclator_ids.filtered(
            lambda a: a.field_type == "many2one"
        )

        # Get query for SQL
        lst_query_replace = [
            (a.name, a.sql_select_modify)
            for a in column_nomenclator_ids.filtered(
                lambda col: col.sql_select_modify
            )
        ]

        # Fetch all data
        l_foreign_table_data = self.get_table_data(
            table_id.name,
            table_id.m2o_db,
            lst_column_name,
            lst_query_replace=lst_query_replace,
        )

        lst_data = list(
            map(
                self._conform_model_created_data(lst_field_name),
                l_foreign_table_data,
            )
        )

        # Compute data before create it
        if column_compute_ids or column_binary_char_ids or column_many2one_ids:
            for data in lst_data:
                # Compute data with a method call
                try:
                    for column_compute_id in column_compute_ids:
                        value = data.get(column_compute_id.field_name)
                        if value is None:
                            continue
                        new_value = eval(
                            column_compute_id.compute_data_function,
                            data.copy(),
                        )
                        if new_value != value:
                            data[column_compute_id.field_name] = new_value
                except Exception as e:
                    _logger.error(e)
                    _logger.error(
                        f"Last error for data {data} on table"
                        f" `{table_id.name}`"
                    )
                    _logger.error(
                        "Last computing:"
                        f" `{column_compute_id.compute_data_function}`"
                    )

                # Compute char path to transform in binary
                for column_binary_char_id in column_binary_char_ids:
                    if data:
                        value = data.get(column_binary_char_id.field_name)
                        if value:
                            # import path in binary
                            path_file = os.path.join(
                                column_binary_char_id.path_binary,
                                value,
                            )
                            if os.path.isfile(path_file):
                                new_data_binary = open(
                                    path_file,
                                    "rb",
                                ).read()
                                data[
                                    column_binary_char_id.field_name
                                ] = base64.b64encode(new_data_binary)
                            else:
                                _logger.error(
                                    f"Cannot add file path `{path_file}` for"
                                    " model"
                                    f" `{column_binary_char_id.ir_model_field_id.model}`"
                                    " and field"
                                    f" `{column_binary_char_id.field_name}`"
                                )
                for column_many2one_id in column_many2one_ids:
                    value = data.get(column_many2one_id.field_name)
                    # Update value with foreign key value
                    new_id = self.env[
                        column_many2one_id.relation_table_id.model_name
                    ].search(
                        [
                            (
                                column_many2one_id.relation_column_id.field_name,
                                "=",
                                value,
                            )
                        ]
                    )
                    if len(new_id) > 1:
                        raise ValueError(
                            "Model"
                            f" `{column_many2one_id.ir_model_field_id.model}`"
                            f" with field `{column_many2one_id.field_name}` is"
                            " required, but cannot find relation"
                            f" `{column_many2one_id.relation_table_id.model_name}`"
                            " relation column"
                            f" `{column_many2one_id.relation_column_id.field_name}`"
                            f" of id `{value}`. Cannot associate multiple"
                            " result, is your foreign configured correctly?"
                        )
                    if value and not new_id:
                        raise ValueError(
                            f"Cannot find value `{value}` for column"
                            f" `{column_many2one_id.relation_column_id.field_name}`"
                            f" in table `{table_id.name}`"
                        )
                    int_new_id = new_id.id
                    # TODO use real required
                    if int_new_id is False and (
                        column_many2one_id.field_required
                    ):
                        raise ValueError(
                            "Model"
                            f" `{column_many2one_id.ir_model_field_id.model}`"
                            f" with field `{column_many2one_id.field_name}` is"
                            " required, but cannot find relation"
                            f" `{column_many2one_id.relation_table_id.model_name}`"
                            " relation column"
                            f" `{column_many2one_id.relation_column_id.field_name}`"
                            f" of id `{value}`. Is it missing data?"
                        )
                    data[column_many2one_id.field_name] = int_new_id

        results = self.env[table_id.new_model_name].sudo().create(lst_data)

    def update_relation_many2one(self, table_ids):
        for table_id in table_ids:
            field_with_relation_ids = table_id.o2m_columns.filtered(
                lambda a: a.relation and a.relation_column
            )
            if field_with_relation_ids:
                for field in field_with_relation_ids:
                    # Find looping dependency
                    related_columns_ids = self.env[
                        "code.generator.db.column"
                    ].search(
                        [
                            ("name", "=", field.relation_column),
                            ("m2o_table.name", "=", field.relation),
                        ]
                    )
                    related_columns_id = related_columns_ids[0]

                    field.relation_table_id = related_columns_id.m2o_table.id
                    field.relation_column_id = related_columns_id.id

                    # Search in all columns of his table
                    for (
                        relate_column_id
                    ) in related_columns_id.m2o_table.o2m_columns:
                        looping_related_columns_ids = self.env[
                            "code.generator.db.column"
                        ].search(
                            [
                                (
                                    "name",
                                    "=",
                                    relate_column_id.relation_column,
                                ),
                                (
                                    "m2o_table.name",
                                    "=",
                                    relate_column_id.relation,
                                ),
                            ]
                        )
                        if (
                            looping_related_columns_ids.m2o_table
                            == field.m2o_table
                        ):
                            _logger.info(
                                "Find looping dependency from table"
                                f" `{field.m2o_table.name}` column"
                                f" `{field.name}` to table"
                                f" `{related_columns_id.m2o_table.name}`"
                                f" column `{related_columns_id.name}`."
                            )
                            table_id.has_looping_many2one_dependency = True
                            # field.m2o_table.table_looping_many2one_dependencies_ids = (4, related_columns_id.m2o_table.id)
                            break
                    else:
                        _logger.info(
                            "Find dependency of table"
                            f" `{field.m2o_table.name}` column"
                            f" `{field.name}` to table"
                            f" `{related_columns_id.m2o_table.name}`"
                            f" column `{related_columns_id.name}`."
                        )
                        # field.m2o_table.table_many2one_dependencies_ids = (4, related_columns_id.m2o_table.id)
                        table_id.has_many2one_dependency = True
            else:
                table_id.order_extract_data = 1

    @staticmethod
    def reorder_many2one_dependency(table_ids):
        table_to_reorder_ids = table_ids.filtered(
            lambda a: a.has_many2one_dependency
            and not a.has_looping_many2one_dependency
            and not a.order_extract_data
            and not a.delete
        )
        pos_order = 1
        max_loop = len(table_to_reorder_ids) + 1
        i = 0
        while table_to_reorder_ids and i < max_loop:
            i += 1
            pos_order += 1
            table_ordered_ids = table_ids.filtered(
                lambda a: a.order_extract_data
            )

            for table_to_reorder_id in table_to_reorder_ids:
                # TODO can we do many2many on same table? it's not working
                lst_table_id_depend = []
                column_ids = table_to_reorder_id.o2m_columns.filtered(
                    lambda a: a.relation_table_id
                )
                for column_id in column_ids:
                    lst_table_id_depend.append(column_id.relation_table_id.id)

                # Check if in list
                for table_id_int in set(lst_table_id_depend):
                    if table_id_int not in table_ordered_ids.ids:
                        break
                else:
                    table_to_reorder_id.order_extract_data = pos_order
                    # Force next order
                    break

            table_to_reorder_ids = table_ids.filtered(
                lambda a: a.has_many2one_dependency
                and not a.has_looping_many2one_dependency
                and not a.order_extract_data
                and not a.delete
            )

        if table_to_reorder_ids:
            _logger.error(
                "Stopping infinity loop, a bug occur when try to reorder"
                " model."
            )

    @staticmethod
    def add_one2many(table_ids, lst_model_dct):
        for table_id in table_ids:
            # table_id = table_ids.filtered(lambda a: a.model_name == dct_model.get("model"))
            column_ids = table_id.o2m_columns.filtered(
                lambda x: x.add_one2many
            )
            for column_id in column_ids:
                for dct_model in lst_model_dct:
                    if (
                        dct_model.get("model")
                        == column_id.relation_table_id.model_name
                    ):
                        # Validate no conflict name
                        lst_field_name = [
                            a[2].get("name") for a in dct_model.get("field_id")
                        ]

                        (
                            application_name,
                            model_name,
                        ) = table_id.model_name.split(".", maxsplit=1)
                        if model_name:
                            new_name_one2many = model_name.replace(".", "_")
                        else:
                            new_name_one2many = application_name
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
                                    f"{original_new_name_one2many}_{j}_ids"
                                )

                        description_name = new_name_one2many.replace(
                            "_", " "
                        ).title()

                        dct_one2many = {
                            "name": new_name_one2many,
                            # don't add ddb_field_name to detect it's added
                            # "ddb_field_name": new_name_one2many,
                            "field_description": description_name,
                            "help": f"{description_name} relation",
                            "ttype": "one2many",
                            "relation": table_id.model_name,
                            "relation_field": column_id.field_name,
                            # "comodel_name": update_info.model_name,
                            # "inverse_name": update_info.new_field_name,
                        }
                        tpl_field_one2many = (0, 0, dct_one2many)
                        dct_model.get("field_id").append(tpl_field_one2many)

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
                        table_name = is_m2o[0]
                        column_name = is_m2o[1]
                        # name_splitted = table_name.split("_", maxsplit=1)
                        #
                        # if len(name_splitted) > 1:
                        #     module_name, table_name = (
                        #         name_splitted[0],
                        #         name_splitted[1],
                        #     )
                        #
                        # else:
                        #     module_name, table_name = "comun", name_splitted[0]
                        t_odoo_field_4insert[2]["relation"] = table_name
                        t_odoo_field_4insert[2][
                            "relation_column"
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
        lst_column_name,
        limit=None,
        lst_query_replace=[],
    ):
        """
        Function to obtain a table data
        :param table_name:
        :param m2o_db:
        :param lst_column_name:
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
            if False in lst_column_name:
                raise ValueError(
                    f"One element is False in list of field {lst_column_name}"
                )
            query = f" SELECT {','.join(lst_column_name)} FROM {table_name} "
            if limit:
                query += f"LIMIT {limit} "

            for str_search, str_replace in lst_query_replace:
                query = query.replace(str_search, str_replace)

            cr.execute(query)

            return cr.fetchall()

        except psycopg2.OperationalError:
            raise ValidationError(TABLEDATAPROBLEM)

    def get_table_data2(
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
    def replace_in(text, regex="\d"):
        """
        Util function to replace some content in a text
        :param text:
        :param regex:
        :return:
        """
        return re.sub(regex, "", text)

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
    def _reorder_dependence_model2(dct_model):
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

    @staticmethod
    def get_new_model_name(table_ids, table_name, column_name):
        table_id = table_ids.filtered(lambda a: a.name == table_name)
        if not table_id:
            _logger.error(
                f"Cannot find table_name '{table_name}' to get new model name."
            )
        else:
            column_id = table_id.o2m_columns.filtered(
                lambda a: a.name == column_name
            )
            if not column_id:
                _logger.error(
                    f"Cannot find column '{column_name}' from table table_name"
                    f" '{table_name}' to get new model name."
                )
            else:
                return table_id.new_model_name, column_id.field_name
        return False, False
