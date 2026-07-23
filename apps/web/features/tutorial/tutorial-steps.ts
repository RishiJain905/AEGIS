import type { TutorialStepId } from './tutorial-machine';

export interface TutorialStepContent {
  id: TutorialStepId;
  index: number;
  /** Uppercase eyebrow shown above the title. */
  eyebrow: string;
  title: string;
  /** Paragraphs of body copy. */
  body: string[];
  /**
   * CSS selectors the spotlight anchors to, tried in order — the first element present
   * in the DOM wins. An empty list (or no match at runtime) renders the card centred in
   * a graceful, still-accessible degraded mode.
   */
  anchors: string[];
  /** What the operator is being pointed at, announced to assistive tech. */
  pointerLabel: string;
  /** The evidence the walkthrough is waiting on before it advances. */
  advanceHint: string;
  /** Primary call-to-action rendered on the card, when the step offers one. */
  primaryAction?: 'begin' | 'launch-next';
}

/**
 * Ordered walkthrough copy for the Synthetic Training Scenario. Tone is confident
 * ops-room: it explains the command surface without gamer-cheese. Anchors point at
 * stable `data-testid` / `data-tutorial-id` hooks already present in the shell; the
 * agent-chat hooks are contributed by the copilot panel and degrade gracefully when
 * absent.
 */
export const TUTORIAL_STEPS: readonly TutorialStepContent[] = [
  {
    id: 'welcome',
    index: 0,
    eyebrow: 'Guided run · Aurora Learning Lab',
    title: 'Welcome to the command floor',
    body: [
      'This is a hand-held training run against a fictional learning organization. Nothing here is timed against you, and every run uses the same pinned seed — so the same story unfolds each time you replay it.',
      'A phishing email is about to reach an instructor workstation. From that foothold the attacker will misuse stolen credentials, move to the file server, and stage an exfiltration of the student records database. Your job: detect it, task an agent to investigate, and approve containment before the records leave.',
      'The workspace has three regions — the operational graph and telemetry in the centre, the inspector on the right, and the control link across the top. We will walk each one as the run comes alive.',
    ],
    anchors: [],
    pointerLabel: 'the command workspace',
    advanceHint: 'Begin when you are ready.',
    primaryAction: 'begin',
  },
  {
    id: 'watch',
    index: 1,
    eyebrow: 'Step 2 · Read the floor',
    title: 'Watch the ops floor come alive',
    body: [
      'Baseline telemetry is streaming into the operational graph — authentications, process activity, database queries. Assets sit green while behaviour looks routine.',
      'Keep an eye on the control link strip at the top: it shows the live connection, the run status, and the deterministic seed anchoring this exercise.',
    ],
    anchors: ['[data-testid="visualization-slot"]', '#command-centre-content'],
    pointerLabel: 'the operational graph',
    advanceHint: 'Waiting for the first telemetry to flow…',
  },
  {
    id: 'first-blood',
    index: 2,
    eyebrow: 'Step 3 · First signal',
    title: 'First blood',
    body: [
      'The detection layer has raised its first alert. Open it in the inspector and read the explanation — a single alert in isolation is rarely the whole story.',
      'Corroborate: does the endpoint signal line up with identity activity? That pairing is what separates a real intrusion from the benign SSO patch-window noise you were warned about.',
    ],
    anchors: ['[data-testid="alerts-panel"]', '[data-testid="inspector-panel"]'],
    pointerLabel: 'the alert in the inspector',
    advanceHint: 'Waiting for the first alert to be raised…',
  },
  {
    id: 'open-incident',
    index: 3,
    eyebrow: 'Step 4 · Escalate',
    title: 'Open the incident',
    body: [
      'Correlated alerts roll up into an incident. Select it from the inspector to pull its full context — affected assets, evidence, and the investigation workspace — into view.',
      'This is your case file. Everything you do next hangs off it.',
    ],
    anchors: ['[data-testid="inspector-panel"]'],
    pointerLabel: 'the incident list in the inspector',
    advanceHint: 'Open an incident to continue…',
  },
  {
    id: 'task-copilot',
    index: 4,
    eyebrow: 'Step 5 · Task your copilot',
    title: 'Task your AI copilot',
    body: [
      'You are not investigating alone. The agent copilot takes a free-text directive and works the case through an allowlisted tool registry — triaging signals, tracing the path, and forming hypotheses.',
      'Give it a directive in the composer, for example: "Investigate the instructor workstation and confirm whether the identity provider logins are credential misuse." Watch its tool calls stream back into the thread.',
    ],
    anchors: [
      '[data-tutorial-id="agent-chat-composer"]',
      '[data-tutorial-id="agent-chat"]',
      '[data-testid="inspector-panel"]',
    ],
    pointerLabel: 'the agent chat composer',
    advanceHint: 'Waiting for an agent task on this run…',
  },
  {
    id: 'containment',
    index: 5,
    eyebrow: 'Step 6 · Make the call',
    title: 'The containment call',
    body: [
      'State-changing actions are never executed by the model. The BASTION agent proposes containment; policy validation classifies it (Class 0–3); and a human — you — holds the approval gate.',
      'Review the proposal: expected benefit, operational cost, reversibility, affected assets. Approve to isolate the threat before exfiltration completes, or reject if the evidence is not there yet.',
    ],
    anchors: [
      '[data-testid="proposals-panel"]',
      '[data-testid="incident-proposals"]',
      '[data-tutorial-id="agent-chat"]',
      '[data-testid="inspector-panel"]',
    ],
    pointerLabel: 'the response proposal',
    advanceHint: 'Approve or reject a proposal to continue…',
  },
  {
    id: 'endgame',
    index: 6,
    eyebrow: 'Step 7 · Endgame',
    title: 'Play it through to the end',
    body: [
      'The call is made. Let the run play out — the simulation advances on its own until the scenario horizon is reached, then finalizes automatically.',
      'When it completes, the after-action report and your run score unlock. That is where the whole story — including the attacker lane you could not see live — is laid out for review.',
    ],
    anchors: ['[data-testid="status-strip"]'],
    pointerLabel: 'the run status in the control link',
    advanceHint: 'Waiting for the run to complete…',
  },
  {
    id: 'debrief',
    index: 7,
    eyebrow: 'Debrief · Nicely done',
    title: 'That is the rhythm of a run',
    body: [
      'You watched the floor, caught the first signal, opened the incident, tasked a copilot, and made the containment call — the full loop of a blue-team engagement.',
      'The after-action report is your debrief: read it to see how the intrusion actually unfolded and how your response scored. Replay this scenario as many times as you like; the seed is pinned, so the story holds.',
      'Ready for the real thing? Operation Silent Relay draws a fresh random seed every launch — a different hidden root cause each run, no walkthrough, no two runs alike.',
    ],
    anchors: [],
    pointerLabel: 'your next operation',
    advanceHint: '',
    primaryAction: 'launch-next',
  },
];

export function stepByIndex(index: number): TutorialStepContent | undefined {
  return TUTORIAL_STEPS[index];
}
