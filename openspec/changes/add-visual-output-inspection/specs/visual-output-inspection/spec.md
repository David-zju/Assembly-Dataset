## ADDED Requirements

### Requirement: Restore visual inspection geometry from persisted outputs

The system SHALL restore runtime CadQuery face objects for visual inspection from the original STEP file and persisted L0 output without rerunning L1 contact detection.

#### Scenario: Restore face map for valid assembly output

- **WHEN** the user provides a valid original STEP file and matching `l0_output.json`
- **THEN** the system SHALL restore a `face_uid -> cq.Face` mapping for all L0 faces
- **AND** the restored mapping SHALL pass the existing fingerprint validation strategy.

#### Scenario: Reject unreliable part boundary output

- **WHEN** the provided L0 output has `part_boundary_reliable = false`
- **THEN** the system SHALL refuse L1 contact visualization that depends on cross-Part semantics
- **AND** it SHALL report that the L0 output cannot reliably recover Part-scoped contact context.

#### Scenario: Detect mismatched STEP and L0 output

- **WHEN** the original STEP file does not match the provided L0 output fingerprints
- **THEN** the system SHALL fail with a diagnostic error rather than showing potentially incorrect highlighted faces.

### Requirement: Provide L0 visual inspection selections

The system SHALL support visual inspection of L0 entities by selecting faces or parts from persisted L0 output.

#### Scenario: Highlight face by face_uid

- **WHEN** the user selects a valid `face_uid`
- **THEN** the system SHALL highlight the corresponding face in `ocp_vscode`
- **AND** it SHALL label the highlighted object with `face_uid`, `part_uid`, and `geom_type`.

#### Scenario: Highlight part by part_uid

- **WHEN** the user selects a valid `part_uid`
- **THEN** the system SHALL highlight the corresponding Part geometry
- **AND** it SHALL include the Part name and face count in the object label or adjacent diagnostic output.

#### Scenario: Highlight unsupported faces

- **WHEN** the user requests unsupported L0 faces
- **THEN** the system SHALL highlight all faces where `supported = false`
- **AND** it SHALL expose each face's `skip_reason`.

#### Scenario: Report missing L0 selection

- **WHEN** the user selects a `face_uid` or `part_uid` that is not present in the L0 output
- **THEN** the system SHALL report a clear not-found error and SHALL NOT open a misleading viewer scene.

### Requirement: Provide browsable L1 contact inspection

The system SHALL provide a browsable list of L1 contacts so users can inspect multiple `contact_uid` values without restarting the script for each contact.

#### Scenario: Browse contacts from L1 output

- **WHEN** the user starts the L1 contact browser with matching STEP, L0 JSON, and L1 JSON files
- **THEN** the system SHALL present a contact list containing `contact_uid`, `contact_type`, confidence, `face_uid_pair`, associated `part_uid` values, and `needs_exact_overlap` status.

#### Scenario: Select contact from list

- **WHEN** the user selects a contact from the browser list
- **THEN** the system SHALL update the viewer to highlight the two faces referenced by that contact
- **AND** the two faces SHALL use distinct colors.

#### Scenario: Preserve browser session across selections

- **WHEN** the user selects another contact in the same browser session
- **THEN** the system SHALL update the highlighted viewer objects without requiring the process to restart or reload L1 JSON.

#### Scenario: Report missing contact

- **WHEN** the user selects or searches for a `contact_uid` that is not present in L1 output
- **THEN** the system SHALL report that the contact does not exist and SHALL keep the current valid selection unchanged.

### Requirement: Filter and sort L1 contacts for inspection

The system SHALL allow users to narrow the L1 contact list by contact properties and involved entities.

#### Scenario: Filter by contact type

- **WHEN** the user filters by `contact_type`
- **THEN** the contact list SHALL include only contacts whose `contact_type` matches the selected type.

#### Scenario: Filter by needs_exact_overlap

- **WHEN** the user filters for `needs_exact_overlap = true`
- **THEN** the contact list SHALL include only contacts whose parameters indicate `needs_exact_overlap = true`.

#### Scenario: Filter by part_uid or face_uid

- **WHEN** the user filters by a `part_uid` or `face_uid`
- **THEN** the contact list SHALL include only contacts involving that Part or face.

#### Scenario: Sort by confidence

- **WHEN** the user sorts by confidence
- **THEN** the contact list SHALL order contacts by confidence in the requested direction.

### Requirement: Render large assemblies with local context by default

The system SHALL avoid default full-assembly rendering for large L1 contact inspection and SHALL render local contact context unless explicitly requested otherwise.

#### Scenario: Default L1 contact rendering

- **WHEN** the user selects a contact in L1 browser mode
- **THEN** the viewer scene SHALL include the two contact faces and their parent Part contexts
- **AND** the parent Part contexts SHALL be visually subdued relative to the selected faces.

#### Scenario: Disable context rendering

- **WHEN** the user requests no context
- **THEN** the viewer scene SHALL include only the selected contact faces.

#### Scenario: Request full context rendering

- **WHEN** the user explicitly requests full assembly context
- **THEN** the system MAY render all Part geometry
- **AND** it SHALL warn that full context can be slow for large models.

### Requirement: Isolate ocp_vscode integration behind a viewer adapter

The system SHALL isolate direct `ocp_vscode` calls behind a viewer adapter so selection and scene-building logic can be tested without a GUI.

#### Scenario: Build scene without real viewer

- **WHEN** automated tests exercise L0 or L1 visual inspection logic
- **THEN** they SHALL be able to verify the produced scene objects, names, colors, transparency, and roles without launching VS Code viewer.

#### Scenario: Viewer unavailable

- **WHEN** `ocp_vscode` cannot connect to a running viewer
- **THEN** the system SHALL report an actionable viewer connection diagnostic
- **AND** it SHALL NOT treat the visual inspection data preparation as failed if selection and scene construction succeeded.

### Requirement: Preserve core pipeline behavior

The visual inspection capability SHALL NOT alter L0/L1 pipeline outputs or require visualization dependencies for normal pipeline execution.

#### Scenario: Run pipeline without visualization

- **WHEN** the user runs `scripts/run_pipeline.py`
- **THEN** the pipeline SHALL NOT import or require `ocp_vscode`
- **AND** L0/L1 JSON outputs SHALL keep their existing schema.

#### Scenario: Visual inspection uses existing outputs

- **WHEN** the user runs L0 or L1 visual inspection
- **THEN** the tool SHALL read existing JSON outputs and original STEP files
- **AND** it SHALL NOT rewrite L0/L1 output files as part of normal viewing.
