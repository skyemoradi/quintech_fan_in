# RF Fan-In Proxy Status Analysis

Source of truth for this analysis:

```text
csi-pdk/csi_quintech_RF_Matrix
```

Compared against:

```text
rules.txt
RF_FAN_IN_PROXY_IMPLEMENTATION_TODO.md
RF_FAN_IN_PROXY_IMPLEMENTATION_PLAN.md
dof-rf.txt
snmpwalk.txt
```

Status date: 2026-05-15.

## Overall Verdict

The fan-in proxy is not complete yet.

The most important issue is a blocking syntax error in `src/csi_quintech_rf_matrix/snmp_setter.py`. Until that is fixed, the proxy cannot import `snmp_setter.py`, so state-change requests that require SNMP sets cannot work.

Some core fan-in work is implemented or partially implemented:

- The device-specific schema is mostly present.
- The active route mapping now targets `parameters.input_ports.connected_outputs`.
- Polling now converts `outputAllInChNr` integers into DoF `connected_outputs` lists.
- The proxy backend no longer does the older output-indexed routing dispatch.
- Setter helper code for range validation, AGC conflict validation, and route conversion has been started.

But several required items are still missing or not currently effective:

- `snmp_setter.py` does not compile.
- `connected_outputs` SNMP set conversion is not currently runnable.
- Detailed fault log entries are not implemented.
- Detailed validation reasons are overwritten by generic failure text.
- Multi-output route warnings are collected but not written into CSI-visible logs.
- `update_settings_on_device()` still does not return `self.result`.
- Mapping cleanup and discover-schema updates from the implementation plan are not complete.

## Static Check Results

### Failing

Command:

```text
python3 -m py_compile src/csi_quintech_rf_matrix/snmp_setter.py
```

Result:

```text
IndentationError: expected an indented block after function definition on line 194 (snmp_setter.py, line 195)
```

Cause:

```python
    def validate_output_index(self, instance):
        ...
        return output_index

        def parse_connected_outputs_for_snmp(self, dofval, instance):
        input_index = self.validate_input_index(instance)
```

`parse_connected_outputs_for_snmp()` is indented under `validate_output_index()`, and its body is not indented relative to the nested function definition. It should be a class method at the same indentation level as `validate_output_index()`.

### Passing

Command:

```text
python3 -m py_compile src/csi_quintech_rf_matrix/snmp_poller.py src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py src/csi_quintech_rf_matrix/proxy_backend.py src/csi_quintech_rf_matrix/main.py
```

Result:

```text
No syntax errors reported.
```

I could not parse `schemas/snmp_to_dof_mapping.yml` with local `python3` because this environment does not have `yaml` installed. The YAML was reviewed manually.

## Findings

### Blocking: `snmp_setter.py` Does Not Compile

File:

```text
src/csi_quintech_rf_matrix/snmp_setter.py:194
```

Current code:

```python
        def parse_connected_outputs_for_snmp(self, dofval, instance):
        input_index = self.validate_input_index(instance)
```

Impact:

- The setter module cannot import.
- `perform_snmp_set()` cannot run.
- `proxy_backend.py` imports `perform_snmp_set`, so this can break application startup or any state-change path that imports the setter.
- None of the new setter-side route, gain, or AGC validation can execute.

Fix needed:

Dedent the function definition to the class level:

```python
    def parse_connected_outputs_for_snmp(self, dofval, instance):
        input_index = self.validate_input_index(instance)
```

Then rerun:

```text
python3 -m py_compile src/csi_quintech_rf_matrix/snmp_setter.py
```

### High: `connected_outputs` Set Logic Is Not Currently Working

Required behavior from `rules.txt`:

```text
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

must become:

```text
outputAllInChNr.6 = 5
```

Implementation status:

- Mapping is correct at `schemas/snmp_to_dof_mapping.yml:63-67`.
- `lookup_oid()` calls `self.parse_connected_outputs_for_snmp()` at `snmp_setter.py:335-339`.
- But the helper has the syntax/indentation error above, so this path is not runnable.

After the syntax fix, the intended design is directionally correct:

- `with_instance=True` should produce `dofkey = parameters.input_ports.connected_outputs`.
- `instance = 6` is the input port index.
- `["out5"]` should parse to SNMP value `5`.
- The final OID should be `outputAllInChNr.6`.

### High: Invalid Requests Publish Failure, But Detailed Reasons Are Lost

Current code:

```python
except InvalidStateChange as e:
    self.result = str(e)
    logging.warning(self.result)
    return None, dofkey, dofval
