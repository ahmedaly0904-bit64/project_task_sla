from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestTaskSla(TransactionCase):
    """كل test هنا بيجاوب على سؤال واحد: امتى النظام بيصعّد، وامتى المفروض يسكت."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.lead = cls.env['res.users'].create({
            'name': 'Operations Lead',
            'login': 'sla_ops_lead',
        })
        cls.env['ir.config_parameter'].sudo().set_param(
            'project_task_sla.operations_lead_user_id', str(cls.lead.id)
        )

        Stage = cls.env['project.task.type']
        cls.stage_open = Stage.create({'name': 'Open', 'sequence': 1, 'fold': False})
        cls.stage_review = Stage.create({'name': 'Review', 'sequence': 2, 'fold': False})
        cls.stage_done = Stage.create({'name': 'Done', 'sequence': 3, 'fold': True})

        cls.project = cls.env['project.project'].create({
            'name': 'SLA Test Project',
            'type_ids': [(6, 0, [cls.stage_open.id, cls.stage_review.id, cls.stage_done.id])],
        })

    # ------------------------------------------------------------------ أدوات

    def _make_task(self, project=None, stage=None, hours_ago=0):
        """تاسك بتدخل مرحلتها من `hours_ago` ساعة. تزوير الوقت بدل الاستنى."""
        task = self.env['project.task'].create({
            'name': 'SLA task',
            'project_id': (project or self.project).id,
            'stage_id': (stage or self.stage_open).id,
        })
        if hours_ago:
            task.stage_entered_date = fields.Datetime.now() - timedelta(hours=hours_ago)
        return task

    def _activities(self, task):
        """بنقرا من mail.activity مباشرة عشان مانتعلقش بالـ cache."""
        return self.env['mail.activity'].search([
            ('res_model', '=', 'project.task'),
            ('res_id', '=', task.id),
        ])

    def _run_cron(self):
        self.env['project.task']._cron_check_sla_overdue()

    # ------------------------------------------------------- ١ · الحساب نفسه

    def test_deadline_is_24h_after_stage_entry(self):
        task = self._make_task()
        self.assertEqual(
            task.sla_deadline,
            task.stage_entered_date + timedelta(hours=24),
            "الـ deadline لازم يتحسب لوحده من stage_entered_date + 24h",
        )

    # ------------------------------------------------ ٢ · المسار السعيد

    def test_overdue_task_is_escalated_once(self):
        task = self._make_task(hours_ago=25)
        self._run_cron()

        activities = self._activities(task)
        self.assertEqual(len(activities), 1, "تاسك متأخرة لازم تتصعّد مرة واحدة")
        self.assertEqual(activities.user_id, self.lead, "التصعيد لازم يروح للـ Operations Lead")
        self.assertTrue(task.sla_notified, "لازم تتعلّم إنها اتصعّدت")

    # --------------------------------------- ٣ · النقل بيصفّر التلاتة

    def test_stage_move_resets_the_sla(self):
        task = self._make_task(hours_ago=25)
        self._run_cron()
        self.assertTrue(task.sla_notified)
        entered_before = task.stage_entered_date

        task.write({'stage_id': self.stage_review.id})

        self.assertGreater(task.stage_entered_date, entered_before, "التاريخ اتكتب من جديد")
        self.assertEqual(
            task.sla_deadline,
            task.stage_entered_date + timedelta(hours=24),
            "الـ deadline اتحسب تاني — ده اللي بيثبت إن @api.depends شغالة",
        )
        self.assertFalse(task.sla_notified, "المرحلة الجديدة بتبدأ صفحة بيضا")

    # ------------------------------ ٤ · الكرون مرتين = تصعيد واحد

    def test_cron_does_not_escalate_twice(self):
        task = self._make_task(hours_ago=25)
        self._run_cron()
        self._run_cron()

        self.assertEqual(
            len(self._activities(task)), 1,
            "sla_notified هو اللي بيمنع التكرار — لو اتشال هيبقى تصعيد كل يوم",
        )

    # ------------------------------- ٥ · المشاريع المعفاة (الـ templates)

    def test_exempt_project_is_never_escalated(self):
        template = self.env['project.project'].create({
            'name': 'Onboarding Template',
            'sla_exempt': True,
            'type_ids': [(6, 0, [self.stage_open.id])],
        })
        task = self._make_task(project=template, hours_ago=25)
        self._run_cron()

        self.assertFalse(
            self._activities(task),
            "محدش بيشتغل على template — تصعيدها بيدفن التأخير الحقيقي في ضوضاء",
        )

    # ------------------------------------ ٦ · المراحل المقفولة

    def test_folded_stage_is_never_escalated(self):
        task = self._make_task(stage=self.stage_done, hours_ago=25)
        self._run_cron()

        self.assertFalse(self._activities(task), "التاسك خلصت — مفيش حاجة تتصعّد")

    # --------------------------- ٧ · الإعداد ناقص: يسكت من غير ما ينفجر

    def test_missing_parameter_escalates_nothing(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'project_task_sla.operations_lead_user_id', False
        )
        task = self._make_task(hours_ago=25)
        self._run_cron()

        self.assertFalse(self._activities(task))
        self.assertFalse(task.sla_notified)
