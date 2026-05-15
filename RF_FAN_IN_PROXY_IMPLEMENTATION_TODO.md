# RF Fan-In Proxy Implementation To-Do

This document is an implementation-oriented to-do list for the Quintech RF fan-in proxy in:

```text
csi-pdk/csi_quintech_RF_Matrix/src/csi_quintech_rf_matrix
```

It uses the current fan-in code, the observed firmware behavior in `rules.txt`, the RF Matrix DoF reference in `dof-rf.txt`, the sample device walk in `snmpwalk.txt`, and lessons from the completed fan-out proxy analysis.

The central design rule for this proxy is:

```text
Firmware behavior is authoritative.
Routing is input-indexed:
    SNMP OID instance = input port index
    SNMP OID value    = output port index
```

Do not implement output-indexed routing semantics. Even when an OID name looks output-oriented, the implementation must treat it as input-indexed if it is used for routing.

## Current State Summary

The fan-in proxy is currently a partly customized SNMP template fork.

Already present:

- `parameters.matrix_type` defaults to `FAN_IN` in `quintech_rf_matrix_settings.py:144`.
- `parameters.input_ports[index].connected_outputs` is modeled as `List[str]` in `quintech_rf_matrix_settings.py:74`.
- Output AGC/gain have started moving to `proprietary_fields` in `quintech_rf_matrix_settings.py:22` and `quintech_rf_matrix_settings.py:35`.
- `snmp_setter.py` already has partial range validation for gain values in `snmp_setter.py:186`.
- `snmp_setter.py` already rejects output gain when output AGC is enabled in `snmp_setter.py:196`.
- `snmp_poller.py` already converts `outputAllAGCMode` SNMP values `0` and `1` into `DISABLED` and `ENABLED` in `snmp_poller.py:246`.

Major gaps:

- Routing is still mapped to `proprietary_fields.input_ports.routed_output` in `schemas/snmp_to_dof_mapping.yml:63`, not to DoF `parameters.input_ports.connected_outputs`.
- The `ProprietaryFields` schema only defines `output_ports`, but the mapping writes `proprietary_fields.input_ports.*` in `schemas/snmp_to_dof_mapping.yml:31` and `schemas/snmp_to_dof_mapping.yml:63`.
- `ProprietaryOutputPort` defines `agc_enable`, but the mapping uses `agc_mode` in `schemas/snmp_to_dof_mapping.yml:56`.
- Incoming DoF routing commands use arrays such as `["out5"]`, but the setter currently sends raw values to SNMP.
- Polling currently writes raw SNMP routing integers instead of DoF arrays like `["out5"]`.
- Invalid requests can raise inside the setter without reliably publishing `state_change_failure`.
- `SnmpSetter.run()` assigns `self.result = self.update_settings_on_device(...)`, but `update_settings_on_device()` does not return a value.
- Logs are cleared on each set success/failure instead of accumulating detailed diagnostic history.
- Fault-log entries for invalid user requests are not consistently created.
- The current tests under `src/test` still reference `src/csi_make_model`, so they are stale. Per `rules.txt`, do not create new test files as part of this plan; use manual verification unless that instruction changes.

## Source Anchors

Use these files and line ranges while implementing:

- Rules and design constraints: `rules.txt:3-27`, `rules.txt:33-52`
- RF Matrix DoF: `dof-rf.txt:43-49`, `dof-rf.txt:61-84`, `dof-rf.txt:96-119`
- Settings model: `src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py:22-83`, `:125-197`, `:499-576`
- Discover/schema setup: `src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py:671-693`
- Mapping file: `schemas/snmp_to_dof_mapping.yml:17-68`
- Poller read path: `src/csi_quintech_rf_matrix/snmp_poller.py:224-279`
- Poller DoF write helper: `src/csi_quintech_rf_matrix/snmp_poller.py:281-334`
- Setter lookup/validation path: `src/csi_quintech_rf_matrix/snmp_setter.py:147-212`
- Setter state update/set path: `src/csi_quintech_rf_matrix/snmp_setter.py:296-360`
- Setter log helpers: `src/csi_quintech_rf_matrix/snmp_setter.py:431-500`
- Backend state-change dispatch: `src/csi_quintech_rf_matrix/proxy_backend.py:303-438`
- Observed SNMP routing values: `snmpwalk.txt:98-113`, `snmpwalk.txt:194-209`, `snmpwalk.txt:290-305`

## Implementation Order

Implement in this order to keep the system coherent:

1. Fix the data model so the schema describes the fan-in proxy accurately.
2. Fix the SNMP-to-DoF mapping so routing lands in the standard DoF field.
3. Add routing conversion helpers in the setter.
4. Add routing conversion helpers in the poller.
5. Harden validation and failure handling so invalid requests always publish `state_change_failure`.
6. Improve log and fault-log behavior.
7. Review backend optimistic state behavior.
8. Manually verify with representative state-change messages and poll results.