```

This is a good pattern: custom validation returns `oid = None`, preserving the template failure path.

But `update_settings_on_device()` currently does this when `oid is None`:

```python
else:
    self.update_fail_set_info(i, incoming_msgdata)
    logging.info(f"dofkey {dofkey} NOT FOUND in list of settable DoF variables or is INVALID")
    self.result = "dofkey " + dofkey + " NOT FOUND in list of settable DoF variables or is INVALID"
```

Impact:

- The detailed validation reason is overwritten by generic text.
- `update_fail_set_info()` is called before `self.result` is updated.
- Fault logs are not written.

Required for the original request:

- Invalid requests must return `state_change_failure`.
- Invalid requests must include detailed fault/log messages.

Status:

- `STATE_CHANGE_FAILURE` will likely be published because `self.successful` remains false.
- Detailed reason handling is incomplete.

### High: `update_settings_on_device()` Still Does Not Return `self.result`

File:

```text
src/csi_quintech_rf_matrix/snmp_setter.py:462-527
```

`run()` does this:

```python
if session:
    self.result = self.update_settings_on_device(session, self.msgdata)
```

But `update_settings_on_device()` currently has no return statement.

Impact:

- After a session-backed set attempt, `self.result` becomes `None`.
- The success/failure publish still depends on `self.successful`, so state-change success/failure can still fire.
- But the published `msgdata['result']` can be `None`, which is not useful and can hide detailed failure reasons.

This is a small base-code change, but it is still needed for clean behavior:

```python
return self.result
```

at the end of `update_settings_on_device()`.

### High: Fault Log Entries Are Not Implemented For Validation Failures

Current failure helper:

```python
def update_fail_set_info(self, i, incoming_msgdata):
    self.current_settings['parameters']['ready'] = "READY"
    self.current_settings['log']['state'] = "HAS_ENTRIES"
    self.current_settings['log']['entries'] = {}
    self.current_settings['log']['entries'][f"{i}"] = {
        "index": f"{i}",
        "id": f"{uuid.uuid4()}",
        "timestamp": f"{time.time()}",
        "level": "ERROR",
        "description": f"SNMP Set Failure. Invalid command passed: {incoming_msgdata}."
    }
    CSI.update_settings(self.current_settings)
```

Missing:

- No `fault_log.entries[...]` is written.
- The detailed reason from `self.result` is not included.

This does not satisfy the original requirement:

```text
Add detailed fault log messages
```

### High: Multi-Output Route Warning Is Collected But Not Published

Current route parser stores warnings:

```python
self.validation_warnings.append(warning)
```

But `update_sucessful_set_info()` does not read `self.validation_warnings`.

Impact:

For:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5", "out7"]}}}}
```

the proxy is intended to select `out5` and log a warning. The warning currently goes to Python logging, but not to the CSI-visible log entry.

Required by `rules.txt`:

```text
If a user sends multiple outputs in the connected_outputs list, the proxy must select the first and log a warning.
```

Status:

- Selection logic is intended.
- CSI-visible warning log is missing.

### Medium: Mapping Is Functionally Mostly Correct, But Cleanup Is Incomplete

File:

```text
schemas/snmp_to_dof_mapping.yml
```

Good:

```yaml
outputAllInChNr:
  use_oid_index: true
  dof_name: parameters.input_ports.connected_outputs
  settable: true
```

Good:

```yaml
outputAllAGCMode:
  use_oid_index: true
  dof_name: proprietary_fields.output_ports.agc_enable
  settable: true
```

Good:

```yaml
inputAllRFLeveldBm:
  dof_name:
    proprietary_fields.input_ports.rf_level_dBm
```

Still incomplete:

```yaml
# dof_name: proprietary_fields.input_ports.routed_output
```

This stale comment should be removed to fully remove `routed_output` from source mappings.

Gain-limit mappings currently lack explicit `use_oid_index: false` and `settable: false`:

```yaml
sysInfoModulesMinEffectiveInputGain:
  dof_name:
    sensors.min_input_gain_dB
```

This is not a functional blocker in the current poller/setter:

- Poller treats missing `use_oid_index` as false.
- Setter only allows set when `settable: true`.

But the implementation plan explicitly called for adding these fields for clarity and to avoid ambiguity.

### Medium: Discover Schema Does Not Include Nested Proprietary Port Definitions

File:

```text
src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py:695-716
```

Current:

