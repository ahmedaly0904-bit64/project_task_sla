# Task SLA Escalation

An Odoo 17 module that puts a deadline on how long a task may sit in one stage.

If a task stays in its stage for more than 24 hours, a scheduled action escalates
it to a designated user. Without something like this, a response time target
lives in a document and depends on people remembering it.

## What it adds

On `project.task`:

| Field | Type | Purpose |
|---|---|---|
| `stage_entered_date` | `Datetime` | When the task entered its current stage |
| `sla_deadline` | `Datetime`, computed, stored | `stage_entered_date + 24h` |
| `sla_notified` | `Boolean`, `copy=False` | Guard that stops a task escalating twice |

On `project.project`:

| Field | Purpose |
|---|---|
| `sla_exempt` | Excludes a project from SLA tracking |

Moving a task to a new stage resets all three. The entry date is rewritten, the
deadline is recomputed from it, and the notified flag goes back to false, so the
new stage starts from zero.

## Configuration

```
System Parameter:  project_task_sla.operations_lead_user_id = <res.users id>
```

If it is unset, the scheduled action returns without doing anything.

> [!WARNING]
> Point this at an active user. If the parameter holds the id of a deactivated
> account, escalations are still created and delivered to nobody, and nothing
> reports a problem. "Does nothing" and "does the wrong thing somewhere nobody
> is looking" are not the same failure, and only one of them is visible.
> `test_missing_parameter_escalates_nothing` covers the empty case for the same
> reason.

## How escalation works

A daily scheduled action, `Task SLA: Check Overdue Tasks`, searches for tasks
matching all four conditions below, then schedules a to-do activity for the
Operations Lead on each one.

| Condition | Why it is there |
|---|---|
| `sla_deadline < now` | The deadline has passed |
| `sla_notified = False` | Not escalated yet, which makes the job safe to run twice |
| `stage_id.fold = False` | The task is not sitting in a closed stage |
| `project_id.sla_exempt = False` | Skips templates and archived projects |

The last condition is there for a practical reason. Nobody works a template, so
every task inside one goes overdue 24 hours after it is created. That buries the
real overdue work under daily noise until the Operations Lead stops reading the
inbox at all.

## Tests

```bash
odoo-bin -c <your.conf> -u project_task_sla \
         --test-enable --test-tags /project_task_sla --stop-after-init
```

Nine cases live in `project_task_sla/tests/test_sla.py`. Four cover the
computation, the escalation, the stage reset, and the rule that saving a task
without changing its stage must not restart the clock. The other five cover the
cases where the module has to stay quiet: one for each condition in the table
above, plus the missing configuration guard.

| Test | Covers |
|---|---|
| `test_deadline_is_24h_after_stage_entry` | The computed field |
| `test_overdue_task_is_escalated_once` | The escalation reaches the right user |
| `test_stage_move_resets_the_sla` | All three fields reset, and the `@api.depends` chain fires |
| `test_writing_the_same_stage_does_not_reset_the_sla` | Pressing Save cannot buy a task another 24 hours |
| `test_task_before_its_deadline_is_not_escalated` | Nothing happens while the deadline is still ahead |
| `test_cron_does_not_escalate_twice` | The idempotency guard |
| `test_exempt_project_is_never_escalated` | Templates stay quiet |
| `test_folded_stage_is_never_escalated` | Closed tasks stay quiet |
| `test_missing_parameter_escalates_nothing` | Missing configuration fails quietly rather than loudly |

The coverage was checked by breaking the module on purpose. Removing any one of
the four conditions above, or the guard in `write()` that checks the stage really
changed, turns a test red.

None of them wait for real time to pass. The deadline is stored data rather than
an event, so each test writes `stage_entered_date` into the past and calls the
cron method directly.

## Known limitations

- Escalation goes to a single configured user rather than to each task's own
  owner. That is enough while one person chases everything, and it is the first
  thing to change when that stops being true.
- Calendar hours, not working hours. A task entering a stage at 16:00 on Thursday
  gets a Friday deadline whether or not Friday is a working day. Reading the
  deadline off `resource.calendar` would fix this.
- In-app only. The escalation is an Odoo activity, with no email or chat message.
- The 24 hour window is fixed. It cannot be configured per project or per stage.

## Translations

`i18n/project_task_sla.pot` holds the extracted terms and `i18n/ar.po` an Arabic
translation, covering the field labels, the help text, the scheduled action, and
both strings the escalation activity shows the user.

To add another language, copy the `.pot` file to `i18n/<code>.po` and fill in the
`msgstr` lines. Odoo picks the file up on the next module upgrade.

## Requirements

Odoo 17.0. Depends on `project`.

## License

LGPL-3
