# -*- coding: utf-8 -*-

import re

import psycopg2
from odoo import _, models, fields, api
from odoo.exceptions import ValidationError
from collections import defaultdict
from odoo.models import MAGIC_COLUMNS
import uuid

import logging

_logger = logging.getLogger(__name__)

MAGIC_FIELDS = MAGIC_COLUMNS + [
    "display_name",
    "__last_update",
    "access_url",
    "access_token",
    "access_warning",
]
INVALIDPORT = "The specify port is invalid."
PSYCOPGUNINSTALLED = "Verify that the psycopg package is installed."
PYMYSQLUNINSTALLED = "Verify that the pymysql package is installed."
PYMSSQLUNINSTALLED = "Verify that the pymssql package is installed."
CONECTIONPROBLEM = "A conection problem occur."
TABLEFIELDPROBLEM = (
    "A conection problem occur trying to obtain a table fields."
)
TABLEDATAPROBLEM = "A conection problem occur trying to obtain a table data."
CREATEDBPROBLEM = "An error occur creating the database."


def _replace_in(string, regex="\d"):
    """
    Util function to replace some content in a string
    :param string:
    :param regex:
    :return:
    """
    return re.sub(regex, "", string)


def _get_port(port):
    """
    Util function to check the specify port
    :param port:
    :return:
    """

    try:
        port = int(port)

    except ValueError:
        raise ValidationError(INVALIDPORT)

    return port


def _get_db_cr(sgdb, database, host, port, user, password):
    """
    Util function to obtain an specific database cursor
    :param sgdb:
    :param database:
    :param host:
    :param port:
    :param user:
    :param password:
    :return:
    """

    conn, port = None, _get_port(port)
    if sgdb == "PostgreSQL":

        try:
            conn = psycopg2.connect(
                database=database,
                host=host,
                port=port,
                user=user,
                password=password,
            )

        except ImportError:
            raise ValidationError(PSYCOPGUNINSTALLED)

    elif sgdb == "MySQL":

        try:
            import pymysql

            conn = pymysql.connect(
                db=database, host=host, port=port, user=user, password=password
            )

        except ImportError:
            raise ValidationError(PYMYSQLUNINSTALLED)

    elif sgdb == "SQLServer":

        try:
            import pymssql

            conn = pymssql.connect(
                database=database,
                server=host,
                port=port,
                user=user,
                password=password,
            )

        except ImportError:
            raise ValidationError(PYMSSQLUNINSTALLED)

    if conn:
        return conn.cursor()

    else:
        raise ValidationError(CONECTIONPROBLEM)


def _get_db_query_4_tables(sgdb, schema, database):
    """
    Function to obtain the SELECT query for a table
    :param sgdb:
    :param schema:
    :param database:
    :return:
    """

    query = (
        f" SELECT table_name, table_type FROM {'information_schema.tables'} "
    )

    if sgdb != "SQLServer":
        query += (
            " WHERE table_schema ="
            f" '{schema if sgdb == 'PostgreSQL' else database}' "
        )

    return query + """ ORDER BY table_name """


def _get_db_query_4_columns(m2o_db, table_name, schema, database):
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
            f" table_schema = '{schema if sgdb == 'PostgreSQL' else database}'"
            " AND "
        )

    return query + f" table_name = '{table_name}' "


def _get_q_4constraints(table_name, column_name, fkey=False, sgdb=None):
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
            return f""" SELECT ccu.table_name FROM {'information_schema.table_constraints'} AS tc
            JOIN {'information_schema.key_column_usage'} AS kcu ON tc.constraint_name = kcu.constraint_name
            JOIN {'information_schema.constraint_column_usage'} AS ccu ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{table_name}'
            AND kcu.column_name = '{column_name}' """

        else:
            return f""" SELECT kcu.referenced_table_name FROM {'information_schema.table_constraints'} AS tc
            JOIN {'information_schema.key_column_usage'} AS kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{table_name}'
            AND kcu.column_name = '{column_name}' """

    else:
        return f""" SELECT * FROM {'information_schema.table_constraints'} AS tc
        JOIN {'information_schema.key_column_usage'} AS kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = '{table_name}'
        AND kcu.column_name = '{column_name}' """