## To-Do 1: Make The Settings Model Match The Fan-In Device

### Context

The settings model in `quintech_rf_matrix_settings.py` is what the proxy advertises through discovery and what clients expect to read from Redis. The DoF says `connected_outputs` is a list of output strings under:

```text
parameters.input_ports[index].connected_outputs
```

The current model already has `connected_outputs: List[str]` at `quintech_rf_matrix_settings.py:74`.

### Purpose

Make the schema explicit and truthful:

- Standard DoF fields go under `parameters` and `sensors`.
- Quintech-specific hardware fields that are not in the RF Matrix DoF go under `proprietary_fields`.
- The schema must not advertise fields that the setter cannot implement correctly.

### File Location

```text
src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py
```

Relevant current lines:

- `ProprietaryOutputPort`: lines 22-33
- `ProprietaryFields`: lines 35-36
- `ParamInputPorts`: lines 38-83
- `ParamOutputPorts`: lines 85-98
- `Parameters`: lines 125-157
- `Sensors`: lines 158-197
- `QuintechRFMatrixSettings`: lines 499-576

### Required Changes

- Keep `parameters.matrix_type` defaulting to `FAN_IN`.
- Keep `parameters.input_ports[index].connected_outputs` as `List[str]`.
- Add a top-level RF Matrix function version field:

```text
field_version_function = "rf_matrix-2023.08.06"
```

This is required by `dof-rf.txt:34`.

- Decide whether `parameters.input_ports[index].agc_enable` is actually implementable.
  - The DoF lists input AGC at `dof-rf.txt:65`.
  - The Quintech MIB exposes `outputAllAGCMode`, which is output-side hardware AGC.
  - Do not map output AGC into input AGC just to satisfy DoF if that would lie about hardware behavior.
  - Recommended: keep Quintech output AGC under `proprietary_fields.output_ports[index].agc_enable`.
  - If `parameters.input_ports[index].agc_enable` remains in the model, document it as unsupported unless a real input-side OID is found.

- Fix proprietary field coverage:
  - Current mapping writes `proprietary_fields.input_ports.rf_level_dbm`, but `ProprietaryFields` does not define `input_ports`.
  - Either add `ProprietaryInputPort` for RF level only, or stop mapping input RF level if it is not needed.
  - Do not use `proprietary_fields.input_ports.routed_output` for routing state. Routing belongs in `parameters.input_ports.connected_outputs`.

- Fix the AGC naming mismatch:
  - Model has `agc_enable`.
  - Mapping currently uses `agc_mode`.
  - Use one name. Recommended: `proprietary_fields.output_ports.agc_enable`, because the public DoF uses `agc_enable`.

- Consider adding output port index fields if useful for client clarity:
  - `parameters.output_ports[index].list_id` is present.
  - DoF does not require `index`, but many CSI proxies keep index fields for list display.
  - If added, keep it read-only.

### Design Notes

Pydantic schema validation is not enough for state-change requests. The proxy receives Redis messages as plain dicts, and the setter operates on those dicts. Therefore:

- Use Pydantic for discover/schema clarity.
- Use explicit runtime validation in `snmp_setter.py` for hardware safety.

## To-Do 2: Fix The SNMP-To-DoF Mapping

### Context

The mapping file is the bridge between SNMP OID names and DoF dotted paths. Current routing mapping is:

```yaml
outputAllInChNr:
  use_oid_index: true
  dof_name: proprietary_fields.input_ports.routed_output
  settable: true
```

That violates the user-facing DoF requirement in `rules.txt:4`.

### Purpose

Make routing poll and set paths target:

```text
parameters.input_ports[index].connected_outputs
```

### File Location

```text
schemas/snmp_to_dof_mapping.yml
```

Relevant current lines:

- Input field mappings: lines 17-35
- Output field mappings: lines 37-59
- Routing mapping: lines 61-66

### Required Changes

Update routing mapping to point at the standard DoF field:

```yaml
outputAllInChNr:
  use_oid_index: true
  dof_name:
    parameters.input_ports.connected_outputs
  settable: true
```

Important: even though the OID name is `outputAllInChNr`, the implementation must interpret `oid_index` as the input port index and value as the output port index, per `rules.txt:8-21`.

If device verification later proves `inputAllOutChNr` is the more reliable write OID, swap the OID name but keep the exact same semantics:

```text
instance = input port
value    = output port
```

Do not add an output-indexed routing write path.

Also update the AGC proprietary mapping:

```yaml
outputAllAGCMode:
  use_oid_index: true
  dof_name:
    proprietary_fields.output_ports.agc_enable
  settable: true
```

