import logging
import re

from psycopg2._psycopg import ProgrammingError

from odoo import _, api, fields, models, tools
from odoo.exceptions import MissingError, ValidationError

_logger = logging.getLogger(__name__)

CONSCREATEUNABLE = _("Unable to create the constraint.")
CONSDELETECREATEUNABLE = _(
    "Since you modify the sql constraint definition we must delete it and"
    " create a new one, and we were unable to do it."
)
CONSMODIFYUNABLE = _("Unable to modify the constraint.")
CONSDELETEUNABLE = _("Unable to delete the constraint.")


def sql_constraint(el_self, constraints):
    cr = el_self._cr
    foreign_key_re = re.compile(r"\s*foreign\s+key\b.*", re.I)

    def process(key, definition):
        conname = "%s_%s" % (el_self._table, key)
        current_definition = tools.constraint_definition(
            cr, el_self._table, conname
        )
        if not current_definition:
            # constraint does not exists
            return add_constraint(cr, el_self._table, conname, definition)
        elif current_definition != definition:
            # constraint exists but its definition may have changed
            drop_constraint(cr, el_self._table, conname)
            return add_constraint(cr, el_self._table, conname, definition)

        else:
            return True

    result = False
    for sql_key, sql_definition, _ in constraints:
        if foreign_key_re.match(sql_definition):
            el_self.pool.post_init(process, sql_key, sql_definition)
        else:
            result = process(sql_key, sql_definition)

        if not result:
            break

    return result


def add_constraint(cr, tablename, constraintname, definition):
    """Add a constraint on the given table."""
    query1 = 'ALTER TABLE "{}" ADD CONSTRAINT "{}" {}'.format(
        tablename, constraintname, definition
    )
    query2 = 'COMMENT ON CONSTRAINT "{}" ON "{}" IS %s'.format(
        constraintname, tablename
    )
    try:
        with cr.savepoint():
            cr.execute(query1)
            cr.execute(query2, (definition,))
            _logger.debug(
                "Table %r: added constraint %r as %s",
                tablename,
                constraintname,
                definition,
            )
            return True
    except Exception:
        msg = (
            "Table %r: unable to add constraint %r!\nIf you want to have it,"
            " you should update the records and execute manually:\n%s"
        )
        _logger.warning(msg, tablename, constraintname, query1, exc_info=True)
        return False


def drop_constraint(cr, tablename, constraintname):
    """drop the given constraint."""
    try:
        with cr.savepoint():
            cr.execute(
                'ALTER TABLE "{}" DROP CONSTRAINT "{}"'.format(
                    tablename, constraintname
                )
            )
            _logger.debug(
                "Table %r: dropped constraint %r", tablename, constraintname
            )
            return True
    except ProgrammingError as proerror:
        return proerror.pgerror.count("does not exist") or False

    except Exception:
        _logger.warning(
            "Table %r: unable to drop constraint %r!",
            tablename,
            constraintname,
        )
        return False


class IrModelConstraint(models.Model):
    _inherit = "ir.model.constraint"

    code_generator_id = fields.Many2one(
        comodel_name="code.generator.module",
        string="Code Generator",
        ondelete="cascade",
    )

    message = fields.Char()

    model_state = fields.Selection(related="model.state")

    module = fields.Many2one(
        default=lambda self: self.env["ir.module.module"]
        .search([("name", "=", "base")])[0]
        .id,
    )

    @api.model_create_multi
    def create(self, vals_list):
        imcs = super(IrModelConstraint, self).create(vals_list)

        for imc in imcs:
            m_target = self.env[imc.model.model]
            t_constrain = (imc.name, imc.definition, imc.message)
            if not sql_constraint(
                m_target, m_target._sql_constraints + [t_constrain]
            ):
                raise ValidationError(CONSCREATEUNABLE)

        return imcs

    @api.multi
    def write(self, vals):
        if "definition" in vals:
            for imc in self:
                tablename = self.env[imc.model.model]._table
                if not drop_constraint(
                    self._cr, tablename, "%s_%s" % (tablename, imc.name)
                ):
                    raise ValidationError(CONSDELETECREATEUNABLE)

        result = super(IrModelConstraint, self).write(vals)

        for imc in self:
            m_target = self.env[imc.model.model]
            t_constrain = (imc.name, imc.definition, imc.message)
            if not sql_constraint(m_target, [t_constrain]):
                raise ValidationError(CONSMODIFYUNABLE)

        return result

    @api.multi
    def unlink(self):
        for imc in self:
            try:
                tablename = self.env[imc.model.model]._table
                if not drop_constraint(
                    self._cr, tablename, "%s_%s" % (tablename, imc.name)
                ):
                    raise ValidationError(CONSDELETEUNABLE)

            except MissingError:
                _logger.warning(
                    "The registry entry associated with %s no longer exists"
                    % imc.model.model
                )

        return super(IrModelConstraint, self).unlink()
