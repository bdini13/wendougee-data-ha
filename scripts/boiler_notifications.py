"""Build native HA notifications; recipients stay in private deployment config.

Requires four persistent input_text helpers named espresso_{boiler}_{kind}_notified.
No initial value: restore markers across restart. These automations never control
the machine. A marker is saved before dispatch (at-most-once attempts, no retries).
"""

# Jinja expressions are kept intact for comparison with HA's automation editor.
# ruff: noqa: E501


def automations(recipients: list[str]) -> list[dict]:
    """Return per-boiler ready and verified scheduled-off automations."""
    if not recipients or any(
        not r.startswith("notify.mobile_app_") for r in recipients
    ):
        raise ValueError("Explicit companion-phone notification services required")
    result = []
    for boiler in ("brew", "steam"):
        health = f"sensor.wendougee_data_s_{boiler}_schedule_health"
        enabled = f"input_boolean.espresso_{boiler}_schedule_enabled"
        temperature = f"sensor.wendougee_data_{boiler}_temperature"
        target = f"sensor.wendougee_data_{boiler}_target"
        for kind in ("ready", "off"):
            marker = f"input_text.espresso_{boiler}_{kind}_notified"
            if kind == "ready":
                triggers = [{"trigger": "time_pattern", "seconds": "/30"}]
                value = "{{ now().date().isoformat() }}"
                condition = f"""{{% set t = states('{temperature}') %}}
{{% set target = states('{target}') %}}
{{% set poll = as_timestamp(state_attr('sensor.wendougee_data_s_communication_health', 'last_successful_poll'), 0) %}}
{{{{ is_state('{enabled}', 'on')
and is_state('binary_sensor.wendougee_data_{boiler}_heating_enabled', 'on')
and is_state('sensor.wendougee_data_s_communication_health', 'healthy')
and 0 <= as_timestamp(now()) - poll < 90
and is_number(t) and is_number(target)
and state_attr('{temperature}', 'unit_of_measurement') == state_attr('{target}', 'unit_of_measurement')
and t | float(0) >= target | float(999)
and states('{marker}') not in ['unknown', 'unavailable']
and states('{marker}') != now().date().isoformat() }}}}"""
                message = f"WENDOUGEE DATA S: {boiler.title()} boiler reached its setpoint ({{{{ states('{temperature}') }}}} {{{{ state_attr('{temperature}', 'unit_of_measurement') }}}}; target {{{{ states('{target}') }}}})."
            else:
                triggers = [
                    {
                        "trigger": "state",
                        "entity_id": health,
                        "attribute": "last_verified_at",
                    }
                ]
                value = "{{ trigger.to_state.attributes.last_verified_at }}"
                condition = f"""{{{{ trigger.from_state is not none and trigger.to_state is not none
and trigger.from_state.state not in ['unknown', 'unavailable']
and trigger.to_state.state not in ['unknown', 'unavailable']
and is_state('{enabled}', 'on')
and trigger.to_state.attributes.get('last_result') == 'verified_off'
and trigger.to_state.attributes.get('last_verified_at') is not none
and trigger.from_state.attributes.get('last_verified_at') != trigger.to_state.attributes.get('last_verified_at')
and 0 <= as_timestamp(now()) - as_timestamp(trigger.to_state.attributes.get('last_verified_at'), 0) < 120
and states('{marker}') not in ['unknown', 'unavailable']
and states('{marker}') != trigger.to_state.attributes.get('last_verified_at') }}}}"""
                message = f"WENDOUGEE DATA S: {boiler.title()} boiler scheduled shutdown verified. The machine reports this boiler disabled; it may still be hot."
            result.append(
                {
                    "id": f"espresso_{boiler}_{kind}_phone_notification",
                    "alias": f"Espresso {boiler} {kind} phone notification",
                    "description": "Read-only notification; persistent deduplication; no machine commands.",
                    "mode": "single",
                    "triggers": triggers,
                    "conditions": [
                        {"condition": "template", "value_template": condition}
                    ],
                    "actions": [
                        {
                            "action": "input_text.set_value",
                            "target": {"entity_id": marker},
                            "data": {"value": value},
                        },
                        *[
                            {
                                "action": recipient,
                                "continue_on_error": True,
                                "data": {"title": "Espresso", "message": message},
                            }
                            for recipient in recipients
                        ],
                    ],
                }
            )
    return result