Add gain limit mappings so runtime validation can use hardware-polled values instead of hardcoded constants when available:

```yaml
sysInfoModulesMinEffectiveInputGain:
  dof_name:
    sensors.min_input_gain_dB

sysInfoModulesMaxEffectiveInputGain:
  dof_name:
    sensors.max_input_gain_dB

sysInfoModulesMinEffectiveOutputGain:
  dof_name:
    sensors.min_output_gain_dB

sysInfoModulesMaxEffectiveOutputGain:
  dof_name:
    sensors.max_output_gain_dB
```

These appear in `snmpwalk.txt:320-323`.

### Design Notes

Do not store routing twice unless there is a specific need. If you keep a proprietary route mirror for debugging, it must be derived from the same input-indexed source and never be the canonical user-facing state.

Canonical routing state:

```text
parameters.input_ports[input_idx].connected_outputs = ["outN"] or []
```

## To-Do 3: Add Routing Parse And Format Helpers In The Setter

### Context

The incoming command shape is:

```json
{
  "parameters": {
    "input_ports": {
      "6": {
        "connected_outputs": ["out5"]
      }
    }
  }
}
```

The hardware expects an integer SNMP value:

```text
outputAllInChNr.6 = 5
```

For clearing, `rules.txt:26` allows `connected_outputs` to be `"0"` or `""`.

### Purpose

Convert DoF routing arrays into SNMP integers before `session.set()`.

### File Location

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

Relevant current lines:

- `lookup_oid()`: lines 147-212
- Existing conversion logic: lines 180-202
- `update_settings_on_device()`: lines 296-360
- `convert_to_dotted_notation()`: lines 362-409

### Required Helper

Add a helper method to `SnmpSetter`, conceptually:

```text
parse_connected_outputs_for_snmp(dofval, input_idx, current_settings) -> tuple[int, list[str]]
```

Inputs:

- `dofval`: incoming value from `connected_outputs`
- `input_idx`: the input port index from the command path
- `current_settings`: current Redis settings

Return:

- `output_idx`: integer value to send to SNMP
- `warnings`: list of warning strings to log if the command is accepted with adjustment

Behavior:

- Accept `[]` as clear -> return `0`.
- Accept `""` as clear -> return `0`.
- Accept `"0"` as clear -> return `0`.
- Accept `[""]` as clear -> return `0`.
- Accept `["0"]` as clear -> return `0`.
- Accept `["out5"]` -> return `5`.
- Accept `"out5"` if you want to be tolerant, but the preferred DoF shape is list.
- If list length is greater than one, select the first element and append a warning:

```text
Fan-in limitation: input {input_idx} can connect to only one output. Selected first output {first}; ignored {rest}.
```

- Validate the output string with a strict format:

```text
^out([0-9]+)$
```

Use case-insensitive matching, but normalize state back to lowercase `outN`.

- Validate the parsed output index:
  - `1 <= output_idx <= output_count`
  - Derive `output_count` from `current_settings["parameters"]["output_ports"]` if populated.
  - If output ports are not populated yet, use the known Quintech 16-output device default only as a fallback.

- Reject invalid values by raising or returning a structured validation error that the caller converts into `state_change_failure`.

### Required Integration

In `lookup_oid()`, when:

```text
oid == "outputAllInChNr"
dofkey == "parameters.input_ports.connected_outputs"
```

call the helper and replace `dofval` with the integer SNMP value.

Do not append an output index instance. Append the input index instance:

```text
outputAllInChNr.{input_idx} = {output_idx}
```

### Examples

Accepted:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

SNMP:

```text
outputAllInChNr.6 = 5
```

Accepted with warning:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5", "out7"]}}}}
```

SNMP:

```text
outputAllInChNr.6 = 5
```

Log:

```text
WARNING: Fan-in limitation: selected first connected output out5 for input 6; ignored out7.
```

Accepted clear:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": []}}}}
```

SNMP:

```text
outputAllInChNr.6 = 0
```

