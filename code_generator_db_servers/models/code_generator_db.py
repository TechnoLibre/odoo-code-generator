import psycopg2
from odoo import _, models, fields, api
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

INVALIDPORT = "The specify port is invalid."
PSYCOPGUNINSTALLED = "Verify that the psycopg package is installed."
PYMYSQLUNINSTALLED = "Verify that the pymysql package is installed."
PYMSSQLUNINSTALLED = "Verify that the pymssql package is installed."
CONNECTIONPROBLEM = "A connection problem occur."
CREATEDBPROBLEM = "An error occur creating the database."


class CodeGeneratorDbType(models.Model):
    _name = "code.generator.db.type"
    _description = "Code Generator Db Type"

    name = fields.Char(string="Db Type Name", help="Db Type", required=True)

    _sql_constraints = [
        ("unique_name", "unique (name)", "The Db Type must be unique.")
    ]


class CodeGeneratorDbUpdateMigrationField(models.Model):
    _name = "code.generator.db.update.migration.field"
    _description = "Code Generator Db update field before migration"

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    model_name = fields.Char(
        string="Model name", help="Name of field to update.", required=True
    )

    field_name = fields.Char(
        string="Field name", help="Name of field to update.", required=True
    )

    new_field_name = fields.Char(string="New name")

    new_description = fields.Char(string="New description")

    new_type = fields.Char(string="New type")

    force_widget = fields.Char(
        string="Force widget",
        help="Use this widget for this field when create views.",
    )

    add_one2many = fields.Boolean(
        string="Add one2many",
        help="Add field one2many to related model on this field.",
    )

    sql_select_modify = fields.Char(
        string="SQL selection modify",
        help="Change field name with this query",
    )

    compute_data_function = fields.Char(
        string="Function compute data",
        help=(
            "Will be execute when extract data, first argument is the origin"
            " data and return data to be overwrite. In string, will be execute"
            " with eval. Use variable name from field in the model."
        ),
    )

    path_binary = fields.Char(
        string="Path binary type",
        help=(
            "Attribut path to use with value of char to binary, import binary"
            " in database."
        ),
    )

    new_help = fields.Char(string="New help")

    new_required = fields.Boolean(string="New required")

    delete = fields.Boolean(
        string="Delete", help="When enable, remove the field in generation."
    )

    ignore_field = fields.Boolean(
        string="Ignore field",
        help="When enable, ignore import field and never compute it.",
    )

    new_change_required = fields.Boolean(
        string="New required update",
        help="Set at True if need to update required value.",
    )


class CodeGeneratorDbUpdateMigrationModel(models.Model):
    _name = "code.generator.db.update.migration.model"
    _description = "Code Generator Db update model before migration"

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        required=True,
        ondelete="cascade",
    )

    model_name = fields.Char(
        string="Model name", help="Name of field to update.", required=True
    )

    new_rec_name = fields.Char(string="New rec name")

    new_description = fields.Char(string="New description")

    new_model_name = fields.Char(string="New model name")


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
                cr = self.get_db_cr(
                    sgdb=sgdb,
                    database=value["database"],
                    host=value["host"],
                    port=value["port"],
                    user=value["user"],
                    password=value["password"],
                )

                result = super(CodeGeneratorDb, self).create(value)

                str_query_4_tables = self.get_db_query_4_tables(
                    sgdb, value["schema"], value["database"]
                )
                cr.execute(str_query_4_tables)
                for table_info in cr.fetchall():
                    table_name = table_info[0]
                    split_name = table_name.split("_", maxsplit=1)
                    if len(split_name) > 1:
                        module_name = split_name[0]
                    else:
                        module_name = ""
                    dct_all_table = dict(
                        m2o_db=result.id,
                        name=table_name,
                        table_type="view"
                        if table_info[1] == "VIEW"
                        else "table",
                        module_name=module_name,
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

    def get_db_cr(self, sgdb, database, host, port, user, password):
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

        conn, port = None, self.get_port(port)
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
                    db=database,
                    host=host,
                    port=port,
                    user=user,
                    password=password,
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
            raise ValidationError(CONNECTIONPROBLEM)

    @staticmethod
    def get_db_query_4_tables(sgdb, schema, database):
        """
        Function to obtain the SELECT query for a table
        :param sgdb:
        :param schema:
        :param database:
        :return:
        """

        query = (
            " SELECT table_name, table_type FROM"
            f" {'information_schema.tables'} "
        )

        if sgdb != "SQLServer":
            query += (
                " WHERE table_schema ="
                f" '{schema if sgdb == 'PostgreSQL' else database}' "
            )

        return query + """ ORDER BY table_name """

    @staticmethod
    def get_port(port):
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
