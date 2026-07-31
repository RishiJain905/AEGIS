/**
 * Walkthrough content for the Synthetic Training Scenario.
 *
 * Ten chapters. Six `cockpit` chapters teach the run workspace in depth; four `tour`
 * chapters pass briefly over the rest of the product. Structure and types come from
 * {@link ./tutorial-contract}; this module is pure data so it can be validated without a
 * DOM and without the machine.
 *
 * Two rules govern the copy:
 *
 *  - **Every literal label here exists on screen.** Command names, menu tier headings,
 *    badge text, button labels and connection states were read out of the components
 *    (`features/operator-actions/*`, `features/command-surface/asset-command-catalogue.ts`,
 *    `features/shell/components/status-strip.tsx`, `packages/ui/src/graph-controls`). If a
 *    surface does not exist — there is no "task an agent from this alert" button anywhere —
 *    the walkthrough does not teach it.
 *  - **Anchors degrade, they never lie.** Selectors are listed most specific first; the
 *    overlay takes the first one present and falls back to a centred card when none match.
 *    Rows keyed by dynamic ids (`alert-item-{id}`, `approve-proposal-{id}`) cannot be
 *    targeted by a fixed selector, so those beats anchor the containing panel and carry a
 *    `TODO(tutorial-anchors)` naming the component that needs a stable hook.
 */

import type { TutorialBeat, TutorialChapter } from './tutorial-contract';

// ---------------------------------------------------------------------------------------
// Chapter 1 · Orientation
// ---------------------------------------------------------------------------------------