```python
discover_settings['properties']['proprietary_fields'] = discover_settings['definitions'].get('ProprietaryFields')
```

Missing from the implementation plan:

```python
discover_settings['properties']['proprietary_fields']['properties']['input_ports'] = discover_settings['definitions'].get('ProprietaryInputPort')
discover_settings['properties']['proprietary_fields']['properties']['output_ports'] = discover_settings['definitions'].get('ProprietaryOutputPort')
```

Impact:

- Runtime settings model has the proprietary fields.
- Discovery may not expose the nested proprietary input/output port schema as clearly as intended after `definitions` is deleted.

This is not the top runtime blocker, but it is incomplete relative to the implementation plan.

### Medium: AGC Poll Conversion May Be Too Narrow

Current poller logic:

```python
if oid == "outputAllAGCMode":
    if value == "0":
        value = "DISABLED"
    elif value == "1":
        value = "ENABLED"
```

Sample `snmpwalk.txt` shows:

```text
QEC-MATRIX-MIB::outputAllAGCMode.1 = INTEGER: manual(0)
```

Depending on what `easysnmp` returns, `value` may be `"0"`, `0`, or a display string such as `"manual(0)"`.

Status:

- If `easysnmp` returns `"0"` or `"1"`, current conversion works.
- If it returns integer `0`/`1` or enum display strings, the state can remain raw instead of `DISABLED`/`ENABLED`.

Recommended:

Make AGC poll conversion tolerate:

```text
0
"0"
"manual(0)"
1
"1"
"agc(1)"
```

### Medium: Port Index Validation Depends On Existing Polled State

Current validation:

```python
max_input = self.get_port_count('parameters', 'input_ports')
if max_input and (input_index < 1 or input_index > max_input):
    raise InvalidStateChange(...)
```

and:

```python
max_output = self.get_port_count('parameters', 'output_ports')
if max_output and (output_index < 1 or output_index > max_output):
    raise InvalidStateChange(...)
```

Impact:

- If `parameters.input_ports` and `parameters.output_ports` have been populated by a poll, validation is useful.
- If they are empty, `max_input` or `max_output` is `0`, and the range check is skipped.

This may be acceptable during initialization, but it is not a strict hardware-level port limit.

If the hardware is known to be 16x16 for this proxy, add a conservative fallback:

```python
max_input = self.get_port_count('parameters', 'input_ports') or 16
max_output = self.get_port_count('parameters', 'output_ports') or 16
```

Only do this if 16 is guaranteed for the target hardware variant.

### Medium: Output Gain Is Rejected When AGC State Is Unknown

Current logic:

```python
if agc_state == 'UNKNOWN':
    raise InvalidStateChange(
        f"Cannot set manual gain for output {instance} because output AGC state is unknown"
    )
```

This is conservative and safe. It prevents manual output gain changes until the proxy has polled the AGC state.

Tradeoff:

- Good: avoids setting output gain when the proxy cannot prove AGC is disabled.
- Cost: output gain can fail after startup before the first successful poll.

This is acceptable if the intended operator workflow is "poll first, then set."

### Low: `main.py` Adds Hardcoded Service Routes

File:

```text
src/csi_quintech_rf_matrix/main.py
```

New routes were added:

```python
@app.get("/service/quintech_rf_matrix/")
@app.get("/service/quintech_rf_matrix/discover")
@app.get("/service/quintech_rf_matrix/landing_page")
```

These routes are not part of the fan-in routing/range/AGC requirement. The hardcoded route name also differs from the configured service name:

```text
csi_quintech_rf_matrix_0
```

Impact:

- Probably not related to the core fan-in implementation.
- Could be confusing if Maestro expects service-name-specific paths.
- The `/discover` route returns `QuintechRFMatrixSettings().schema()` directly, not the customized `initialize_discover()` output.

Recommendation:

Do not spend time here until the setter compiles and the fan-in state-change behavior works.

## Requirement Coverage Matrix

### Device-Specific Schema

Status: mostly implemented.

Implemented:

- `field_version_function = "rf_matrix-2023.08.06"` at `quintech_rf_matrix_settings.py:523-532`.
- `parameters.matrix_type = FAN_IN` at lines 157-167.
- `parameters.input_ports[index].connected_outputs` at lines 87-96.
- `proprietary_fields.input_ports[index].rf_level_dBm` at lines 22-42.
- `proprietary_fields.output_ports[index].agc_enable` and `gain_db` at lines 44-55.
- Sensor gain limits at lines 186-209.

Missing:

