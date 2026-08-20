from odoo import models, fields, api, _
from datetime import timedelta


class ProjectTask(models.Model):
    _inherit = 'project.task'

    stage_entered_date = fields.Datetime(
        string='Stage Entered Date',
        default=fields.Datetime.now,
    )

    sla_deadline = fields.Datetime(
        string='SLA Deadline',
        compute='_compute_sla_deadline',
        store=True,
    )

    sla_notified = fields.Boolean(
        string='SLA Notified',
        default=False,
        copy=False,
    )

    @api.depends('stage_entered_date')
    def _compute_sla_deadline(self):
        for task in self:
            if task.stage_entered_date:
                task.sla_deadline = task.stage_entered_date + timedelta(hours=24)
            else:
                task.sla_deadline = False

    def write(self, vals):
        if 'stage_id' in vals:
            changed_tasks = self.filtered(lambda t: t.stage_id.id != vals['stage_id'])
        else:
            changed_tasks = self.browse()

        res = super().write(vals)

        if changed_tasks:
            changed_tasks.write({
                'stage_entered_date': fields.Datetime.now(),
                'sla_notified': False,
            })
        return res

    @api.model
    def _cron_check_sla_overdue(self):
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        operations_lead_id = IrConfigParam.get_param('project_task_sla.operations_lead_user_id')

        if not operations_lead_id:
            return

        operations_lead_id = int(operations_lead_id)

        overdue_tasks = self.search([
            ('sla_deadline', '<', fields.Datetime.now()),
            ('sla_notified', '=', False),
            ('stage_id.fold', '=', False),
            ('project_id.sla_exempt', '=', False),
        ])

        for task in overdue_tasks:
            task.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('SLA overdue: %s', task.name),
                note=_('This task has passed its 24 hour SLA deadline in '
                       'its current stage.'),
                user_id=operations_lead_id,
            )
            task.sla_notified = True