const ORIENTATION: TutorialChapter = {
  id: 'orientation',
  title: 'Orientation',
  summary: 'What a run is, how the cockpit is laid out, and the controls that drive it.',
  section: 'cockpit',
  beats: [
    {
      id: 'welcome',
      kind: 'learn',
      title: 'Welcome to the command floor',
      body: [
        'This is a run: one deterministic simulation of a fictional organization under attack, streaming synthetic telemetry into the surface in front of you. Nothing here is timed against you, and nothing you do touches a real network.',
        'The organization is a small learning institution. A phishing email is about to reach Instructor Workstation Alpha. From that foothold the attacker misuses stolen credentials against the Identity Provider, moves to the File Server, and stages exfiltration of the Student Records Database.',
        'Your job is to read the floor, catch the signal, task the agents, and hold the approval gate on containment. This walkthrough runs alongside the live simulation rather than driving it — it stays out of your way while you work, and you can leave it and come back to any chapter.',
        'A run has a fixed horizon — twenty-five simulation minutes — and reading this floor properly takes longer than that. So if the clock nears the end while you are still working, the walkthrough holds the run once rather than let it expire out from under you. The world freezes; nothing you have gathered is lost. Resume sim and Step stay yours throughout, and this chapter closes by teaching you both.',
      ],
      anchors: [],
      pointerLabel: 'the command workspace',
      primaryAction: 'begin',
    },
    {
      id: 'cockpit-regions',
      kind: 'learn',
      title: 'Three regions',
      body: [
        'The centre is the stage: the operational graph, the operator command bar directly under it, and the run tape along the foot. Everything you act on lives there.',
        'Two docks flank it. The left dock is the operator console — where you think and ask. The right dock is the context channel — where the run reports back to you.',
        'Focus graph collapses the rail and both docks together so the stage takes the whole viewport; the same button then reads Restore panels. Use it when the map matters more than the paperwork.',
      ],
      anchors: [
        '[data-testid="focus-stage"]',
        '[data-testid="command-centre-shell"]',
        '#command-centre-content',
      ],
      pointerLabel: 'the cockpit layout and the Focus graph control',
    },
    {
      id: 'cockpit-docks',
      kind: 'learn',
      title: 'The docks and their tabs',
      body: [
        'Left dock, Operator console. Copilot is the agent chat. Evidence is a filtered search over the run’s raw event stream. Hypotheses is your ledger of working theories.',
        'Right dock, Context channel. Inspector is everything about the current selection — entity detail, risk explanation, incident context, proposals, alerts. Ops feed is the room’s live heartbeat.',
        'Collapse either dock and it narrows to a strip of its own tab names set sideways — Copilot, Evidence, Hypotheses read vertically, not icons. Click one and the dock reopens with that tab selected.',
        'The collapse itself is remembered across runs and reloads. Which tab was active is not, so a dock you reopen after a refresh lands on its first tab.',
      ],
      anchors: ['[data-testid="left-dock"]', '[data-testid="right-dock"]'],
      pointerLabel: 'the operator console and context channel docks',
    },
    {
      id: 'control-link',
      kind: 'learn',
      title: 'The control link',
      body: [
        'The strip across the top is the control link. It opens with the connection badge — Live when the stream is healthy, and Reconnecting, Catching up, Gap, Resyncing, Sim paused, Updates paused or Stale when it is not. Read it before you trust anything below it.',
        'Then the mono telemetry. RUN is the run id. STATUS is the run’s lifecycle state. SEED is the determinism anchor. SIM is the current simulation clock. SEQ is the last event sequence your browser has applied.',
        'To the right sit the threat tempo meter — five bands, quiet, low, elevated, high, critical, warming upward through them as undetected attacker progress accumulates — the loadout chips for this run’s bias guard and threat tempo, the RoE dial, the SITREP button, and your operator identity.',
      ],
      anchors: ['[data-testid="status-strip"]'],
      pointerLabel: 'the control link strip',
    },
    {
      id: 'run-seed',
      kind: 'learn',
      title: 'SEED, and why the story repeats',
      body: [
        'SEED is the number the simulation draws all of its randomness from. Same scenario version, same seed, same config produces an identical event sequence — every time, event for event.',
        'That is why this training run can promise you the same story on every replay: the phishing email lands at the same simulation minute, and the same alerts fire in the same order.',
        'Operation Silent Relay is deliberately the opposite. It launches seedless, the server draws a fresh seed, and the hidden root cause changes with it. Determinism is a training aid here, not a limit of the engine.',
      ],
      anchors: ['[data-testid="run-seed"]', '[data-testid="status-strip"]'],
      pointerLabel: 'the SEED readout in the control link',
    },
    {
      id: 'live-run-controls',
      kind: 'do',
      title: 'Driving the simulation',
      body: [
        'Step advances the run one tick by hand. Resync reloads the authoritative snapshot and replays anything you missed. Stop ends the run for good.',
        'The two pause buttons are not the same control, and this is the one operators get wrong. Pause sim is server-side: the simulation stops advancing and the world genuinely freezes. Pause updates is client-only: your view freezes while the run carries on without you.',
        'Use Pause updates when the floor is moving faster than you can read and you do not want to distort the exercise. Use Pause sim when you want the world itself to wait. Both buttons re-label while they are holding — Resume sim and Resume updates — so one glance at the pair tells you which pause is actually in force.',
        'Leave it running for now and watch SIM climb. The server ticks every two seconds of real time against a scenario horizon of twenty-five simulation minutes, so an uninterrupted run plays out in roughly ten minutes at the desk.',
      ],
      anchors: ['[data-testid="live-run-controls"]', '[data-testid="status-strip"]'],
      pointerLabel: 'the live run controls',
      objective: {
        evidence: 'telemetryFlowing',
        pending: 'Watch the SIM clock advance in the control link.',
        done: 'Telemetry is flowing — the simulation is live.',
        requirement: 'required',
      },
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 2 · Reading the floor
// ---------------------------------------------------------------------------------------

const READING_THE_FLOOR: TutorialChapter = {
  id: 'reading-the-floor',
  title: 'Reading the floor',
  summary: 'The analysis plane, selection, view options, the graph encodings, and the run tape.',
  section: 'cockpit',
  beats: [
    {
      id: 'graph-canvas',
      kind: 'learn',
      title: 'The analysis plane',
      body: [
        'The graph is the authoritative picture of the estate: every asset a node, every dependency an edge, drawn from the same GraphStore the rest of the system reads. Drag to pan, click a node to select it, right-click a node to command it.',
        'Search filters nodes by label or id. The camera group gives you Fit, zoom in, zoom out and Reset, for when you have panned somewhere you cannot get back from.',
        'The 2D/3D toggle switches renderers. 2D is the analysis plane and is authoritative for investigation; 3D is a read-only semantic presentation over the same data, and disables itself when the WebGL probe fails.',
        'Node index under the canvas is the same graph as a keyboard-navigable list. It is not a lesser view — a selection made there is the same selection.',
      ],
      anchors: [
        '[data-testid="operational-graph-canvas"]',
        '[data-testid="visualization-slot"]',
        '#command-centre-content',
      ],
      pointerLabel: 'the operational graph canvas',
    },
    {
      id: 'graph-select-asset',
      kind: 'do',
      title: 'Select an asset',
      body: [
        'Click any node on the canvas, or any entry in the node index. Two things happen together: the inspector on the right fills with that asset’s detail and risk explanation, and the operator command bar under the graph arms with the commands available against it.',
        'Try Instructor Workstation Alpha — the endpoint the phishing email is about to reach. Read its risk score and criticality, and note the asset type badge; the command set you are offered is derived from it.',
        'Clicking empty canvas clears the selection and disarms the bar.',
      ],
      anchors: [
        '[data-testid="operational-graph-canvas"]',
        '[data-testid="graph-entity-list"]',
        '[data-testid="visualization-slot"]',
      ],
      pointerLabel: 'the graph canvas and the node index',
      objective: {
        evidence: 'assetSelected',
        pending: 'Select an asset on the graph.',
        done: 'Asset selected — the inspector and command bar are armed.',
        requirement: 'required',
      },
    },
    {
      id: 'graph-view-options',
      kind: 'do',
      title: 'Open View options',
      body: [
        'View options is the graph’s control panel. It stays behind one button so the default state is almost pure canvas — the map is the play surface, and rows of chrome were cropping it.',
        'Open it now. Four groups sit inside — Data layers, Signal overlays, Investigation focus, Analysis actions — with the legend below them. Read the legend first; it decodes everything the four groups act on.',
      ],
      anchors: ['[data-testid="graph-controls-toggle"]', '[data-testid="visualization-slot"]'],
      pointerLabel: 'the View options button',
      objective: {
        evidence: 'graphOptionsOpened',
        pending: 'Open View options on the graph.',
        done: 'View options open.',
        advanceOnSatisfied: true,
        requirement: 'required',
      },
    },
    {
      id: 'graph-legend',
      kind: 'learn',
      title: 'What the shapes and rings mean',
      body: [
        'Start at the foot of the panel you just opened. The legend is the key to the canvas, and shape and colour carry asset class: a Service is a blue circle, a Device a violet diamond, a Database an amber square. That mapping never changes, so class reads at a glance without hovering.',
        'The ring around a node carries security state. Compromised means the attacker is confirmed on the asset. Suspicious means anomalous signals, unconfirmed. Investigating means under active work. Contained draws a dashed rim.',
        'Two more encodings matter. A High-risk link is an edge carrying attack-path risk. An Evidence marker flags a node with linked evidence — that one is a replay encoding, because a live run has no evidence projection to draw from, so expect both the marker and the Evidence overlay to stay empty on this floor.',
        'An asset your sensors have not disclosed yet carries no status ring at all here, and the command bar badges it undisclosed when you select it. That is deliberate fog of war, and the trap in it is obvious once you name it: a bare node is not a clean node, it is an unknown one. The floor shows what your sensors know, not what the simulation knows.',
      ],
      anchors: [
        '[data-testid="graph-legend"]',
        '[data-testid="graph-view-options"]',
        '[data-testid="operational-graph-canvas"]',
      ],
      pointerLabel: 'the graph legend',
    },
    {
      id: 'graph-analysis-tools',
      kind: 'learn',
      title: 'Layers, overlays and focus',
      body: [
        'Now the groups above the legend. Data layers decide what is drawn at all: Infrastructure, Activity, Security, Investigation, Presentation. Turning Activity off on a noisy floor leaves you the topology alone.',
        'Signal overlays tint what is already drawn — Risk, Status, Evidence, Incident. Layers change the graph; overlays change how it reads. Evidence is the exception on a live run, where there is nothing yet for it to tint.',
        'Investigation focus narrows the world without emptying it. Isolate neighborhood fades everything not adjacent to your selection down to a ghost — the nodes stay on canvas at roughly a fifth of their opacity, labels dropped, their edges fainter still — while the neighbourhood keeps full weight. Restore full graph puts it back. Neither touches the simulation: this is a view filter, not a containment action, and nothing on the estate is contained by dimming it.',
        'Analysis actions: Trace path takes two node selections and draws the route between them, which is how you argue lateral movement. Collapse dense clusters folds crowded groups into single nodes when the estate gets busy.',
      ],
      anchors: [
        '[data-testid="graph-view-options"]',
        '[data-testid="graph-layer-controls"]',
        '[data-testid="graph-controls-toggle"]',
      ],
      pointerLabel: 'the view options panel',
    },
    {
      id: 'run-tape',
      kind: 'learn',
      title: 'The run tape',
      body: [
        'The strip along the foot of the stage is the run tape: one tick per significant event, oldest to newest, coloured by the status that event carried. It gives you the one thing a vertical feed cannot — density and position across the whole run.',
        'A quiet tape is a quiet floor. A dense band of red is an attack accelerating, and you can see that without reading a line of text.',
        'Click a tick to pin its label and simulation time in the readout; click it again to unpin and follow the newest beat. The tape is a probe, not a scrubber — time travel belongs to the replay route.',
      ],
      anchors: ['[data-testid="run-tape"]', '[data-testid="run-tape-readout"]'],
      pointerLabel: 'the run tape',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 3 · Signals and cases
// ---------------------------------------------------------------------------------------

const SIGNALS_AND_CASES: TutorialChapter = {
  id: 'signals-and-cases',
  title: 'Signals and cases',
  summary: 'Alerts, incidents, the inspector, evidence search, hypotheses and the ops feed.',
  section: 'cockpit',
  beats: [
    {
      id: 'alert-anatomy',
      kind: 'do',
      title: 'Reading an alert',
      body: [
        'Detections land in the Alerts panel in the inspector. An alert is a claim, not a verdict — read all of it before you act.',
        'Severity is how bad this would be if true. Confidence is how sure the detector is, as a percentage. The mono string beside them is the detector version, which is what makes a detection reproducible and auditable months later.',
        'Expand Explanation for the detector’s own account of why it fired, what it compared against, and the evidence window. Anomaly-model alerts carry a second Anomaly model disclosure with the observed score.',
        'A single alert in isolation is rarely the whole story. The question is always whether it corroborates: does the endpoint signal line up with identity activity, or is this the benign patch-window noise you were warned about.',
      ],
      anchors: [
        '[data-tutorial-id="alerts-list"]',
        '[data-testid="alerts-panel"]',
        '[data-testid="inspector-panel"]',
        '[data-testid="right-dock"]',
      ],
      pointerLabel: 'the alerts list in the inspector',
      objective: {
        // BUG-005: this used to key on `alertRaised`, so the objective read as met the moment
        // an alert merely existed — before its Explanation was ever opened. `alertExplanationOpened`
        // (see tutorial-contract.ts) is `alertRaised` plus the actual disclosure interaction.
        evidence: 'alertExplanationOpened',
        pending: 'Wait for the first alert, then open its Explanation.',
        done: 'First alert raised — read the explanation before you move.',
        requirement: 'required',
      },
    },
    {
      id: 'incident-correlation',
      kind: 'do',
      title: 'Alerts correlate into an incident',
      body: [
        'When related alerts line up, the correlation layer rolls them into an incident. That incident is your case file: investigation, proposals, approvals and the final report all hang off it.',
        'Incidents appear as a clickable list in the inspector. Select one and the inspector deepens — triage timeline, linked alerts and evidence with provenance, the agent roster, and the response proposals raised against it.',
        'The incident state shows as a badge. It is a lifecycle, not a label; it moves as investigation and containment progress.',
      ],
      anchors: [
        '[data-testid="incidents-panel"]',
        '[data-testid="inspector-panel"]',
        '[data-testid="right-dock"]',
      ],
      pointerLabel: 'the incident list in the inspector',
      objective: {
        evidence: 'incidentOpened',
        pending: 'Open the incident from the inspector.',
        done: 'Incident open — this is your case file.',
        // BUG-006: alerts can still be uncorrelated at this point in the run — there is no
        // incident to open yet — so this cannot be required.
        requirement: 'skippable',
        skipReason:
          'Alerts may not have correlated into an incident yet this run. Investigate a little longer, or skip and come back once one appears.',
      },
    },
    {
      id: 'inspector-stack',
      kind: 'learn',
      title: 'What the inspector stacks',
      body: [
        'The inspector is not one panel; it is an ordered stack that changes with the selection. Entity detail and risk score come first, then the risk explanation, which separates the asset’s own detection score from risk propagated to it by its neighbours.',
        'Below that: incident context for the selection, the investigation workspace, BASTION response proposals, the SCRIBE reports panel, and finally the raw Incidents and Alerts lists.',
        'The ordering is the argument. What is this, how risky is it, why, what case is it part of, and what are we proposing to do about it.',
      ],
      anchors: ['[data-testid="inspector-panel"]', '[data-testid="dock-tab-inspector"]'],
      pointerLabel: 'the inspector stack',
    },
    {
      id: 'operator-console-dock',
      kind: 'learn',
      title: 'Evidence and hypotheses',
      body: [
        'Evidence, in the left dock, searches the run’s raw event stream — free text against event type or payload, plus filters for a specific asset, an event-type prefix such as telemetry., and a simulation-time range. Go here when you distrust a summary and want the underlying events.',
        'Hypotheses is your ledger. Pin a statement with the assets it implicates and your confidence, and it anchors the investigation instead of living in your head.',
        'Each card shows its origin — Operator for yours, ORACLE for the agent’s. When the bias guard finds evidence contradicting a pinned hypothesis, the card gains a Challenged badge; expand it to read why.',
        'Being challenged is not a failure. It is the system doing the one thing a lone analyst cannot reliably do for themselves: arguing against the theory you already like.',
      ],
      anchors: [
        '[data-testid="console-event-search"]',
        '[data-testid="operator-hypotheses"]',
        '[data-testid="left-dock"]',
      ],
      pointerLabel: 'the Evidence and Hypotheses tabs',
    },
    {
      id: 'ops-feed',
      kind: 'learn',
      title: 'The ops feed',
      body: [
        'The ops feed merges everything that happens on the run into one newest-first stream: agent findings, detections, policy decisions, approvals, executions, RoE changes, and your own actions.',
        'Two badges are loud on purpose. Detection marks the moment the run reveals attacker activity. Bias check marks the bias guard challenging a hypothesis. Everything else stays quiet, and routine autonomy entries that changed nothing collapse.',
        'Agent entries carry an initiator badge: Tasked means you asked for it, Autonomy means the background worker did it under the current rules of engagement. When you cannot remember whether you ordered something, that badge is the answer.',
      ],
      anchors: ['[data-testid="ops-feed-panel"]', '[data-testid="dock-tab-feed"]'],
      pointerLabel: 'the ops feed',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 4 · Commanding assets
// ---------------------------------------------------------------------------------------

const COMMANDING_ASSETS: TutorialChapter = {
  id: 'commanding-assets',
  title: 'Commanding assets',
  summary: 'The allowlisted command set, the consequences gate, and two commands end to end.',
  section: 'cockpit',
  beats: [
    {
      id: 'command-allowlist',
      kind: 'learn',
      title: 'Seven commands, four classes',
      body: [
        'You cannot type arbitrary commands at this estate. There are exactly seven allowlisted actions — observe, increase monitoring, isolate, restrict access, revoke credentials, restart service, roll back deployment — and every surface in the product speaks that same vocabulary.',
        'Each carries a fixed policy class. Class 0 · Read-only and Class 1 · Low impact execute immediately. Class 2 · Operational and Class 3 · Critical require your confirmation first.',
        'What changes per asset type is the wording, never the semantics. On a device, isolate reads Isolate host; on a database it reads Quarantine database. Same command, same class, same reversibility — the menu just talks about the target the way a responder would.',
        'Availability changes too. A database has no Class 3 tier at all, because restarting a datastore contains nothing and risks the data. You cannot isolate or restart a person either.',
      ],
      anchors: ['[data-testid="asset-command-bar"]'],
      pointerLabel: 'the operator command bar',
    },
    {
      id: 'command-surfaces',
      kind: 'learn',
      title: 'Three surfaces, one execution path',
      body: [
        'The same command menu lives in three places. The command bar under the graph promotes the first three commands to one-click buttons with All actions behind them. Right-clicking a node opens the identical menu where you found it. Deep dive opens the asset drawer, which carries the menu again under Direct action.',
        'All three run through one execution path, so policy, confirmation and audit behave identically no matter where you clicked.',
        'Inside the menu, commands group by tier: Read & monitor for Class 0 and 1, Containment · needs confirm for Class 2, Critical · needs confirm for Class 3. The tier heading is the warning.',
      ],
      anchors: [
        '[data-testid="command-bar-all-actions"]',
        '[data-testid="asset-command-bar"]',
        '[data-testid="asset-context-menu"]',
      ],
      pointerLabel: 'the three command menus',
    },
    {
      id: 'command-observe',
      kind: 'do',
      title: 'Run your first command',
      body: [
        'Select a device — Instructor Workstation Alpha will do — and press Observe. It is Class 0: read-only, reversible, no confirmation. It pulls the asset into focused watch and changes nothing about it.',
        'Watch the result toast. It reports the outcome honestly: Action executed or Action ordered when it went through, Confirmation required when the class demands a second look, Blocked by policy with the reason codes the policy engine returned, or Action failed when the request itself did not land.',
        'Blocked by policy is an honest answer, not a fault. Policy adjudicates every action from every surface, including yours, and the toast never reports a success that did not happen.',
      ],
      anchors: [
        '[data-testid="command-bar-action-observe"]',
        '[data-testid="action-result-toast"]',
        '[data-testid="asset-command-bar"]',
      ],
      pointerLabel: 'the Observe command and its result toast',
      objective: {
        evidence: 'operatorActionExecuted',
        pending: 'Run Observe on a device and read the result toast.',
        done: 'Command executed — the toast reported the outcome.',
        requirement: 'required',
      },
    },
    {
      id: 'command-consequences',
      kind: 'learn',
      title: 'The consequences gate',
      body: [
        'Class 2 and Class 3 do not execute on a click. They open the consequences dialog, and you are named there as the incident commander ordering the action.',
        'The dialog states the target by label and id, the action class, the consequence in plain language, and whether the action is reversible or hard to undo. Below that sits the blast radius preview computed against the live graph: which edges are severed or degraded, which assets are impacted, which are downstream, and any warnings.',
        'Justification (audited) is required — the confirm button stays disabled until you write one, and what you write is recorded on the action. Stand down cancels with nothing sent.',
      ],
      anchors: [
        '[data-testid="action-consequences-dialog"]',
        '[data-testid="blast-radius-summary"]',
        '[data-testid="asset-command-bar"]',
      ],
      pointerLabel: 'the consequences dialog',
    },
    {
      id: 'command-isolate-host',
      kind: 'do',
      title: 'Isolate the host',
      body: [
        'Now the real thing. Select the compromised workstation and choose Isolate host — Class 2, reversible, and the single most useful move you have against an endpoint foothold.',
        'Read the blast radius before you confirm. The host loses all network reachability and whoever is using it is cut off mid-session; the preview tells you what else loses it. Containment always costs something, and the point of this dialog is that you priced it.',
        'Write a justification — why this, why now — and confirm. Then watch the node: its status ring moves to Contained, drawn as a dashed rim, and the action lands in the ops feed as an operator execution.',
      ],
      anchors: [
        '[data-testid="command-bar-action-isolate"]',
        '[data-testid="action-consequences-dialog"]',
        '[data-testid="asset-command-bar"]',
      ],
      pointerLabel: 'the Isolate host command',
      objective: {
        evidence: 'containmentActionExecuted',
        pending: 'Isolate the compromised workstation through the consequences dialog.',
        done: 'Containment executed — watch the node’s status ring change.',
        requirement: 'required',
      },
    },
    {
      id: 'command-catalogue',
      kind: 'learn',
      title: 'The rest of the vocabulary',
      body: [
        'The same seven commands re-voice across every asset class. On a device: Raise endpoint telemetry, Isolate host, Block egress, Kill malicious process. On a database: Enable query auditing, Restrict access, Rotate database credentials, Quarantine database.',
        'On a service — the only class carrying the full toolkit: Increase telemetry, Isolate service, Restrict access, Revoke service credentials, Restart service, Roll back deployment. On an identity: Watch principal activity, Audit token issuance, Restrict entitlements, Disable account & revoke credentials. On a control point: Raise control-plane auditing, Block source addresses, Isolate control point, Restart control plane. On a deployed model: Log inference traffic, Restrict inference access, Take model offline, Roll back model version.',
        'Class 3 is the irreversible tier — Kill malicious process, Restart service, Restart control plane, Roll back deployment, Roll back model version. In-flight work is dropped, downstream consumers see an outage window, and state written since the last deploy may be lost. There is no undo, and the dialog says so.',
        'This training floor is devices, services and one database, so the identity, control-point and model verbs are not on today’s menu. They are the same seven commands wearing different clothes.',
      ],
      anchors: ['[data-testid="command-bar-all-actions"]', '[data-testid="asset-command-bar"]'],
      pointerLabel: 'the full command catalogue',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 5 · The AI copilot
// ---------------------------------------------------------------------------------------

const THE_COPILOT: TutorialChapter = {
  id: 'the-copilot',
  title: 'The AI copilot',
  summary: 'The agent roles, the four ways to engage them, and the boundary they never cross.',
  section: 'cockpit',
  beats: [
    {
      id: 'copilot-roles',
      kind: 'learn',
      title: 'Who you are talking to',
      body: [
        'The Copilot tab holds four agents, and the role tabs are not cosmetic — each targets a different thread with a different job. WATCHTOWER sweeps current alerts and telemetry and recommends what to triage first. TRACE investigates a specific asset, hypothesis or lead across the run.',
        'ORACLE weighs competing explanations for what you are seeing. BASTION drafts proportionate containment, and needs an open incident before it can propose actions.',
        'Two more agents exist without a chat tab. WARDEN is the policy layer that judges every proposal — you meet it as a decision, not a conversation. SCRIBE compiles briefs and reports, and is reached through the SITREP button in the control link.',
      ],
      anchors: [
        '[data-tutorial-id="agent-chat"]',
        '[data-testid="agent-chat-panel"]',
        '[data-testid="dock-tab-copilot"]',
      ],
      pointerLabel: 'the agent role tabs',
    },
    {
      id: 'copilot-directive',
      kind: 'do',
      title: 'Send a directive',
      body: [
        'The composer takes free text. Enter sends, Shift+Enter starts a new line, and the button always names the agent you are about to task, so you cannot send to the wrong one by accident.',
        'Be specific about the asset and the question. Something like: sweep the current alerts, tell me which endpoint signal corroborates identity activity, and what to triage first.',
        'The turn appears immediately and the agent works while the run keeps moving. You do not have to sit on the card — leave it and come back.',
      ],
      anchors: [
        '[data-tutorial-id="agent-chat-composer"]',
        '[data-tutorial-id="agent-chat"]',
        '[data-testid="agent-chat-panel"]',
      ],
      pointerLabel: 'the copilot composer',
      objective: {
        evidence: 'agentTaskCreated',
        pending: 'Send WATCHTOWER a directive in the composer.',
        done: 'Directive sent — the agent is working.',
        requirement: 'required',
      },
    },
    {
      id: 'copilot-reading-the-reply',
      kind: 'do',
      title: 'Read the tool trace',
      body: [
        'A reply is not just prose. Above the answer sit the tool chips: every tool the agent actually called, with its duration, coloured by whether the call succeeded, was rejected or failed. That is the agent’s working, not a summary of it.',
        'Below them is the artifact — the rationale, a confidence meter, and evidence-citation chips. Those chips are evidence ids from this run, and they are the grounding: a claim without a citation is a claim you should check yourself in the Evidence tab.',
        'Read the trace before you read the conclusion. An agent that reached a confident answer after one tool call is telling you something different from one that reached it after eight.',
      ],
      anchors: ['[data-tutorial-id="agent-chat"]', '[data-testid="agent-chat-panel"]'],
      pointerLabel: 'the agent reply and its tool trace',
      objective: {
        evidence: 'agentReplyReceived',
        pending: 'Wait for the reply, then read its tool chips and evidence citations.',
        done: 'Reply received — the tool trace and citations are on the card.',
        // The connected model can time out or fail at the provider boundary before it ever
        // replies — not something the operator can force, so this cannot be required.
        requirement: 'skippable',
        skipReason:
          'The connected model can be slow or fail to respond. Skip if it does not reply after a fair wait.',
      },
    },
    {
      id: 'copilot-engagement-paths',
      kind: 'learn',
      title: 'Four ways to engage',
      body: [
        'There is no button that tasks an agent from an alert. There are four genuine paths, and knowing them saves you hunting for a fifth.',
        'One, a free-text directive in the composer. Two, the role tabs, which switch which agent and thread the composer targets. Three, the RoE dial in the control link. Four, SITREP, which opens the comms desk — press Request SITREP there and SCRIBE compiles a leadership-ready brief from the run’s live evidence.',
        'The RoE dial is the one people miss. It is standing doctrine, not a one-off request. Observe means agents watch and report, and open nothing without your word. Investigate means they autonomously triage new alerts and surface findings to the feed. Forward-deployed means they proactively draft containment proposals for your approval.',
        'Changing it mid-run is audited and takes effect immediately. Anything the agents then do on their own appears in the ops feed marked Autonomy.',
      ],
      anchors: [
        '[data-testid="roe-dial"]',
        '[data-testid="sitrep-button"]',
        '[data-testid="status-strip"]',
      ],
      pointerLabel: 'the RoE dial and the SITREP button',
    },
    {
      id: 'copilot-boundary',
      kind: 'learn',
      title: 'The model proposes, it never executes',
      body: [
        'No model ever sees an execution tool. The registry marks them execution-class and not model-visible, so they are never rendered into any agent’s tool catalogue, and no role is permitted to hold one. Should a call for one arrive regardless — a poisoned scenario field, a jailbroken turn — the runtime refuses it on class alone, before it reads a single argument, and audits the attempt as unauthorized.',
        'So there is no path by which a model changes the state of this estate, however it is prompted. That is a property of the runtime, not a request in a system prompt: prompts can be talked around, and a class check cannot.',
        'Everything state-changing an agent produces is a proposal. Policy classifies it, WARDEN decides whether it may proceed, and a human holds the approval gate.',
        'That boundary is why you can hand an agent a broad directive without hedging it. The worst outcome of a bad agent judgement is a bad proposal in front of you, not a bad action behind you.',
      ],
      anchors: [
        '[data-testid="proposals-panel"]',
        '[data-tutorial-id="agent-chat"]',
        '[data-testid="inspector-panel"]',
      ],
      pointerLabel: 'the proposal boundary',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 6 · The call and the debrief
// ---------------------------------------------------------------------------------------

const THE_CALL: TutorialChapter = {
  id: 'the-call',
  title: 'The call and the debrief',
  summary: 'Proposal anatomy, WARDEN’s verdict, the approval gate, and playing the run out.',
  section: 'cockpit',
  beats: [
    {
      id: 'proposal-anatomy',
      kind: 'do',
      title: 'Anatomy of a proposal',
      body: [
        'BASTION proposals land on the incident, under BASTION response proposals. Each card names its action class and the scenario command it would run, then argues for it.',
        'The selected response option is where the argument lives: expected benefit, operational cost, reversibility, affected assets, expected consequences, uncertainty, and a confidence percentage. Evidence & monitoring expands to the evidence ids, hypothesis ids and the monitoring plan it would leave behind.',
        'Read the cost and the uncertainty first. A proposal that admits what it does not know is easier to approve than one that does not.',
      ],
      anchors: [
        '[data-testid="proposals-panel"]',
        '[data-testid="incident-proposals"]',
        '[data-testid="inspector-panel"]',
      ],
      pointerLabel: 'the response proposal',
      objective: {
        evidence: 'proposalRaised',
        pending: 'Wait for a BASTION proposal on the incident.',
        done: 'Proposal raised — read its selected option.',
        // Needs an open incident (itself skippable) and a responsive model — either can be
        // absent this run, so this cannot be required.
        requirement: 'skippable',
        skipReason:
          'Needs an open incident and a responsive model to draft a proposal. Skip if neither has landed yet.',
      },
    },
    {
      id: 'warden-decision',
      kind: 'learn',
      title: 'WARDEN’s decision',
      body: [
        'Every proposal is adjudicated by WARDEN before you are offered a gate. The decision appears on the card as one of three outcomes: allow, approval_required, or block.',
        'It comes with reason codes — the machine-readable why — and, where available, prose explaining them. When approval is required, the decision also names which operator roles may give it.',
        'A blocked proposal is not a broken agent. It is the policy layer doing its job on an action that was out of bounds, and the reason codes tell you which bound.',
      ],
      anchors: ['[data-testid="proposals-panel"]', '[data-testid="inspector-panel"]'],
      pointerLabel: 'the WARDEN policy decision',
    },
    {
      id: 'approval-gate',
      kind: 'do',
      title: 'Hold the gate',
      body: [
        'You have three answers. Approve executes the authorized command path and records the decision. Reject blocks execution and requires a written rejection reason. Modify / request revision sends it back with a revised rationale and risk tradeoffs, and WARDEN re-evaluates.',
        'The operator comment is optional and is carried on any of the three. The rejection reason is not optional — Reject stays disabled until you write one.',
        'The panel states plainly that these decisions are enforced by the backend, not by this UI. Hiding buttons would not be a control; refusing the command server-side is.',
        'If your role lacks the approvals:decide permission you see an information notice instead of controls. That is the same gate seen from the other side.',
      ],
      anchors: ['[data-testid="proposals-panel"]', '[data-testid="incident-proposals"]'],
      pointerLabel: 'the approval controls',
      objective: {
        evidence: 'containmentResolved',
        pending: 'Approve or reject the proposal.',
        done: 'Decision recorded — the gate is closed.',
        // Chained on `proposalRaised`, which is itself skippable — nothing to decide on if no
        // proposal ever landed.
        requirement: 'skippable',
        skipReason: 'Needs a proposal to approve or reject. Skip if none has been raised.',
      },
    },
    {
      id: 'executed-actions-ledger',
      kind: 'learn',
      title: 'The audit trail',
      body: [
        'Proposal lifecycle & audit, below the proposals, is the ledger: every proposal, every policy decision, every approval and every executed action, in order, with ids.',
        'This is what makes a run reviewable afterwards. The after-action review grades your decisions from this trail, and the SCRIBE report cites it.',
        'Executions also stream into the ops feed as they land, so you can watch containment take effect on the graph and see it recorded in the same moment.',
      ],
      anchors: [
        '[data-testid="proposal-lifecycle-panel"]',
        '[data-testid="proposals-panel"]',
        '[data-testid="ops-feed-panel"]',
      ],
      pointerLabel: 'the proposal lifecycle and audit ledger',
    },
    {
      id: 'run-completion',
      kind: 'do',
      title: 'Play it out',
      body: [
        'The call is made. Let the run reach its horizon — twenty-five simulation minutes — and it finalizes on its own. You can also end it early with Stop, which finalizes it where it stands.',
        'STATUS in the control link is the authority on this. When it reads completed or stopped, the after-action review and your score unlock.',
        'Nothing you do after that point changes the run. It becomes a record: replayable, exportable, and gradeable.',
      ],
      anchors: [
        '[data-testid="run-status"]',
        '[data-testid="status-strip"]',
        '[data-testid="live-run-controls"]',
      ],
      pointerLabel: 'the run status readout',
      objective: {
        evidence: 'runComplete',
        pending: 'Let the run reach its horizon, or stop it deliberately.',
        done: 'Run complete — the debrief is unlocked.',
        // Always within the operator's control — Stop is available whenever they choose it.
        requirement: 'required',
      },
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 7 · The rail and the catalogue (tour)
// ---------------------------------------------------------------------------------------

const THE_RAIL: TutorialChapter = {
  id: 'the-rail',
  title: 'The rail and the catalogue',
  summary: 'Where everything else lives, and the two scenarios you can run.',
  section: 'tour',
  beats: [
    {
      id: 'rail-destinations',
      kind: 'learn',
      title: 'The operations rail',
      body: [
        'Eight destinations down the left edge. Scenarios is the catalogue. Active run is this cockpit. Incidents is the cross-run queue. Replay reconstructs a finished run. After-action is the debrief. Reports holds SCRIBE’s output. Admin is users, policy and platform. Design system is the component reference.',
        'Run-scoped destinations — Active run, Replay, After-action — follow whichever run you are on, so you never have to carry a run id around by hand.',
        'The rail collapses to icons, and the theme toggle sits at its head — above the collapse control and all eight destinations, not down at the foot where most consoles hide it. Both preferences persist.',
      ],
      anchors: ['[data-testid="operations-rail"]'],
      pointerLabel: 'the operations rail',
      surface: 'run',
    },
    {
      id: 'scenario-catalogue',
      kind: 'learn',
      title: 'Two scenarios',
      body: [
        'The catalogue holds two operations. Synthetic Training Scenario — this one — is the recommended first run: a pinned deterministic seed with this walkthrough alongside it.',
        'Operation Silent Relay is the live operation. The server draws a fresh seed on every launch, so the hidden root cause changes each time and no two runs are alike.',
        'A run you already own can be resumed from the catalogue rather than started over.',
      ],
      anchors: ['[data-testid="scenarios-table"]'],
      pointerLabel: 'the scenario catalogue',
      surface: 'scenarios',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 8 · Incidents and reports (tour)
// ---------------------------------------------------------------------------------------

const INCIDENTS_AND_REPORTS: TutorialChapter = {
  id: 'incidents-and-reports',
  title: 'Incidents and reports',
  summary: 'The cross-run incident queue, and SCRIBE’s versioned reports.',
  section: 'tour',
  beats: [
    {
      id: 'incidents-queue',
      kind: 'learn',
      title: 'The incident queue',
      body: [
        'The Incidents route is the case-centric view: open cases across all of your active runs, not just this one. It is where you work when you are managing several engagements rather than watching one floor.',
        'Opening an incident gives you its full workspace — summary and next action, triage timeline, linked alerts and evidence with provenance, candidate affected assets, the agent roster, and its response proposals behind the same approval gate you used in the cockpit.',
        'This route deliberately runs outside the command centre shell, so it has no control link, no identity badge and no keyboard shortcuts. It is a queue, not a cockpit.',
      ],
      anchors: ['[data-testid="incident-queue-list"]', '[data-testid="incident-queue-summary"]'],
      pointerLabel: 'the incident queue',
      surface: 'incidents',
    },
    {
      id: 'scribe-reports',
      kind: 'learn',
      title: 'SCRIBE reports',
      body: [
        'Reports holds SCRIBE’s output for a run as immutable versions. Nothing is edited in place; a revision is a new version, and the earlier ones are kept. What an archived version keeps is its record — provenance, source sequence range, when it was written — not its prose. Select one and the panel says as much: full claim and timeline rendering belongs to the current version.',
        'A report is built from claims, and every claim carries citations and provenance back to the events supporting it. That is the difference between a narrative and a record.',
        'Export writes the current report to JSON, claims and metadata together, for handover outside the platform. It is always the current version that leaves the building — selecting an older one in the list does not change what the export produces.',
      ],
      anchors: ['[data-testid="reports-workspace"]', '[data-testid="report-versions-list"]'],
      pointerLabel: 'the reports workspace',
      surface: 'reports',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 9 · After-action and scoring (tour)
// ---------------------------------------------------------------------------------------

const AFTER_ACTION: TutorialChapter = {
  id: 'after-action',
  title: 'After-action and scoring',
  summary: 'How a run is graded, and the attacker lane you could not see live.',
  section: 'tour',
  beats: [
    {
      id: 'after-action-score',
      kind: 'do',
      title: 'How the run is graded',
      body: [
        'The after-action review opens with the verdict: a score out of its maximum, a letter grade, a pass or fail, and the run’s provenance — scenario version, rubric version, grading engine version, and the exact event sequence range that was graded.',
        'Below it the score breaks down per criterion, with an explanation naming the rule that produced each one and, where that rule points at a moment, a jump straight into replay at that sequence. Timeline review carries the same jump on every highlight. Decision reviews do not — they print the sequence number and leave you to carry it across yourself.',
        'Two sections are worth more than the number. Evidence coverage lists the evidence you never collected. Valid alternatives lists other defensible plays, explicitly labelled counterfactual and non-authoritative — they are not a claim that you were wrong.',
      ],
      anchors: ['[data-testid="after-action-dashboard"]', '[data-testid="overall-score"]'],
      pointerLabel: 'the after-action dashboard',
      objective: {
        evidence: 'reportReady',
        pending: 'Let the run finalize — this clears once its report has compiled.',
        done: 'Debrief ready — read the breakdown, not just the number.',
        // BUG-006: report generation runs after the tutorial hands off from the run — it can
        // take a while, or stall outright — so this cannot strand the walkthrough.
        requirement: 'skippable',
        skipReason:
          'The report compiles once the run is terminal, which can take a moment or stall. Skip and check the After-action route directly.',
      },
      surface: 'after-action',
    },
    {
      id: 'hidden-cause-reveal',
      kind: 'learn',
      title: 'The lane you could not see',
      body: [
        'Hidden cause revealed is the honest part of the debrief. During the run the attacker lane is hidden from you by design — you saw what your sensors detected, not what the simulation knew.',
        'Afterwards it is named. That is where you find out whether the theory you pinned in the hypothesis ledger was the story, or a plausible neighbour of it.',
        'The operator profile panel carries the same comparison across runs, which is where improvement actually shows up.',
      ],
      anchors: ['[data-testid="hidden-cause-reveal"]', '[data-testid="after-action-dashboard"]'],
      pointerLabel: 'the hidden cause reveal',
      surface: 'after-action',
    },
  ],
};

// ---------------------------------------------------------------------------------------
// Chapter 10 · Replay, admin and the rest (tour)
// ---------------------------------------------------------------------------------------

const REPLAY_AND_THE_REST: TutorialChapter = {
  id: 'replay-and-the-rest',
  title: 'Replay, admin and the rest',
  summary: 'Reconstructing a run, the admin console, shortcuts, and what to run next.',
  section: 'tour',
  beats: [
    {
      id: 'replay-engine',
      kind: 'learn',
      title: 'Replay',
      body: [
        'Replay reconstructs historical state from snapshots plus the event log — it does not record video. Any point in the run can be rebuilt exactly, which is only possible because events are append-only with a monotonic sequence per run.',
        'Transport controls scrub, step and change speed. Bookmarks mark moments worth returning to, and the comparison panel holds two positions side by side. A ?sequence= link addresses one exact moment, which is what the after-action timeline links use.',
        'Cinematic mode narrates the same reconstruction as chapters and beats, with captions and a reduced-motion path.',
      ],
      anchors: ['[data-testid="replay-transport-controls"]', '[data-testid="replay-scrubber"]'],
      pointerLabel: 'the replay transport',
      surface: 'replay',
    },
    {
      id: 'admin-and-the-rest',
      kind: 'learn',
      title: 'Admin, palette and shortcuts',
      body: [
        'Admin gates on the admin:manage permission and holds three sections: Users & Roles, Policy — the enforced rules, shown as they run — and Platform. Design system is the live component reference.',
        'The command palette opens on ⌘K or Ctrl+K and searches every destination and toggle by name. Run-scoped destinations only appear when there is a run to go to.',
        'Three shortcuts are worth memorising: ⌘B toggles the operations rail, ⌘J the operator console dock, ⌘I the context channel dock. Together they are the fastest way to give the graph the whole screen and take it back.',
      ],
      anchors: [
        '[data-testid="command-palette"]',
        '[data-testid="admin-users"]',
        '[data-testid="command-centre-shell"]',
      ],
      pointerLabel: 'the command palette and the admin console',
      surface: 'admin',
    },
    {
      id: 'next-operation',
      kind: 'learn',
      title: 'That is the floor',
      body: [
        'You read the graph, caught the first signal, opened the case, commanded an asset through the consequences gate, tasked a copilot, and held the approval gate on containment. That is the whole loop.',
        'This run is repeatable. The seed is pinned, so the story holds every time you replay it, and every chapter of this walkthrough stays open from the menu.',
        'Operation Silent Relay draws a fresh random seed on every launch. A different hidden root cause each run, no walkthrough, no two runs alike. You have the desk.',
      ],
      anchors: [],
      pointerLabel: 'your next operation',
      primaryAction: 'launch-next',
    },
  ],
};

/** The full guided walkthrough, in order. */
export const TUTORIAL_CHAPTERS: readonly TutorialChapter[] = [
  ORIENTATION,
  READING_THE_FLOOR,
  SIGNALS_AND_CASES,
  COMMANDING_ASSETS,
  THE_COPILOT,
  THE_CALL,
  THE_RAIL,
  INCIDENTS_AND_REPORTS,
  AFTER_ACTION,
  REPLAY_AND_THE_REST,
];

/** Every beat, flattened in walkthrough order. */
export function allBeats(): TutorialBeat[] {
  return TUTORIAL_CHAPTERS.flatMap((chapter) => chapter.beats);
}

/** Look up a chapter by its stable id. */
export function chapterById(id: string): TutorialChapter | undefined {
  return TUTORIAL_CHAPTERS.find((chapter) => chapter.id === id);
}

/** Look up a beat by its stable id, across every chapter. */
export function beatById(id: string): TutorialBeat | undefined {
  for (const chapter of TUTORIAL_CHAPTERS) {
    const found = chapter.beats.find((beat) => beat.id === id);
    if (found) {
      return found;
    }
  }
  return undefined;
}
