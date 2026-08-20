# Task SLA Escalation

An Odoo 17 module that enforces one rule from an internal operations playbook:

> Any handoff between two departments must get a response within 24 hours,
> or it escalates to the Operations Lead.

Without it the rule lives in a document and depends on people remembering it.

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
> Point this at an active user. During development it was set to a deactivated
> account for a while, and the documentation claimed it was empty. Escalations
> were being created and delivered to nobody, and nothing anywhere reported a
> problem. "Does nothing" and "does the wrong thing somewhere nobody is looking"
> are not the same failure, and only one of them is visible.
> `test_missing_parameter_escalates_nothing` exists because of that.

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

Seven cases live in `project_task_sla/tests/test_sla.py`. Three cover the
computation, the escalation and the stage reset. The other four cover the cases
where the module has to stay quiet, one per condition in the table above.

| Test | Covers |
|---|---|
| `test_deadline_is_24h_after_stage_entry` | The computed field |
| `test_overdue_task_is_escalated_once` | The escalation reaches the right user |
| `test_stage_move_resets_the_sla` | All three fields reset, and the `@api.depends` chain fires |
| `test_cron_does_not_escalate_twice` | The idempotency guard |
| `test_exempt_project_is_never_escalated` | Templates stay quiet |
| `test_folded_stage_is_never_escalated` | Closed tasks stay quiet |
| `test_missing_parameter_escalates_nothing` | Missing configuration fails quietly rather than loudly |

None of them wait for real time to pass. The deadline is stored data rather than
an event, so each test writes `stage_entered_date` into the past and calls the
cron method directly.

## Known limitations

- Calendar hours, not working hours. A task entering a stage at 16:00 on Thursday
  gets a Friday deadline whether or not Friday is a working day. Reading the
  deadline off `resource.calendar` would fix this.
- In-app only. The escalation is an Odoo activity, with no email or chat message.
- The 24 hour window is fixed. It cannot be configured per project or per stage.

## Requirements

Odoo 17.0. Depends on `project`.

## License

LGPL-3
