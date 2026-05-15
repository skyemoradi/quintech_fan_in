# RF Fan-In Proxy Implementation Plan

This is the corrected implementation plan for the current code in:

```text
csi-pdk/csi_quintech_RF_Matrix/src/csi_quintech_rf_matrix
```

It follows:

```text
csi-pdk/csi_quintech_RF_Matrix/rules.txt
```

Important correction: an earlier draft of this document quoted stale/template-shaped snippets for `quintech_rf_matrix_settings.py`. This version is based on the live files currently on disk. Line numbers below refer to the current working copy at the time this corrected plan was written.

For this plan, the source of truth is the current RF Fan-In proxy in this directory. The SNMP template and RF fan-out proxy are references only; they are not treated as authoritative when they conflict with the live fan-in files.

## Answers To Your Questions

### Do we need to aggregate `outputAllInChNr` during polling?

No, not into a multi-output list.

The updated rules say the route OIDs are input-indexed:

```text
outputAllInChNr.<input_index> = <output_index>
```

So this hardware value:

```text
outputAllInChNr.6 = 5
```

should become:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

If the hardware value is `0`, empty, or invalid, poll it as:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": []}}}}
```

Do not collect multiple output rows into one input's `connected_outputs`. The rules also say that if the user sends multiple connected outputs in one command, this proxy selects the first and logs a warning. That means the model is effectively zero-or-one connected output per input.

### Should `proprietary_fields.input_ports.routed_output` exist?

No.

Your current `quintech_rf_matrix_settings.py` does not define it. Keep it that way. Fully removing it means only deleting the stale commented mapping from `schemas/snmp_to_dof_mapping.yml`.

The canonical route state should be:

```text
parameters.input_ports[index].connected_outputs
```

Do not add:

```text
proprietary_fields.input_ports[index].routed_output
```

because it duplicates the same route in a second shape and can drift from `connected_outputs`.

### Do we need the fan-out proxy's `SessionIDResponse` fields?

No, not for this fan-in SNMP set flow.

Your current `proxy_backend.py` has commented response/session ID code in `create_response()`:

```python
#current_settings['response'].update({"response_type": "NEW_SESSION", "session_id": f"{sessionID}"})
#current_settings['session_id'] = f"{sessionID}"
```

That is different from needing a `SessionIDResponse` model. Normal SNMP sets are published by `SnmpSetter.run()` as `STATE_CHANGE_SUCCESS` or `STATE_CHANGE_FAILURE`. Do not copy fan-out session response fields unless an external CSI integration specifically requires them.

## Target State Shape

Keep the fan-in matrix schema focused on one representation per hardware concept:

```text
field_version_common
field_version_function
description
service_id
service_name
services
capabilities
parameters.ready
parameters.input_ports[index].list_id
parameters.input_ports[index].gain_db
parameters.input_ports[index].connected_outputs
parameters.output_ports[index].list_id
proprietary_fields.input_ports[index].list_id
proprietary_fields.input_ports[index].rf_level_dBm
proprietary_fields.output_ports[index].agc_enable
proprietary_fields.output_ports[index].gain_db
sensors.temperature_C
sensors.min_input_gain_dB
sensors.max_input_gain_dB
sensors.min_output_gain_dB
sensors.max_output_gain_dB
sensors.output_ports[index].output_power_dBm
log.entries[index]
fault_log.entries[index]
```

Do not add active fields for:

```text
proprietary_fields.input_ports[index].routed_output
parameters.input_ports[index].agc_enable
parameters.input_ports[index].agc_output_level_dbm
```

The DoF input-side AGC fields do not match the current Quintech MIB field you identified. `outputAllAGCMode` is output-side AGC and should stay under `proprietary_fields.output_ports[index].agc_enable`.

## Step 1: Verify Settings Schema And Fix Discover

### File

```text
src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py
```

### Location

Current schema classes are at lines 22-59. `QuintechRFMatrixSettings` begins at line 512. `initialize_discover()` is at lines 695-716.

### Current Code Context

Your current `ProprietaryInputPort` already has no `routed_output` field:

```python
class ProprietaryInputPort(BaseModel):
    list_id: str = Field(
        None,
        description='User-friendly label assigned to the input port',
        title='Input port name',
        readOnly=False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    rf_level_dBm: float | None = Field(
        None,
        description='Measured RF level at the input port in dBm',
        title='Input RF Level (dBm)',
        readOnly=True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class ProprietaryOutputPort(BaseModel):
    agc_enable: str | None = Field(
          None,
          description="Quintech output AGC mode",
          enum=["DISABLED", "ENABLED"],
          readOnly=False,
    )
```

Do not rename `rf_level_dBm`. The current mapping also uses `rf_level_dBm`, so schema and mapping agree.

### Function Version Context

The function version is already top-level on `QuintechRFMatrixSettings`. It is not under `service_name`.

Current lines around it:

```python
class QuintechRFMatrixSettings(BaseModel):
    field_version_common: str = Field(
        default= 'common-2022.10.07',
        description= 'This object is the version that specifies the schema for the common fields.',
        title= 'Field Version',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    field_version_function: str = Field(
          default='rf_matrix-2023.08.06',
          description='This object specifies the RF Matrix function field version.',
          title='RF Matrix Field Version',
          readOnly=True,
          json_schema_extra={
              "ADMINISTRATOR": ["READ"],
              "SYSTEMOPERATOR": ["READ"]
          },
      )
    description: str = Field(
        default= '',
        description= 'Description of the microservice.',
        title= 'Description',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
```

No change is needed for `field_version_function`.

### Actual Settings Change Needed

`initialize_discover()` currently defines top-level `proprietary_fields`, but it does not attach the nested `ProprietaryInputPort` and `ProprietaryOutputPort` definitions. Add those so discover accurately describes the custom fan-in proprietary fields.

This follows the current local discover pattern used for `parameters.input_ports` and `parameters.output_ports` at lines 709-710. The codebase is flattening indexed dict item schemas into the discover document rather than leaving `$ref` entries that will be deleted at line 714.

### Change Type

MODIFY.

### Replace This

```python
        discover_settings['properties']['parameters'] = discover_settings['definitions'].get('Parameters')
        discover_settings['properties']['parameters']['properties']['input_ports'] = discover_settings['definitions'].get('ParamInputPorts')               
        discover_settings['properties']['parameters']['properties']['output_ports'] = discover_settings['definitions'].get('ParamOutputPorts')
        discover_settings['properties']['sensors']['properties']['output_ports'] = discover_settings['definitions'].get('SensorOutputPorts')
        discover_settings['properties']['proprietary_fields'] = discover_settings['definitions'].get('ProprietaryFields')
        
        del discover_settings['definitions']
```

### With This

```python
        discover_settings['properties']['parameters'] = discover_settings['definitions'].get('Parameters')
        discover_settings['properties']['parameters']['properties']['input_ports'] = discover_settings['definitions'].get('ParamInputPorts')               
        discover_settings['properties']['parameters']['properties']['output_ports'] = discover_settings['definitions'].get('ParamOutputPorts')
        discover_settings['properties']['sensors']['properties']['output_ports'] = discover_settings['definitions'].get('SensorOutputPorts')
        discover_settings['properties']['proprietary_fields'] = discover_settings['definitions'].get('ProprietaryFields')
        discover_settings['properties']['proprietary_fields']['properties']['input_ports'] = discover_settings['definitions'].get('ProprietaryInputPort')
        discover_settings['properties']['proprietary_fields']['properties']['output_ports'] = discover_settings['definitions'].get('ProprietaryOutputPort')
        
        del discover_settings['definitions']
```

### Why

The runtime settings model already has the proprietary field classes. This discover change makes the published schema match the runtime model.

## Step 2: Clean The Mapping Without Changing The Good Parts

### File

```text
schemas/snmp_to_dof_mapping.yml
```

### Location

Edit the routing/gain-limit area at lines 61-87.

### Current Code Context

Current routing mapping:

```yaml
  # Routing
  #index=input_port, value = output_port
  outputAllInChNr:
    use_oid_index: true
    # dof_name: proprietary_fields.input_ports.routed_output
    dof_name: parameters.input_ports.connected_outputs
    settable: true

#Gain limit mappings 
  sysInfoModulesMinEffectiveInputGain:
    dof_name:
      sensors.min_input_gain_dB
```

### Change Type

MODIFY.

### Replace This

```yaml
  # Routing
  #index=input_port, value = output_port
  outputAllInChNr:
    use_oid_index: true
    # dof_name: proprietary_fields.input_ports.routed_output
    dof_name: parameters.input_ports.connected_outputs
    settable: true

#Gain limit mappings 
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

polled_oids:
```

### With This

```yaml
  # Routing
  # index=input_port, value=output_port
  outputAllInChNr:
    use_oid_index: true
    dof_name: parameters.input_ports.connected_outputs
    settable: true

  # Gain limit mappings
  sysInfoModulesMinEffectiveInputGain:
    dof_name:
      sensors.min_input_gain_dB
    use_oid_index: false
    settable: false

  sysInfoModulesMaxEffectiveInputGain:
    dof_name:
      sensors.max_input_gain_dB
    use_oid_index: false
    settable: false

  sysInfoModulesMinEffectiveOutputGain:
    dof_name:
      sensors.min_output_gain_dB
    use_oid_index: false
    settable: false

  sysInfoModulesMaxEffectiveOutputGain:
    dof_name:
      sensors.max_output_gain_dB
    use_oid_index: false
    settable: false

polled_oids:
```

### Why

The mapping should not suggest `routed_output` as an alternative implementation. Keep `parameters.input_ports.connected_outputs` as the only mapped route field.

The gain limit OIDs are already indented under `properties` because the OID keys have two spaces. The zero-indent comment is ugly but not fatal. This change makes the YAML clearer and makes the non-settable behavior explicit for the gain-limit sensor OIDs.

## Step 3: Finish Polling Conversion For Routes

### File

```text
src/csi_quintech_rf_matrix/snmp_poller.py
```

### Location

Edit `perform_poll()` at lines 241-252 and the existing route helper at lines 254-264.

### Current Code Context

Your poller already has a helper, but `perform_poll()` does not call it:

```python
        for item in snmp_results:
            oid = item.oid
            oid_index = item.oid_index
            snmp_type = item.snmp_type
            value = item.value
            # Converting int to string for the DoF
            if oid == "outputAllAGCMode":
                if value == "0":
                    value = "DISABLED"
                elif value == "1":
                    value = "ENABLED"
            self.update_setting_if_tracking(oid, oid_index, snmp_type, value)

    def format_connected_outputs_from_snmp(self, value):
        try:
            output_index = int(value)
        except (TypeError, ValueError):
            logging.warning(f"Invalid outputAllInChrNr value from SNMP: {value}")
            return []
            
        if output_index <= 0:
            return []
        
        return [f"out{output_index}"]
```

### Change Type

MODIFY.

### Replace This

```python
            # Converting int to string for the DoF
            if oid == "outputAllAGCMode":
                if value == "0":
                    value = "DISABLED"
                elif value == "1":
                    value = "ENABLED"
            self.update_setting_if_tracking(oid, oid_index, snmp_type, value)
```

### With This

```python
            # Converting SNMP-native values to DoF-native values
            if oid == "outputAllAGCMode":
                if value == "0":
                    value = "DISABLED"
                elif value == "1":
                    value = "ENABLED"
            elif oid == "outputAllInChNr":
                value = self.format_connected_outputs_from_snmp(value)
            self.update_setting_if_tracking(oid, oid_index, snmp_type, value)
```

### Also Replace This Typo

```python
            logging.warning(f"Invalid outputAllInChrNr value from SNMP: {value}")
```

with:

```python
            logging.warning(f"Invalid outputAllInChNr value from SNMP: {value}")
```

### Why

Without this change, polling writes the raw integer route value into a field that the DoF expects to be a list of strings.

Execution path:

```text
session.walk()
-> perform_poll()
-> outputAllInChNr value converted from "5" to ["out5"]
-> update_setting_if_tracking()
-> dof_update("parameters.input_ports.connected_outputs", ["out5"], "6")
```

## Step 4: Add Setter Imports And Validation Exception

### File

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

### Location

Edit imports at lines 10-14 and add `InvalidStateChange` after `CSI = CSI_Properties("csi_properties.yml")` at line 21.

### Current Code Context

Current imports and CSI initialization:

```python
import threading
import logging
import time
import yaml
import uuid
from csi_properties import CSI_Properties
from snmp_config import SNMPConfig
from snmp_poller import restart_snmp_poller

from easysnmp import Session

CSI = CSI_Properties("csi_properties.yml")

def perform_snmp_set(msgdata, proxycfg: SNMPConfig):
```

### Change Type

MODIFY/ADD.

### Replace This

```python
import threading
import logging
import time
import yaml
import uuid
```

### With This

```python
import threading
import logging
import re #********
import time
import yaml
import uuid
```

### Replace This

```python
CSI = CSI_Properties("csi_properties.yml")

def perform_snmp_set(msgdata, proxycfg: SNMPConfig):
```

### With This

```python
CSI = CSI_Properties("csi_properties.yml")


class InvalidStateChange(Exception):
    pass


def perform_snmp_set(msgdata, proxycfg: SNMPConfig):
```

### Why

Use `InvalidStateChange` for expected user-request failures. These should become `STATE_CHANGE_FAILURE`, not uncaught thread exceptions.

### Also Add A Warning Accumulator

Current `__init__()` state fields are:

```python
        self.result = 'undiagnosed failure'
        # self.successful refers to whether or not the SNMP Set was successful
        self.successful = False
```

Replace them with:

```python
        self.result = 'undiagnosed failure'
        # self.successful refers to whether or not the SNMP Set was successful
        self.successful = False
        self.validation_warnings = []
```

The setter needs this because a multi-output route command is still a successful command, but the proxy must preserve a visible warning that only the first output was used.

## Step 5: Add Device-Specific Setter Helpers

### File

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

### Location

Add these methods inside `class SnmpSetter`, immediately before the current `lookup_oid()` method.

Current line location: add after `create_session()` returns at line 145 and before `lookup_oid()` begins at line 147.

Current anchor:

```python
    def create_session(self, hostname, community, version, write_auth_pass, write_priv_pass):
        ...
        logging.debug(f'Created SNMP session with {hostname}, {community}, and {version}')
        return session

    def lookup_oid(self, incoming_msgdata, with_instance=False):
```

### Change Type

ADD.

### Add This

```python
    def get_indexed_section(self, *path):
        node = self.current_settings
        for key in path:
            if not isinstance(node, dict):
                return {}
            node = node.get(key, {})
        return node if isinstance(node, dict) else {}

    def get_port_count(self, *path):
        section = self.get_indexed_section(*path)
        numeric_keys = []
        for key in section.keys():
            try:
                numeric_keys.append(int(key))
            except (TypeError, ValueError):
                continue
        return max(numeric_keys) if numeric_keys else 0

    def validate_input_index(self, instance):
        try:
            input_index = int(instance)
        except (TypeError, ValueError):
            raise InvalidStateChange(f"Invalid input port index '{instance}'")

        max_input = self.get_port_count('parameters', 'input_ports')
        if max_input and (input_index < 1 or input_index > max_input):
            raise InvalidStateChange(f"Input port index {input_index} is outside available range 1-{max_input}")

        return input_index

    def validate_output_index(self, instance):
        try:
            output_index = int(instance)
        except (TypeError, ValueError):
            raise InvalidStateChange(f"Invalid output port index '{instance}'")

        max_output = self.get_port_count('parameters', 'output_ports')
        if max_output and (output_index < 1 or output_index > max_output):
            raise InvalidStateChange(f"Output port index {output_index} is outside available range 1-{max_output}")

        return output_index

    def parse_connected_outputs_for_snmp(self, dofval, instance):
        input_index = self.validate_input_index(instance)

        if isinstance(dofval, list):
            requested_outputs = dofval
        else:
            requested_outputs = [dofval]

        warnings = []
        if len(requested_outputs) == 0:
            return 0, warnings

        first_output = requested_outputs[0]
        first_output_text = "" if first_output is None else str(first_output).strip().lower()

        if len(requested_outputs) > 1:
            warnings.append(
                f"Input {input_index} requested multiple connected_outputs {requested_outputs}; using first value '{first_output}'"
            )

        if first_output_text in ("", "0"):
            return 0, warnings

        match = re.fullmatch(r"out([1-9][0-9]*)", first_output_text)
        if not match:
            raise InvalidStateChange(
                f"Invalid connected_outputs value '{first_output}' for input {input_index}; expected labels like 'out5'"
            )

        output_index = int(match.group(1))
        self.validate_output_index(output_index)
        return output_index, warnings

    def get_numeric_setting(self, default_value, *path):
        node = self.current_settings
        for key in path:
            if not isinstance(node, dict):
                return default_value
            node = node.get(key)
        try:
            return float(node)
        except (TypeError, ValueError):
            return default_value

    def get_output_agc_state(self, instance):
        output_ports = self.get_indexed_section('proprietary_fields', 'output_ports')
        output_port = output_ports.get(str(instance), {})
        if not isinstance(output_port, dict):
            return "UNKNOWN"
        agc_state = output_port.get('agc_enable')
        if agc_state is None:
            return "UNKNOWN"
        return str(agc_state).upper()

    def validate_gain_for_snmp(self, oid, dofval, instance):
        try:
            gain = float(dofval)
        except (TypeError, ValueError):
            raise InvalidStateChange(f"Invalid gain value '{dofval}' for {oid}.{instance}")

        if oid == 'inputAllGain':
            self.validate_input_index(instance)
            minimum = self.get_numeric_setting(-14.5, 'sensors', 'min_input_gain_dB')
            maximum = self.get_numeric_setting(17.0, 'sensors', 'max_input_gain_dB')
            port_label = f"input {instance}"
        elif oid == 'outputAllGain':
            self.validate_output_index(instance)
            minimum = self.get_numeric_setting(-18.5, 'sensors', 'min_output_gain_dB')
            maximum = self.get_numeric_setting(13.0, 'sensors', 'max_output_gain_dB')
            port_label = f"output {instance}"

            agc_state = self.get_output_agc_state(instance)
            if agc_state == 'ENABLED':
                raise InvalidStateChange(
                    f"Cannot set manual gain for output {instance} while output AGC is ENABLED"
                )
            if agc_state == 'UNKNOWN':
                raise InvalidStateChange(
                    f"Cannot set manual gain for output {instance} because output AGC state is unknown"
                )
        else:
            return dofval

        if gain < minimum or gain > maximum:
            raise InvalidStateChange(
                f"Gain {gain} dB for {port_label} is outside hardware range {minimum} to {maximum} dB"
            )

        return gain

    def convert_agc_mode_for_snmp(self, dofval, instance):
        self.validate_output_index(instance)
        value = str(dofval).upper()

        if value == "DISABLED":
            return 0
        if value == "ENABLED":
            return 1

        raise InvalidStateChange(
            f"Invalid output AGC mode '{dofval}' for output {instance}; expected ENABLED or DISABLED"
        )
```

### Why

These helpers handle every custom device rule before any SNMP set:

```text
["out5"] -> 5
[] -> 0
["out5", "out7"] -> 5 plus warning log
bad output labels -> failure
bad port indexes -> failure
input gain outside sensor range -> failure
output gain outside sensor range -> failure
output gain while output AGC enabled -> failure
output gain while output AGC state is unknown -> failure
```

## Step 6: Replace Setter Conversion Logic In `lookup_oid()`

### File

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

### Location

Edit the conversion block in `lookup_oid()` at lines 180-205.

### Current Code Context

Current conversion logic:

```python
                        # Converting string to int for the matrix
                        if oid == 'outputAllAGCMode':
                            if dofval == "DISABLED":
                                dofval = 0
                            elif dofval == "ENABLED":
                                dofval = 1
                        elif oid == 'inputAllGain' or oid == 'outputAllGain':
                            #enforcing the hardware bounds for gain (-14.5, +17.0)
                            try:
                                gain_float = float(dofval)
                                if gain_float < -14.5 or gain_float > 17.0:
                                    raise Exception(f'FAIL: Gain {gain_float} exceeds hardware limitations of [-14.5, +17.0]')
                                #dofval = f"{gain_float:+.1f}"
                            except ValueError:
                                raise Exception(f'Gain {dofval} is not a valid entry.')

                            if oid == 'outputAllGain':
                                output_fields = self.current_settings.get('proprietary_fields', {}).get('output_ports', {})
                                port_data = output_fields.get(f'{instance}', {})
                                agc_state = port_data.get('agc_mode', 'DISABLED')
                                
                                if str(agc_state).upper() == "ENABLED":
                                    raise Exception("Invalid command. Gain cannot be manually set when AGC Mode is enabled.")

                        if with_instance == True:
                            oid = oid + '.' + instance
```

### Change Type

REPLACE.

### Replace With This

```python
                        # Convert DoF-native values to SNMP-native values and validate hardware constraints.
                        try:
                            if oid == 'outputAllAGCMode':
                                dofval = self.convert_agc_mode_for_snmp(dofval, instance)
                            elif oid == 'outputAllInChNr':
                                dofval, warnings = self.parse_connected_outputs_for_snmp(dofval, instance)
                                for warning in warnings:
                                    logging.warning(warning)
                                    self.validation_warnings.append(warning)
                            elif oid == 'inputAllGain' or oid == 'outputAllGain':
                                dofval = self.validate_gain_for_snmp(oid, dofval, instance)
                        except InvalidStateChange as e:
                            self.result = str(e)
                            logging.warning(self.result)
                            return None, dofkey, dofval

                        if with_instance == True:
                            oid = oid + '.' + instance
```

### Why

This is where user commands become SNMP sets. Example:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

Execution path:

```text
lookup_oid(..., with_instance=False)
-> no direct mapping
-> lookup_oid(..., with_instance=True)
-> dofkey = parameters.input_ports.connected_outputs
-> instance = 6
-> oid = outputAllInChNr
-> parse_connected_outputs_for_snmp(["out5"], "6") returns 5
-> final SNMP set target outputAllInChNr.6 = 5
```

Also, the current code checks `agc_mode`; your schema and mapping use `agc_enable`. The replacement fixes that.

The `self.validation_warnings.append(warning)` line is required because `update_sucessful_set_info()` currently clears log entries before writing the success entry. Without saving warnings on the setter object, the required "selected first output" warning would only go to the process log and would not be visible in CSI state.

The local `try/except InvalidStateChange` is deliberately inside `lookup_oid()`. This preserves the template's existing `update_settings_on_device()` structure: custom validation failures return `oid = None`, then the existing failure branch publishes `STATE_CHANGE_FAILURE`. This avoids requiring a broad rewrite of the base setter method.

## Step 7: Preserve Template Flow And Make Minimal Setter Failure Edits

### File

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

### Location

Edit `update_settings_on_device()` at lines 296-361. Do not replace the whole method.

### Current Code Context

Current critical section:

```python
        if session:
            self.current_settings = CSI.get_settings(CSI.service_name)

            # set log entry index
            i = self.update_log_entry_index()

            # Find the oid
            oid, dofkey, dofval = self.lookup_oid(incoming_msgdata)

            if oid is not None:
                logging.info(f"update_settings_on_device: dofkey is {dofkey}")
                logging.info(f"SNMP setting oid {oid} to value {dofval}")

                self.update_sucessful_set_info(i, oid, incoming_msgdata)

                try:
                    # skip session.set if oid maps to a hardcoded field
                    if oid not in hardcoded:
                        self.successful = session.set(oid, dofval)
                    else:
                        self.successful = True
```

What your previous Maestro logs prove:

1. The template flow can publish `STATE_CHANGE_FAILURE` when `lookup_oid()` returns `oid = None`.
2. The template flow can publish `STATE_CHANGE_FAILURE` when `session.set()` returns false.
3. Therefore, a full rewrite of `update_settings_on_device()` is not required just to trigger failures.

What the logs do not prove:

1. They do not prove new custom validators are safe if they raise exceptions from `lookup_oid()`.
2. In the current code, `lookup_oid()` is called before the `try` block inside `update_settings_on_device()`.
3. So custom validation should either not raise out of `lookup_oid()`, or the base method must be changed to catch those exceptions.

This plan chooses the smaller change: Step 6 catches `InvalidStateChange` inside `lookup_oid()` and returns `oid = None`.

The `run()` pattern is fine:

```python
if session:
    self.result = self.update_settings_on_device(session, self.msgdata)
```

The remaining required base-code edits are small:

1. Preserve detailed validation reasons when `oid is None`.
2. Set `self.result` before writing failure logs.
3. Return `self.result` so `run()` does not overwrite it with `None`.

Optionally update the session-creation failure branch in `run()` at lines 92-97. `proxy_backend.handle_state_change()` sets `parameters.ready = "HARDWARE_BUSY"` before starting the setter. If session creation fails before `update_settings_on_device()` runs, the proxy should still set ready back to `READY`.

### Change Type

MODIFY.

### Modify SNMP Set Failure Ordering

Current code:

```python
                    if not self.successful:
                        self.update_fail_set_info(i, incoming_msgdata)
                        logging.info("snmpset failed")
                        self.result = "snmpset failed"
```

Replace with:

```python
                    if not self.successful:
                        self.result = "snmpset failed"
                        self.update_fail_set_info(i, incoming_msgdata)
                        logging.info(self.result)
```

### Modify Exception Failure Ordering

Current code:

```python
                except Exception as e:
                    self.update_fail_set_info(i, incoming_msgdata)
                    self.result = "SNMP Set Failure"
                    logging.info(f"SNMP Set failed: {e}")
```

Replace with:

```python
                except Exception as e:
                    self.result = f"SNMP Set Failure: {e}"
                    self.update_fail_set_info(i, incoming_msgdata)
                    logging.info(f"SNMP Set failed: {e}")
```

### Preserve Validation Reasons When `oid is None`

Current code:

```python
            else:
                self.update_fail_set_info(i, incoming_msgdata)
                logging.info(f"dofkey {dofkey} NOT FOUND in list of settable DoF variables or is INVALID")
                self.result = "dofkey " + dofkey + " NOT FOUND in list of settable DoF variables or is INVALID"
```

Replace with:

```python
            else:
                if self.result == 'undiagnosed failure':
                    self.result = "dofkey " + dofkey + " NOT FOUND in list of settable DoF variables or is INVALID"
                self.update_fail_set_info(i, incoming_msgdata)
                logging.info(self.result)
```

This lets custom validation failures from Step 6 keep their detailed reason instead of being overwritten by the generic "dofkey not found" text.

### Add Return Value Without Rewriting The Method

Add this at the end of `update_settings_on_device()`, after the existing `if session:` block:

```python
        return self.result
```

Completed after-context:

```python
            else:
                if self.result == 'undiagnosed failure':
                    self.result = "dofkey " + dofkey + " NOT FOUND in list of settable DoF variables or is INVALID"
                self.update_fail_set_info(i, incoming_msgdata)
                logging.info(self.result)

        return self.result
```

### Optional Defensive Fix For Session Creation Failure

This is not required for range/routing validation. It is a small robustness fix because `proxy_backend.handle_state_change()` sets `parameters.ready = "HARDWARE_BUSY"` before the setter thread runs.

Current `run()` session failure branch:

```python
        else:
            errmsg = 'Could not create session to perform SNMP Set'
            logging.debug(errmsg)
            self.result = errmsg
```

Optional replacement:

```python
        else:
            errmsg = 'Could not create session to perform SNMP Set'
            logging.debug(errmsg)
            self.result = errmsg
            current_settings = CSI.get_settings(CSI.service_name)
            if current_settings and 'parameters' in current_settings:
                current_settings['parameters']['ready'] = "READY"
                CSI.update_settings(current_settings)
```

### Why

This keeps the base template architecture intact. Invalid route labels, invalid indexes, AGC conflicts, and gain range violations publish as `STATE_CHANGE_FAILURE` through the existing `SnmpSetter.run()` logic:

```python
if self.successful:
    CSI.pub(... STATE_CHANGE_SUCCESS ...)
else:
    CSI.pub(... STATE_CHANGE_FAILURE ...)
```

## Step 8: Add Detailed Failure Logs And Fault Entries

### File

```text
src/csi_quintech_rf_matrix/snmp_setter.py
```

### Location

Edit `update_log_entry_index()` and the set-info helpers at lines 431-501.

### Current Failure Helper

```python
    def update_fail_set_info(self, i, incoming_msgdata):
        """
        Updates the settings with a session reject and new log entry

        Parameters:
        -----------
        self - current instance of class
        i - index of new log entry
        incoming_msgdata - command in json/as a dict
        """
        self.current_settings['parameters']['ready'] = "READY"

        # update log entry
        self.current_settings['log']['state'] = "HAS_ENTRIES"
        self.current_settings['log']['entries'] = {}  # Clear previous logs accumulation
        self.current_settings['log']['entries'][f"{i}"] = {"index": f"{i}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": "ERROR", "description": f"SNMP Set Failure. Invalid command passed: {incoming_msgdata}."}
        CSI.update_settings(self.current_settings)
```

### Change Type

MODIFY/ADD.

### Add This Helper After `update_log_entry_index()`

```python
    def update_fault_entry_index(self):
        i = 1

        if not 'fault_log' in self.current_settings:
            self.current_settings['fault_log'] = {}
        if not 'entries' in self.current_settings['fault_log']:
            self.current_settings['fault_log']['entries'] = {}

        if len(self.current_settings['fault_log']['entries']) > 0:
            i = int(list(self.current_settings['fault_log']['entries'])[-1]) + 1
        return i
```

### Replace Success Helper With This

Current success helper clears logs and always writes an INFO-style success entry:

```python
    def update_sucessful_set_info(self, i, oid, incoming_msgdata):
        """
        Updates the settings with a session response and new log entry

        Parameters:
        -----------
        self - current instance of class
        i - index of new log entry
        oid - oid thats mapped to the dof_name listed in incoming_msgdata
        incoming_msgdata - command in json/as a dict
        """
        self.current_settings['parameters']['ready'] = "READY"

        # dict that maps logging level to text
        log_tbl = {logging.CRITICAL: 'CRITICAL',
                logging.ERROR: 'ERROR',
                logging.WARNING: 'WARNING',
                logging.DEBUG: 'DEBUG',
                logging.INFO: 'INFO'}
                
        # get current logging level in text
        log_state = log_tbl[logging.getLogger().getEffectiveLevel()]

        #update log entry 
        if oid != 'HardCodeClearLogs':
            self.current_settings['log']['state'] = "HAS_ENTRIES"
            # Clear previous logs
            self.current_settings['log']['entries'] = {}
            self.current_settings['log']['entries'][f"{i}"] = {"index": f"{i}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": f"{log_state}", "description": f"SNMP Set Success with {incoming_msgdata}."}
```

Replace it with:

```python
    def update_sucessful_set_info(self, i, oid, incoming_msgdata):
        """
        Updates the settings with a session response and new log entry.
        """
        self.current_settings['parameters']['ready'] = "READY"

        log_tbl = {logging.CRITICAL: 'CRITICAL',
                logging.ERROR: 'ERROR',
                logging.WARNING: 'WARNING',
                logging.DEBUG: 'DEBUG',
                logging.INFO: 'INFO'}
        log_state = log_tbl[logging.getLogger().getEffectiveLevel()]

        description = f"SNMP Set Success with {incoming_msgdata}."
        if self.validation_warnings:
            log_state = "WARNING"
            description = f"{description} Warnings: {'; '.join(self.validation_warnings)}"

        if oid != 'HardCodeClearLogs':
            self.current_settings['log']['state'] = "HAS_ENTRIES"
            self.current_settings['log']['entries'] = {}
            self.current_settings['log']['entries'][f"{i}"] = {
                "index": f"{i}",
                "id": f"{uuid.uuid4()}",
                "timestamp": f"{time.time()}",
                "level": f"{log_state}",
                "description": description
            }
```

This is the CSI-visible warning path for the fan-in rule "if multiple outputs are sent, select the first and log a warning."

### Replace Failure Helper With This

```python
    def update_fail_set_info(self, i, incoming_msgdata):
        """
        Updates the settings with a session reject and new log/fault entries.
        """
        self.current_settings['parameters']['ready'] = "READY"
        reason = self.result
        if not reason or reason == 'undiagnosed failure':
            reason = f"Invalid command passed: {incoming_msgdata}"

        self.current_settings['log']['state'] = "HAS_ENTRIES"
        self.current_settings['log']['entries'] = {}
        self.current_settings['log']['entries'][f"{i}"] = {
            "index": f"{i}",
            "id": f"{uuid.uuid4()}",
            "timestamp": f"{time.time()}",
            "level": "ERROR",
            "description": f"SNMP Set Failure: {reason}. Invalid command passed: {incoming_msgdata}."
        }

        fault_i = self.update_fault_entry_index()
        self.current_settings['fault_log']['entries'][f"{fault_i}"] = {
            "index": f"{fault_i}",
            "id": f"{uuid.uuid4()}",
            "timestamp": f"{time.time()}",
            "description": reason
        }

        CSI.update_settings(self.current_settings)
```

This keeps the existing `update_fail_set_info(i, incoming_msgdata)` call signature. That is intentional: it avoids a broader base-code change and lets the failure helper read the already-populated `self.result`.

### Why

The user specifically needs detailed fault log messages. This records the actual validation reason, for example:

```text
Invalid connected_outputs value 'output5' for input 6; expected labels like 'out5'
Cannot set manual gain for output 5 while output AGC is ENABLED
Gain 99.0 dB for input 6 is outside hardware range -14.5 to 17.0 dB
```

## Step 9: Do Not Modify `proxy_backend.py` For Normal SNMP Set Success/Failure

### File

```text
src/csi_quintech_rf_matrix/proxy_backend.py
```

### Current Code Context

The normal state-change path ends here:

```python
            if "DEBUG" in incoming_msgdata['debug_mode']:
                pass
            if "VERBOSE" in incoming_msgdata['debug_mode']:
                pass
        elif "REFLECTOR" in ProxyBackend.__DEBUG:
            # run mocker
            QUINTECH_RF_MATRIX_TEST.mock_perform_snmp_set(incoming_msgdata)
        else:
            perform_snmp_set(incoming_msgdata, ProxyBackend._proxycfg)
        return
```

`perform_snmp_set()` starts the setter thread, and `SnmpSetter.run()` publishes success or failure.

### Change Type

VERIFY/NO CHANGE.

### Location

Verify only at `src/csi_quintech_rf_matrix/proxy_backend.py` lines 429-438.

### Why

The backend does not need to inspect `SnmpSetter.successful` because it does not run the setter inline. The setter thread publishes:

```text
CSI.STATE_CHANGE_SUCCESS
CSI.STATE_CHANGE_FAILURE
```

Fix failure behavior in `snmp_setter.py`, not in `proxy_backend.py`.

The commented session response fields in `create_response()` are not required for routing/gain/AGC implementation.

## Step 10: Manual Verification Checklist

Do not add test files.

### Static Checks

Run from:

```text
csi-pdk/csi_quintech_RF_Matrix
```

```text
rg routed_output src schemas
```

Expected after implementation:

```text
No active source mapping or settings field. Historical markdown may mention it.
```

Run:

```text
rg agc_mode src/csi_quintech_rf_matrix
```

Expected after implementation:

```text
No active validation code should use agc_mode. Use agc_enable.
```

Run:

```text
python -m py_compile src/csi_quintech_rf_matrix/snmp_setter.py src/csi_quintech_rf_matrix/snmp_poller.py src/csi_quintech_rf_matrix/quintech_rf_matrix_settings.py
```

### Routing Verification

Request:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

Expected SNMP set:

```text
outputAllInChNr.6 = 5
```

Request:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5", "out7"]}}}}
```

Expected:

```text
outputAllInChNr.6 = 5
warning log explaining that only the first output was used
```

Request:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": []}}}}
```

Expected:

```text
outputAllInChNr.6 = 0
```

Also verify the explicit clear forms required by `rules.txt`:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["0"]}}}}
```

and:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": [""]}}}}
```

Both should produce:

```text
outputAllInChNr.6 = 0
```

Request:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["output5"]}}}}
```

Expected:

```text
No SNMP set
STATE_CHANGE_FAILURE
fault_log entry with invalid label reason
```

### Gain And AGC Verification

Input gain inside range:

```json
{"parameters": {"input_ports": {"6": {"gain_db": 3.0}}}}
```

Expected:

```text
inputAllGain.6 = 3.0
```

Input gain outside range:

```json
{"parameters": {"input_ports": {"6": {"gain_db": 99.0}}}}
```

Expected:

```text
No SNMP set
STATE_CHANGE_FAILURE
fault_log entry with range reason
```

Output gain while AGC is enabled in current state:

```json
{"proprietary_fields": {"output_ports": {"5": {"gain_db": 1.0}}}}
```

with:

```json
{"proprietary_fields": {"output_ports": {"5": {"agc_enable": "ENABLED"}}}}
```

Expected:

```text
No SNMP set
STATE_CHANGE_FAILURE
fault_log entry explaining AGC conflict
```

### Poll Reflection Verification

Polled SNMP:

```text
outputAllInChNr.6 = 5
```

Expected DoF:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": ["out5"]}}}}
```

Polled SNMP:

```text
outputAllInChNr.6 = 0
```

Expected DoF:

```json
{"parameters": {"input_ports": {"6": {"connected_outputs": []}}}}
```

Polled SNMP:

```text
outputAllAGCMode.5 = 1
```

Expected DoF:

```json
{"proprietary_fields": {"output_ports": {"5": {"agc_enable": "ENABLED"}}}}
```

## Ordered Implementation To-Do

1. Leave `ProprietaryInputPort.rf_level_dBm` as-is. Do not rename it.
2. Leave `field_version_function` top-level on `QuintechRFMatrixSettings`.
3. In `initialize_discover()`, add nested discover definitions for `ProprietaryInputPort` and `ProprietaryOutputPort`.
4. In `schemas/snmp_to_dof_mapping.yml`, delete the commented `proprietary_fields.input_ports.routed_output` line.
5. In `schemas/snmp_to_dof_mapping.yml`, clean the routing/gain comments without changing the active `connected_outputs` mapping.
6. In `schemas/snmp_to_dof_mapping.yml`, mark gain-limit sensor OIDs with `use_oid_index: false` and `settable: false`.
7. In `snmp_poller.py`, call `format_connected_outputs_from_snmp()` for `outputAllInChNr`.
8. In `snmp_poller.py`, fix the `outputAllInChrNr` typo in the warning.
9. In `snmp_setter.py`, import `re`.
10. In `snmp_setter.py`, add `InvalidStateChange`.
11. In `snmp_setter.py`, add `self.validation_warnings = []` in `__init__()`.
12. In `snmp_setter.py`, add helper methods for port lookup, route parsing, gain validation, and AGC conversion.
13. In `snmp_setter.py`, replace inline `lookup_oid()` conversion logic with helper calls.
14. In `snmp_setter.py`, preserve multi-output route warnings in `self.validation_warnings`.
15. In `snmp_setter.py`, validate output gain against output gain limits, not input gain limits.
16. In `snmp_setter.py`, check output AGC using `agc_enable`, not `agc_mode`.
17. In `snmp_setter.py`, reject output gain if cached output AGC state is `UNKNOWN`.
18. In `snmp_setter.py`, catch `InvalidStateChange` inside `lookup_oid()` and return `oid = None` to preserve the template failure path.
19. In `snmp_setter.py`, set `self.result` before calling `update_fail_set_info()` in the existing failure branches.
20. In `snmp_setter.py`, make success logs include route warnings when only the first connected output was used.
21. In `snmp_setter.py`, return `self.result` from `update_settings_on_device()`.
22. Optional: in `snmp_setter.py`, reset `parameters.ready` to `READY` when session creation fails before `update_settings_on_device()` runs.
23. In `snmp_setter.py`, make `update_fail_set_info()` read detailed failure reasons from `self.result`.
24. In `snmp_setter.py`, write detailed fault log entries for validation failures.
25. Do not modify normal SNMP set success/failure handling in `proxy_backend.py`; verify only.
26. Do not add `SessionIDResponse` fields unless an external integration contract requires them.
27. Run the static checks and manual verification cases above.