Rejected:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["foo"]}}}}
```

Result:

```text
state_change_failure
no SNMP set
log/fault entry explains invalid connected_outputs value
```

## To-Do 4: Convert Routing Values During Polling

### Context

The poller reads SNMP integers and writes them into Redis. Today it only converts `outputAllAGCMode` values at `snmp_poller.py:246`.

The user-facing state after a poll must reflect hardware reality:

```text
SNMP outputAllInChNr.6 = 5
Redis parameters.input_ports["6"].connected_outputs = ["out5"]
```

### Purpose

Make the read path produce DoF-compliant routing arrays.

### File Location

```text
src/csi_quintech_rf_matrix/snmp_poller.py
```

Relevant current lines:

- `perform_poll()`: lines 224-252
- `update_setting_if_tracking()`: lines 256-279
- `dof_update()`: lines 281-334

### Required Helper

Add a helper method to `SnmpPoller`, conceptually:

```text
format_connected_outputs_from_snmp(value) -> list[str]
```

Behavior:

- `0`, `"0"`, empty, or invalid empty value -> `[]`
- positive integer `N` -> `[f"out{N}"]`
- if value is non-numeric, log warning and do not update the field, or set `[]` with a fault/log entry depending on desired strictness

### Required Integration

In `perform_poll()` or `update_setting_if_tracking()`, when OID is the routing OID:

```text
outputAllInChNr
```

convert raw SNMP integer to the DoF array before calling `dof_update()`.

Also ensure the mapping writes to:

```text
parameters.input_ports.connected_outputs
```

With `use_oid_index: true`, the poller will write:

```json
"parameters": {
  "input_ports": {
    "6": {
      "connected_outputs": ["out5"]
    }
  }
}
```

### Design Notes

The poller is the source-of-truth reconciliation mechanism. If a set command succeeds but the device normalizes or rejects the value in a way the setter did not catch, the next poll must overwrite Redis with the observed hardware state.

Do not leave routing under `proprietary_fields.input_ports.routed_output` as the only state. That would make GUI/automation clients read the wrong field.

## To-Do 5: Harden Gain Validation

### Context

Current setter validation at `snmp_setter.py:186-202`:

- Converts gain to `float`.
- Rejects gain outside `[-14.5, +17.0]`.
- Rejects output gain while output AGC is enabled.

This is a good start, but it needs to be systematic and must reliably return `state_change_failure` without sending SNMP.

### Purpose

Protect the hardware and return clear user feedback.

### File Location

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

Relevant current lines:

- Gain conversion: lines 186-194
- AGC conflict check: lines 196-202
- Failure update path: lines 351-360
- Failure log helper: lines 485-500

### Required Helper

Add a helper method to `SnmpSetter`, conceptually:

```text
validate_and_format_gain(oid, dofval, instance, current_settings) -> str
```

Behavior:

- Accept numbers or numeric strings.
- Reject non-numeric values.
- Use the correct range:
  - Input gain: `sensors.min_input_gain_dB` to `sensors.max_input_gain_dB`
  - Output gain: `sensors.min_output_gain_dB` to `sensors.max_output_gain_dB`
  - If sensors are absent, fall back to explicit constants:
    - input: `-14.5` to `17.0`
    - output: `-18.5` to `13.0`, based on `snmpwalk.txt:322-323`
- If hardware requires 0.5 dB steps, reject values not aligned to 0.5 increments.
- Format output as the SNMP string the device expects, e.g. `+3.5` or `-2.0`.

### AGC Conflict Validation

Reject manual gain changes when AGC is enabled.

Current output check reads:

```python
output_fields = self.current_settings.get('proprietary_fields', {}).get('output_ports', {})
port_data = output_fields.get(f'{instance}', {})
agc_state = port_data.get('agc_mode', 'DISABLED')
```

This needs to match the schema/mapping name. Recommended:

```text
proprietary_fields.output_ports[index].agc_enable
```

If you keep input AGC in `parameters.input_ports[index].agc_enable`, then input gain validation should check:

```text
parameters.input_ports[input_idx].agc_enable
```

But do not invent input AGC behavior if the hardware does not expose it.

### Failure Behavior

Invalid gain requests must:

- avoid `session.set()`
- set `self.successful = False`
- set a meaningful `self.result`
- update log and fault log with the exact reason
- publish `CSI.STATE_CHANGE_FAILURE`

Example failure result:

```text
Invalid gain for parameters.input_ports.6.gain_db: 22.0 exceeds hardware range -14.5 to 17.0.
```

## To-Do 6: Make Invalid Requests Publish `state_change_failure`

### Context

Currently, exceptions raised in `lookup_oid()` can escape before the failure path runs because `update_settings_on_device()` calls `lookup_oid()` before entering its `try` block at `snmp_setter.py:331`.

Also, `SnmpSetter.run()` assigns:

```python
self.result = self.update_settings_on_device(session, self.msgdata)
```

but `update_settings_on_device()` does not return a value.

### Purpose

Every invalid user request should result in a clean, visible CSI failure message.

### File Location

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

Relevant current lines:

- `run()`: lines 81-110
- `lookup_oid()`: lines 147-212
- `update_settings_on_device()`: lines 296-360

### Required Changes

- Wrap the full set operation in exception handling, including `lookup_oid()`.
- Make `update_settings_on_device()` return `self.result`.
- Or change `run()` so it calls `update_settings_on_device()` without overwriting `self.result` with `None`.
- Introduce a local validation exception type, e.g. `InvalidStateChange`, to distinguish user command failures from SNMP/session failures.
- Ensure invalid commands never call `session.set()`.
- Publish `STATE_CHANGE_FAILURE` for:
  - unknown DoF field
  - field not marked `settable: true`
  - invalid route format
  - output index out of range
  - input index out of range
  - invalid gain format
  - gain out of range
  - manual gain while AGC enabled
  - `session.set()` returns false
  - SNMP session creation fails

### Current Bug To Fix

Do not do this:

```python
self.result = self.update_settings_on_device(...)
```

unless `update_settings_on_device()` returns a string.

Otherwise successful/failed detailed results get overwritten with `None`.

## To-Do 7: Move Success Logging After Actual SNMP Success

### Context

`update_settings_on_device()` currently calls `update_sucessful_set_info()` before `session.set()` in `snmp_setter.py:329`.

That means the settings/log can say success before the hardware operation actually succeeds.

### Purpose

Keep the CSI state honest.

### File Location

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

Relevant current lines:

- Pre-set success info: line 329
- Actual SNMP set: line 334
- Success result: lines 343-349
- Failure path: lines 351-360

### Required Changes

Order should be:

1. Load current settings.
2. Parse and validate command.
3. If hardcoded local command, apply local mutation.
4. Else call `session.set(oid, dofval)`.
5. If `session.set()` returns true, record success.
6. If it returns false, record failure.
7. Publish result.
8. Start/restart poller.

Do not write a success log before step 5.

## To-Do 8: Add Detailed Log And Fault-Log Helpers

### Context

Current success/failure helpers clear previous logs:

- Success clears `log.entries` at `snmp_setter.py:481`.
- Failure clears `log.entries` at `snmp_setter.py:499`.
- `ProxyBackend.create_response()` also clears logs at `proxy_backend.py:286` and `proxy_backend.py:294`.

The user requested detailed fault log messages.

### Purpose

Keep useful diagnostic history, especially for rejected commands.

### File Locations

```text
src/csi_quintech_rf_matrix/snmp_setter.py
src/csi_quintech_rf_matrix/proxy_backend.py
```

Relevant current lines:

- Setter log helpers: `snmp_setter.py:455-500`
- Backend response helper: `proxy_backend.py:263-301`

### Required Helpers

Add helper functions in `snmp_setter.py`:

```text
next_entry_index(entries) -> str
append_log_entry(level, description, command=None)
append_fault_entry(description, command=None)
```

Behavior:

- Do not clear existing entries during normal success/failure logging.
- Set `log.state = "HAS_ENTRIES"` when adding log entries.
- Set `fault_log.entries` and `fault_log.state` if the fault schema is extended to include state.
- Include:
  - field path
  - input index
  - output index
  - requested value
  - normalized SNMP value
  - reason for rejection
  - original incoming command

Example invalid route fault:

```text
Rejected routing command for input 6: connected_outputs value "foo" is invalid. Expected ["outN"], [], "", or "0".
```

Example multi-output warning:

```text
Fan-in limitation: input 6 requested multiple connected_outputs ["out5", "out7"]; selected "out5" and ignored ["out7"].
```

### Log Versus Fault Log

Use:

- `log.entries` for all command outcomes and warnings.
- `fault_log.entries` for user-visible invalid command/fault conditions that should be surfaced as operational faults.

If the team wants fault_log only for hardware faults, keep invalid command details in `log.entries` but still make them detailed. The user asked for detailed fault log messages, so this plan assumes invalid state-change requests should create fault entries.

## To-Do 9: Keep Redis State Consistent With Hardware Reality

### Context

CSI clients read Redis state. The poller should reconcile Redis to actual hardware state.

The backend currently sets `parameters.ready = "HARDWARE_BUSY"` before dispatching a command at `proxy_backend.py:327`, then the setter sets ready back to `READY`.

### Purpose

Avoid stale or optimistic state, especially after failed writes.

### File Locations

```text
src/csi_quintech_rf_matrix/proxy_backend.py
src/csi_quintech_rf_matrix/snmp_setter.py
src/csi_quintech_rf_matrix/snmp_poller.py
```

Relevant lines:

- Backend state-change handling: `proxy_backend.py:303-438`
- Setter success/failure ready updates: `snmp_setter.py:466`, `snmp_setter.py:495`
- Poller DB update: `snmp_poller.py:101-104`

### Required Changes

- Do not merge requested routing values into settings as truth until either:
  - SNMP set succeeds, or
  - the next poll confirms the hardware state.

Current backend does not merge normal incoming settings directly, which is good. Keep it that way.

- After successful SNMP set, trigger a poll to read back the device.
- If a poll is already running, use `set_poll_again_flag()` or equivalent so a follow-up poll occurs.
- The final user-facing routing state should come from the poll:

```text
SNMP value 5 -> connected_outputs ["out5"]
SNMP value 0 -> connected_outputs []
```

- On failure, leave the last known good settings in place and add failure log/fault entries.

## To-Do 10: Make Routing Replacement Explicit

### Context

`rules.txt:25` says two separate sets for the same input must result in the second set replacing the first:

```text
input 6 connected_outputs ["out2"]
then input 6 connected_outputs ["out5"]
final state: ["out5"]
```

### Purpose

Make one input connect to only one output at a time.

### File Locations

```text
src/csi_quintech_rf_matrix/snmp_setter.py
src/csi_quintech_rf_matrix/snmp_poller.py
```

### Required Changes

- Do not append to an existing `connected_outputs` list.
- Setter should send only one integer output value for the input.
- Poller should overwrite the full list for that input with either:

```python
[]
```

or:

```python
[f"out{output_idx}"]
```

This guarantees replacement behavior after poll reconciliation.

## To-Do 11: Handle Clear Commands

### Context

`rules.txt:26` says clearing can be sent as `"0"` or `""`.

Since `connected_outputs` is a list, also support empty list forms.

### Purpose

Let clients disconnect an input from any output.

### File Locations

```text
src/csi_quintech_rf_matrix/snmp_setter.py
src/csi_quintech_rf_matrix/snmp_poller.py
```

### Required Behavior

Setter accepted clear values:

- `[]`
- `""`
- `"0"`
- `[""]`
- `["0"]`

All convert to:

```text
SNMP value 0
```

Poller readback:

```text
SNMP value 0 -> connected_outputs []
```

Reject ambiguous values:

- `None`, unless you explicitly decide to treat it as clear.
- `["out0"]`, because DoF output labels should be `outX` for real output ports and clearing should use `0`, `""`, or empty list.

## To-Do 12: Type Matching And Conversion

### Context

SNMP values arrive as strings from `easysnmp`, even when MIB syntax is integer. DoF values are strings, floats, lists, and enums.

### Purpose

Prevent accidental type drift in Redis and invalid SNMP writes.

### File Locations

```text
src/csi_quintech_rf_matrix/snmp_poller.py
src/csi_quintech_rf_matrix/snmp_setter.py
schemas/snmp_to_dof_mapping.yml
```

### Required Conversions

Poller:

- `outputAllAGCMode`: `0 -> DISABLED`, `1 -> ENABLED`
- routing OID: `0 -> []`, `N -> ["outN"]`
- gain strings: preserve as numeric-compatible values, ideally `float` in Redis if the Pydantic schema says float
- output RF level: keep as string or convert to float; align with schema type
- temperature: currently `Sensors.temperature_C` is `str`; consider changing to `int` or `float` if clients expect numeric

Setter:

- `DISABLED -> 0`, `ENABLED -> 1` for `outputAllAGCMode`
- `["outN"] -> N` for routing
- clear values -> `0`
- gain numeric value -> signed SNMP string

### Design Note

Avoid leaving SNMP integer strings like `"5"` in DoF list fields. The public DoF should contain `["out5"]`, not `["5"]`, `5`, or `"5"`.

## To-Do 13: Fix Discover Schema For Nested Proprietary Fields

### Context

`initialize_discover()` manually rewrites pieces of the Pydantic schema at `quintech_rf_matrix_settings.py:671-693`.

It currently sets:

```python
discover_settings['properties']['proprietary_fields'] = discover_settings['definitions'].get('ProprietaryFields')
```

But nested proprietary port definitions may not be fully expanded.

### Purpose

Make `/discover` accurate for GUI and automation clients.

### File Location

```text
src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py
```

Relevant current lines:

- `initialize_discover()`: lines 671-693

### Required Changes

- Ensure `proprietary_fields.output_ports` references `ProprietaryOutputPort`.
- If you add `ProprietaryInputPort`, ensure `proprietary_fields.input_ports` references it.
- Ensure `parameters.input_ports` references `ParamInputPorts`.
- Ensure `parameters.output_ports` references `ParamOutputPorts`.
- Ensure `sensors.output_ports` references `SensorOutputPorts`.
- Check that `field_version_function` appears in the discover output.

## To-Do 14: Update Reflector/Mock Behavior

### Context

Reflector mode is used when `debug_mode` includes `REFLECTOR`. Mock behavior lives in `quintech_rf_matrix_mocker.py`.

Current mock session set still checks `exampleMIB` at `quintech_rf_matrix_mocker.py:145`, which is not relevant to Quintech routing.

### Purpose

Keep reflector mode useful for fan-in behavior.

### File Location

```text
src/csi_quintech_rf_matrix/quintech_rf_matrix_mocker.py
```

Relevant current lines:

- Mock setter: lines 83-125
- Mock session set: lines 127-152

### Required Changes

- Update reflector sample settings to include:
  - `matrix_type: FAN_IN`
  - 16 input ports
  - 16 output ports
  - `connected_outputs` as lists
  - proprietary output AGC/gain if retained
  - sensor output power values
- Update mock SNMP set acceptance for:
  - `outputAllInChNr.{input_idx}` with integer values `0..16`
  - `inputAllGain.{input_idx}` with valid gain strings
  - `outputAllAGCMode.{output_idx}` values `0` or `1`
  - `outputAllGain.{output_idx}` if retained
- Fix `debug_logger()` if used; it references `wraps` but does not import it.

Do not develop new test files as part of this task, per `rules.txt:48`.

## To-Do 15: Fix Stale Test Import Paths Only If You Are Asked To Touch Tests

### Context

The current test files:

- `src/test/test_snmp_setter_quintech_rf_matrix.py`
- `src/test/test_snmp_poller_quintech_rf_matrix.py`

still append:

```text
src/csi_make_model
```

That path does not match this project.

### Purpose

The tests are currently not reliable evidence for this proxy.

### Required Action

Do not create or edit test files unless the instruction changes. For this implementation plan, use manual verification.

If test work is later allowed, update imports to:

```text
src/csi_quintech_rf_matrix
```

and add cases for routing conversion, gain validation, AGC conflicts, and failure publishing.

## To-Do 16: Manual Verification Checklist

Do this after implementation. These are manual checks, not new test files.

### Startup

- Start proxy with `debug_mode: ['OFF']`.
- Confirm `/service/csi_quintech_rf_matrix_0/settings` exists in Redis.
- Confirm `parameters.matrix_type` is `FAN_IN`.
- Confirm `field_version_function` is `rf_matrix-2023.08.06`.
- Confirm discover advertises `parameters.input_ports.connected_outputs` as list of strings.

### Poll Conversion

Use observed sample behavior:

```text
outputAllInChNr.6 = 3
```

Expected Redis:

```json
{
  "parameters": {
    "input_ports": {
      "6": {
        "connected_outputs": ["out3"]
      }
    }
  }
}
```

For SNMP value `0`, expected:

```json
"connected_outputs": []
```

### Set Route

Command:

```json
{
  "parameters": {
    "input_ports": {
      "6": {
        "connected_outputs": ["out5"]
      }
    }
  }
}
```

Expected SNMP:

```text
outputAllInChNr.6 = 5
```

Expected result:

```text
state_change_success
poll readback shows ["out5"]
```

### Replace Route

First:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out2"]}}}}
```

