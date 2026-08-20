from odoo import models, fields


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sla_exempt = fields.Boolean(
        string='Exempt from SLA',
        default=False,
        help="Templates and archive projects should be exempt. Nobody works a "
             "template, so every task in one goes overdue 24h after creation "
             "and buries real overdue work in noise.",
    )
