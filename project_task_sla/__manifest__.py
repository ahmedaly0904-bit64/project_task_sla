{
    'name': 'Task SLA Escalation',
    'version': '1.0',
    'summary': 'SLA deadline tracking and escalation for internal task handoffs',
    'description': """
        Adds an sla_deadline field to project.task, computed automatically
        as: date the task entered its current stage + 24 hours.
        A scheduled action flags overdue tasks for Operations Lead escalation.
    """,
    'author': 'Ahmed Aly',
    'category': 'Project',
    'license': 'LGPL-3',
    'depends': ['project'],
    'data': [
        'views/project_task_views.xml',
        'views/project_project_views.xml',
        'data/ir_cron.xml',
        ],
    'installable': True,
    'application': False,
}