Then:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

Expected final Redis:

```json
{"connected_outputs": ["out5"]}
```

### Multiple Outputs In Fan-In

Command:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5", "out7"]}}}}
```

Expected:

- SNMP sends only `5`.
- `state_change_success`, because rule says select first and log warning.
- Log entry says `out7` was ignored.
- Poll readback shows `["out5"]`.

### Clear Route

Commands to verify:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": []}}}}
{"parameters": {"input_ports": {"6": {"connected_outputs": ""}}}}
{"parameters": {"input_ports": {"6": {"connected_outputs": "0"}}}}
```

Expected SNMP:

```text
outputAllInChNr.6 = 0
```

Expected Redis after poll:

```json
{"connected_outputs": []}
```

### Invalid Route

Command:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["bad"]}}}}
```

Expected:

- no SNMP set
- `state_change_failure`
- detailed log/fault entry
- Redis keeps last known good hardware state

### Gain Out Of Range

Command:

```json
{"parameters": {"input_ports": {"6": {"gain_db": 22.0}}}}
```

Expected:

- no SNMP set
- `state_change_failure`
- log/fault says gain exceeds `-14.5` to `17.0`

### Manual Gain While AGC Enabled

Precondition:

```json
"proprietary_fields": {
  "output_ports": {
    "2": {
      "agc_enable": "ENABLED"
    }
  }
}
```

Command:

```json
{"proprietary_fields": {"output_ports": {"2": {"gain_db": 3.0}}}}
```

Expected:

- no SNMP set
- `state_change_failure`
- log/fault explains manual gain is blocked while AGC is enabled

## Execution Walkthrough After Implementation

### Startup

1. `main.py` imports `QuintechRFMatrixSettings` and starts `proxy_backend_start()`.
2. `ProxyBackend.__init__()` calls `QuintechRFMatrixSettings.initialize_database()`.
3. `initialize_settings()` creates the default DoF-shaped settings document:
   - common service metadata
   - `field_version_function`
   - `parameters.matrix_type = FAN_IN`
   - empty input/output port dictionaries
   - sensors
   - proprietary fields
   - logs/faults
4. The proxy initializes comms from `csi_properties.yml`.
5. `ProxyBackend.run()` subscribes to `/state-change-request`.
6. It schedules heartbeat, keepalive, and polling.

### Poll Path

1. `restart_snmp_poller()` creates/updates `SNMPConfig`.
2. `SnmpPoller` creates an `easysnmp.Session`.
3. `perform_poll()` walks the configured OIDs.
4. For each returned OID:
   - `outputAllAGCMode` is converted to `DISABLED` or `ENABLED`.
   - routing OID values are converted from SNMP integer to DoF list:
     - `0 -> []`
     - `5 -> ["out5"]`
   - gain limits and telemetry are written to the configured fields.
5. `dof_update()` writes values into `current_settings`.
6. `CSI.update_settings()` writes Redis.
7. `CSI.SNMP_POLL_SUCCESSFUL` is published.
8. This poll result is the authoritative user-facing hardware state.

### Set Route Path

1. Client publishes state-change request:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

2. `ProxyBackend.handle_state_change()` marks hardware busy and dispatches to `perform_snmp_set()`.
3. `SnmpSetter.run()` creates an SNMP write session.
4. `update_settings_on_device()` loads current settings.
5. `lookup_oid()` converts nested dict to:

```text
dofkey = parameters.input_ports.connected_outputs
instance = 6
dofval = ["out5"]
```

6. Mapping finds routing OID:

```text
outputAllInChNr
```

7. Routing helper converts:

```text
["out5"] -> 5
```

8. Setter calls:

```text
session.set("outputAllInChNr.6", 5)
```

9. If successful:
   - append success log
   - publish `state_change_success`
   - restart or queue poller
10. Poller reads back hardware and writes:

```json
"connected_outputs": ["out5"]
```

### Set Failure Path

1. Client sends invalid command:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["bad"]}}}}
```