def _get_odoo_field_tuple_4insert(
    name, field_description, ttype, required=False
):
    """
    Function to obtain the tuple for a insert operation (0, 0, {...})
    :param name:
    :param field_description:
    :param ttype:
    :param required:
    :return:
    """

    return (
        0,
        0,
        dict(
            name=name.lower().replace("ñ", "n"),
            field_description=field_description.replace("_", " "),
            ttype=ttype,
            required=required,
        ),
    )


def _get_odoo_ttype(data_type):
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


def _get_table_fields(table_name, m2o_db):
    """
    Function to obtain a table fields
    :param table_name:
    :param m2o_db:
    :return:
    """

    try:
        sgdb = m2o_db.m2o_dbtype.name
        database = m2o_db.database
        cr = _get_db_cr(
            sgdb=sgdb,
            database=database,
            host=m2o_db.host,
            port=m2o_db.port,
            user=m2o_db.user,
            password=m2o_db.password,
        )
        str_query_4_columns = _get_db_query_4_columns(
            m2o_db, table_name, m2o_db.schema, database
        )
        cr.execute(str_query_4_columns)

        l_fields = []
        having_column_name = False
        lst_column_info = cr.fetchall()
        for column_info in lst_column_info:

            column_name = column_info[3]

            if column_name == "name":
                having_column_name = True

            elif len(column_name) > 63:
                slice_column_name = column_name[:63]
                _logger.warning(
                    f"Slice column {column_name} to"
                    f" {slice_column_name} because length is upper than 63."
                )
                column_name = slice_column_name

            str_query_4_constraints = _get_q_4constraints(
                table_name, column_name
            )
            cr.execute(str_query_4_constraints)
            if (
                m2o_db.accept_primary_key or not cr.fetchone()
            ):  # if it is not a primary key

                str_query_4_constraints_fkey = _get_q_4constraints(
                    table_name, column_name, fkey=True, sgdb=sgdb
                )
                cr.execute(str_query_4_constraints_fkey)
                is_m2o = cr.fetchone()

                t_odoo_field_4insert = _get_odoo_field_tuple_4insert(
                    column_name,
                    column_name.capitalize(),
                    "many2one" if is_m2o else _get_odoo_ttype(column_info[7]),
                    column_info[6] == "NO",
                )

                if is_m2o:  # It is a foreign key?
                    model_name = is_m2o[0]
                    name_splitted = model_name.split("_", maxsplit=1)

                    if len(name_splitted) > 1:
                        module_name, table_name = (
                            name_splitted[0],
                            name_splitted[1],
                        )

                    else:
                        module_name, table_name = "comun", name_splitted[0]
                    t_odoo_field_4insert[2]["relation"] = f"{table_name}"

                l_fields.append(t_odoo_field_4insert)

        if not having_column_name:
            l_fields.append(
                _get_odoo_field_tuple_4insert("name", "Name", "char")
            )

        return l_fields

    except psycopg2.OperationalError:
        raise ValidationError(TABLEFIELDPROBLEM)


def _get_table_data(table_name, m2o_db, model_created_fields):
    """
    Function to obtain a table data
    :param table_name:
    :param m2o_db:
    :param model_created_fields:
    :return:
    """

    port = _get_port(m2o_db.port)
    try:
        cr = _get_db_cr(
            sgdb=m2o_db.m2o_dbtype.name,
            database=m2o_db.database,
            host=m2o_db.host,
            port=port,
            user=m2o_db.user,
            password=m2o_db.password,
        )
        query = f" SELECT {','.join(model_created_fields)} FROM {table_name} "
        cr.execute(query)

        return cr.fetchall()

    except psycopg2.OperationalError:
        raise ValidationError(TABLEDATAPROBLEM)


class CodeGeneratorDbType(models.Model):
    _name = "code.generator.db.type"
    _description = "Code Generator Db Type"

    name = fields.Char(string="Db Type Name", help="Db Type", required=True)

    _sql_constraints = [
        ("unique_name", "unique (name)", "The Db Type must be unique.")
    ]