- Nested proprietary discover definitions at `initialize_discover()`.

### Routing Logic

Status: partially implemented.

Implemented:

- Mapping uses `parameters.input_ports.connected_outputs`.
- Polling converts `outputAllInChNr` value to `["outN"]` or `[]`.
- Backend no longer has old output-indexed batch dispatch.

Not working yet:

- Setter conversion is blocked by the `snmp_setter.py` syntax error.

### `connected_outputs[]` Handling

Status: partially implemented.

Implemented in intended code:

- Empty list -> `0`.
- `["0"]` or `[""]` -> `0`.
- `["out5"]` -> `5`.
- Multiple outputs -> first selected and warning collected.

Missing:

- Syntax fix needed before any of this can run.
- CSI-visible warning log is missing.

### Range Validation

Status: partially implemented, currently blocked.

Implemented in intended code:

- Input gain converts to float.
- Input gain uses `sensors.min_input_gain_dB` and `sensors.max_input_gain_dB`.
- Output gain uses `sensors.min_output_gain_dB` and `sensors.max_output_gain_dB`.

Missing:

- Syntax fix required.
- Detailed fault log messages required.
- Strict port-count fallback if hardware size must be enforced before first poll.

### Output AGC Conflict Check

Status: partially implemented, currently blocked.

Implemented in intended code:

- Output manual gain checks `proprietary_fields.output_ports[index].agc_enable`.
- If AGC is `ENABLED`, output gain is rejected.
- If AGC state is `UNKNOWN`, output gain is rejected.

Missing:

- Syntax fix required.
- Detailed fault log messages required.

### `state_change_failure` On Invalid Requests

Status: partially implemented.

What should happen:

- `InvalidStateChange` is caught in `lookup_oid()`.
- `lookup_oid()` returns `oid = None`.
- Existing template flow publishes `STATE_CHANGE_FAILURE`.

What is incomplete:

- `self.result` is overwritten by generic text.
- `update_fail_set_info()` writes a generic log entry.
- No fault log entry is written.
- `update_settings_on_device()` does not return `self.result`.

### User-Facing State Reflects Hardware After Poll

Status: mostly implemented for routing.

Implemented:

- Polling `outputAllInChNr.6 = 3` should update:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out3"]}}}}
```

Potential issue:

- AGC poll conversion may need to support `manual(0)` / `agc(1)` or integer values, depending on `easysnmp`.

## Ordered Next Steps

1. Fix the indentation of `parse_connected_outputs_for_snmp()` in `snmp_setter.py`.
2. Run `python3 -m py_compile src/csi_quintech_rf_matrix/snmp_setter.py`.
3. Add `return self.result` at the end of `update_settings_on_device()`.
4. Change the `oid is None` branch so it preserves `self.result` if custom validation already populated it.
5. Move `self.result = "snmpset failed"` before `update_fail_set_info()` in the SNMP set failure branch.
6. Move `self.result = f"SNMP Set Failure: {e}"` before `update_fail_set_info()` in the exception branch.
7. Update `update_fail_set_info()` to include `self.result` in the log description.
8. Add a fault log entry in `update_fail_set_info()`.
9. Update `update_sucessful_set_info()` to include `self.validation_warnings` in the success log as a warning.
10. Remove the stale `routed_output` comment from `schemas/snmp_to_dof_mapping.yml`.
11. Add explicit `use_oid_index: false` and `settable: false` to the gain-limit mappings.
12. Add nested proprietary discover definitions in `initialize_discover()`.
13. Make `outputAllAGCMode` poll conversion tolerant of integer and enum-display values.
14. Decide whether to add a hard fallback port count, such as 16, for validation before first poll.
15. Re-run static checks.
16. Manually verify the routing, clearing, range, AGC conflict, and poll-reflection cases from the implementation plan.

## Current Completion Summary

Completed or mostly complete:

- Device-specific runtime settings model.
- Top-level RF Matrix function version.
- Active DoF route mapping.
- Active output AGC mapping.
- Poll-side route conversion.
- Removal of old proxy-backend output-indexed dispatch.

Incomplete:

- Setter syntax.
- Setter route conversion runtime behavior.
- Detailed validation result preservation.
- Fault log entries.
- CSI-visible multi-output warning logs.
- Mapping cleanup.
- Discover schema completeness.
- Robust AGC poll type conversion.

The immediate priority is fixing `snmp_setter.py` so the proxy can import. After that, focus on preserving validation reasons and adding fault log entries; those are the main gaps relative to the original request.