2. Routing helper rejects the value before SNMP set.
3. Setter records:
   - `self.successful = False`
   - detailed `self.result`
   - log entry
   - fault entry
4. Setter publishes:

```text
state_change_failure
```

5. No SNMP set is sent.
6. Last known good Redis state remains until future poll.

## Final Priority Checklist

Highest priority:

- [ ] Change routing mapping to `parameters.input_ports.connected_outputs`.
- [ ] Add setter conversion `["outN"] -> N`.
- [ ] Add poller conversion `N -> ["outN"]`, `0 -> []`.
- [ ] Ensure all routing is input-indexed: instance is input, value is output.
- [ ] Implement clear behavior for `[]`, `""`, `"0"`, `[""]`, and `["0"]`.
- [ ] Select first output and log warning when multiple outputs are requested.
- [ ] Reject malformed output labels with `state_change_failure`.
- [ ] Reject out-of-range input/output indexes with `state_change_failure`.
- [ ] Make validation exceptions publish `state_change_failure`.
- [ ] Fix `update_settings_on_device()` result handling.
- [ ] Move success logging after actual SNMP success.
- [ ] Stop clearing old log entries on every command.
- [ ] Add detailed log/fault entries for invalid commands.

Schema/mapping priority:

- [ ] Add `field_version_function = "rf_matrix-2023.08.06"`.
- [ ] Fix `proprietary_fields.output_ports.agc_enable` naming mismatch.
- [ ] Add or remove `proprietary_fields.input_ports` so mapping and schema agree.
- [ ] Keep output AGC/gain in `proprietary_fields` unless a true DoF input-side hardware mapping exists.
- [ ] Add gain limit OID mappings to sensors.
- [ ] Confirm discover output includes nested proprietary field definitions.

Validation priority:

- [ ] Validate input gain range.
- [ ] Validate output gain range if output gain remains settable.
- [ ] Validate 0.5 dB increments if required by hardware.
- [ ] Reject manual gain changes while relevant AGC mode is enabled.
- [ ] Include exact reason in failure result and logs.

Runtime consistency priority:

- [ ] Ensure successful set triggers poll/readback.
- [ ] Ensure failed set does not overwrite Redis with requested state.
- [ ] Ensure poll result overwrites stale routing state.
- [ ] Ensure `parameters.ready` transitions back to `READY` after success and failure.

Manual verification priority:

- [ ] Verify startup settings.
- [ ] Verify discover schema.
- [ ] Verify poll conversion for route `0`.
- [ ] Verify poll conversion for route `N`.
- [ ] Verify set route `["out5"]`.
- [ ] Verify replace route `["out2"]` then `["out5"]`.
- [ ] Verify multi-output warning and first-selection behavior.
- [ ] Verify clear commands.
- [ ] Verify invalid route failure.
- [ ] Verify gain out-of-range failure.
- [ ] Verify manual gain while AGC enabled failure.