class CodeGeneratorDb(models.Model):
    _name = "code.generator.db"
    _description = "Code Generator Db"
    _rec_name = "database"

    m2o_dbtype = fields.Many2one(
        "code.generator.db.type",
        "Db Type",
        required=True,
        default=lambda self: self.env.ref(
            "code_generator_db_servers.code_generator_db_type_pgsql"
        ).id,
        ondelete="cascade",
    )

    m2o_dbtype_name = fields.Char(related="m2o_dbtype.name")

    database = fields.Char(string="Db Name", help="Db Name", required=True)

    schema = fields.Char(
        string="Schema", help="Schema", required=True, default="public"
    )

    host = fields.Char(string="Ip address", help="Ip address", required=True)

    port = fields.Char(string="Port", help="Port", required=True)

    user = fields.Char(string="User", help="User", required=True)

    password = fields.Char(string="Password", help="Password", required=True)

    accept_primary_key = fields.Boolean(
        string="Accept Primary Key",
        help="Integrate primary key fields in column",
        default=False,
    )

    _sql_constraints = [
        (
            "unique_db",
            "unique (m2o_dbtype, host, port)",
            "The Db Type, host and port combination must be unique.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):

        failure, result = 0, None
        for value in vals_list:

            try:

                sgdb = (
                    self.env["code.generator.db.type"]
                    .browse(value["m2o_dbtype"])
                    .name
                )
                cr = _get_db_cr(
                    sgdb=sgdb,
                    database=value["database"],
                    host=value["host"],
                    port=value["port"],
                    user=value["user"],
                    password=value["password"],
                )

                result = super(CodeGeneratorDb, self).create(value)

                str_query_4_tables = _get_db_query_4_tables(
                    sgdb, value["schema"], value["database"]
                )
                cr.execute(str_query_4_tables)
                for table_info in cr.fetchall():
                    dct_all_table = dict(
                        m2o_db=result.id,
                        name=table_info[0],
                        table_type="view"
                        if table_info[1] == "VIEW"
                        else "table",
                    )

                    self.env["code.generator.db.table"].sudo().create(
                        dct_all_table
                    )

            except Exception as e:
                failure += 1
                _logger.error(e)

        if len(vals_list) == failure:
            raise ValidationError(CREATEDBPROBLEM)

        return result


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

    _sql_constraints = [
        (
            "unique_db_table",
            "unique (m2o_db, name)",
            "The Db and name combination must be unique.",
        )
    ]

    @api.multi
    def toggle_nomenclator(self):
        for table in self:
            table.nomenclator = not table.nomenclator

    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            result = super(CodeGeneratorDbTable, self).create(value)
            lst_fields = _get_table_fields(result.name, result.m2o_db)
            for field in lst_fields:
                column_value = {
                    "name": field[2].get("name"),
                    "required": field[2].get("required"),
                    "column_type": field[2].get("ttype"),
                    "description": field[2].get("field_description"),
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
    def generate_module(self, generated_module_name=False):
        """
        Function to generate a module
        :return:
        """

        # TODO associate code.generator.db.table to code.generator.db.table to remote generated_module_name

        l_module_tables = dict(comun=[])
        for table in self:

            name_splitted = table.name.split("_", maxsplit=1)

            if len(name_splitted) > 1:
                module_name, table_name = name_splitted[0], name_splitted[1]

            else:
                module_name, table_name = "comun", name_splitted[0]

            t_tname_m2o_db_nom = (table_name, table.m2o_db, table.nomenclator)
            if module_name not in l_module_tables:
                l_module_tables[module_name] = [t_tname_m2o_db_nom]

            else:
                l_module_tables[module_name].append(t_tname_m2o_db_nom)

        for module_name in l_module_tables.keys():

            if not l_module_tables[module_name]:
                continue

            module_name_caps = module_name.capitalize()
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

            lst_model = list(
                map(
                    lambda t_info: dict(
                        name="Model %s belonging to Module %s"
                        % (t_info[0].capitalize(), module_name_caps),
                        model=_replace_in(t_info[0].lower().replace("_", ".")),
                        field_id=_get_table_fields(
                            self._get_model_name(module_name, t_info[0]),
                            t_info[1],
                        ),
                        m2o_module=module.id,
                        nomenclator=t_info[2],
                    ),
                    l_module_tables[module_name],
                )
            )
            models_created = self.env["ir.model"].create(lst_model)
            # TODO hack, the many2one is not created in this database, force to create it
            # model.init() not working, create foreign key manually
            # models_created._setup_complete()
            # models_created._auto_init()
            # models_created.init()
            # models_created.recompute()
            for dct_model in [lst_model[3]]:
                for tpl_field in dct_model.get("field_id"):
                    dct_field = tpl_field[2]
                    if dct_field.get("ttype") == "many2one":
                        model_db = dct_model.get("model").replace(".", "_")
                        field_db = dct_field.get("name").replace(".", "_")
                        field_relation_db = dct_field.get("relation").replace(
                            ".", "_"
                        )
                        self.env.cr.execute(
                            f"""
                            alter table {model_db}
                                add {field_db} int;

                            alter table {model_db}
                                add constraint {model_db}_{field_relation_db}_id_fk
                                    foreign key ({field_db}) references {field_relation_db};
                            """
                        )

            models_nomenclator = models_created.filtered("nomenclator")
            lst_models_created = self._reorder_dependence_nonmenclature_model(
                models_nomenclator
            )
            for model_created in lst_models_created:
                model_created_fields = model_created.field_id.filtered(
                    lambda field: field.name not in MAGIC_FIELDS + ["name"]
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

                l_foreign_table_data = _get_table_data(
                    foreign_table.name,
                    foreign_table.m2o_db,
                    mapped_model_created_fields,
                )

                lst_data = list(
                    map(
                        self._conform_model_created_data(
                            mapped_model_created_fields
                        ),
                        l_foreign_table_data,
                    )
                )
                for i, name in enumerate(mapped_model_created_fields):
                    if model_created_fields[i].ttype == "many2one":
                        relation_model = model_created_fields[i].relation
                        relation_field = model_created_fields[i].name
                        for data in lst_data:
                            # Update many2one
                            data[name] = (
                                self.env[relation_model]
                                .search([(relation_field, "=", data[name])])
                                .id
                            )
                results = self.env[model_created.model].sudo().create(lst_data)
                if generated_module_name:
                    # Generate xml_id for all nonmenclature
                    for result in results:
                        second = (
                            result.name if result.name else uuid.uuid1().int
                        )
                        new_id = (
                            f"{model_created.model.replace('.', '_')}_{second}"
                        )
                        self.env["ir.model.data"].create(
                            {
                                "name": new_id,
                                "model": model_created.model,
                                "module": generated_module_name,
                                "res_id": result.id,
                                "noupdate": True,
                            }
                        )
        return module

    @staticmethod
    def _reorder_dependence_nonmenclature_model(models_created):
        # TODO cannot support looping dependency, this will break later, need to detect it
        lst_model_ordered = []
        dct_model = {a.model: a for a in models_created}
        dct_model_depend = defaultdict(list)
        for model_id in models_created:
            for field_id in model_id.field_id:
                if (
                    field_id.ttype == "many2one"
                    and field_id.relation in dct_model.keys()
                ):
                    dct_model_depend[model_id.model].append(
                        dct_model[field_id.relation]
                    )
        # Reorder
        # add in begin if no dependency
        # add at the end if dependency, but it is not found
        # Add after the last dependency if added
        for model_id in models_created:
            if model_id.model in dct_model_depend.keys():
                # search index
                final_index = -1
                for ele in dct_model_depend[model_id.model]:
                    try:
                        index = lst_model_ordered.index(ele)
                        if index > final_index:
                            final_index = index
                    except ValueError:
                        pass
                if final_index >= 0:
                    lst_model_ordered.insert(final_index + 1, model_id)
                else:
                    lst_model_ordered.append(model_id)
            else:
                lst_model_ordered.insert(0, model_id)

        return lst_model_ordered


class CodeGeneratorDbColumn(models.Model):
    _name = "code.generator.db.column"
    _description = "Code Generator Db Column"

    m2o_table = fields.Many2one(
        "code.generator.db.table", "Table", required=True, ondelete="cascade"
    )

    name = fields.Char(string="Name", help="Column name", required=True)

    description = fields.Char(
        string="Description",
        help="Column description",
    )

    required = fields.Boolean(
        string="Required",
        help="Column required",
    )

    column_type = fields.Selection(
        string="Column type",
        help="Column type",
        required=True,
        selection=[
            ("char", "Char"),
            ("text", "Text"),
            ("integer", "Integer"),
            ("monetary", "Monetary"),
            ("float", "Float"),
            ("datetime", "Datetime"),
            ("date", "Date"),
            ("boolean", "Boolean"),
            ("html", "Html"),
            ("binary", "Binary"),
            ("selection", "Selection"),
            ("many2one", "Many2one"),
            # TODO support many2many
            # ("many2many", "Many2many"),
            # Cannot detect one2many in database relation
            # ("one2many", "One2many"),
        ],
    )
