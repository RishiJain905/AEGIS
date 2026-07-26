import type { NodeHoverDrawingFunction, NodeLabelDrawingFunction } from 'sigma/rendering';

type NodeShape = 'circle' | 'diamond' | 'square' | 'triangle' | 'hexagon';

interface AegisNodeCanvasData {
  shape?: NodeShape;
  riskBand?: string;
  riskColor?: string;
  statusIndicator?: string;
  selected?: boolean;
  hovered?: boolean;
  showHoverLabel?: boolean;
  evidenceMarked?: boolean;
  incidentMarked?: boolean;
}

function roundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  const safeRadius = Math.min(radius, width / 2, height / 2);
  context.beginPath();
  context.moveTo(x + safeRadius, y);
  context.lineTo(x + width - safeRadius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
  context.lineTo(x + width, y + height - safeRadius);
  context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
  context.lineTo(x + safeRadius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
  context.lineTo(x, y + safeRadius);
  context.quadraticCurveTo(x, y, x + safeRadius, y);
  context.closePath();
}

/** Canonical shape painter for the per-asset-type glyph language — used by
 * the 2D label/hover renderers here and by the 3D billboard glyph textures
 * (§7.2), so the type glyphs are defined in exactly one place. */
export function drawShape(
  context: CanvasRenderingContext2D,
  shape: NodeShape,
  x: number,
  y: number,
  size: number,
): void {
  context.beginPath();
  switch (shape) {
    case 'diamond':
      context.moveTo(x, y - size);
      context.lineTo(x + size, y);
      context.lineTo(x, y + size);
      context.lineTo(x - size, y);
      break;
    case 'square':
      context.rect(x - size, y - size, size * 2, size * 2);
      break;
    case 'triangle':
      context.moveTo(x, y - size);
      context.lineTo(x + size, y + size);
      context.lineTo(x - size, y + size);
      break;
    case 'hexagon':
      for (let index = 0; index < 6; index += 1) {
        const angle = (Math.PI / 3) * index - Math.PI / 2;
        const pointX = x + Math.cos(angle) * size;
        const pointY = y + Math.sin(angle) * size;
        if (index === 0) context.moveTo(pointX, pointY);
        else context.lineTo(pointX, pointY);
      }
      break;
    case 'circle':
    default:
      context.arc(x, y, size, 0, Math.PI * 2);
  }
  context.closePath();
}

// Pills size themselves to the measured text, so ordinary asset names never
// truncate. This cap is a safety net for pathologically long labels only —
// well beyond "Communications Gateway" (the longest name in the default
// scenario roster) — so it should not fire in normal use.
const MAX_LABEL_TEXT_WIDTH = 260;

/** Trims `label` with a trailing ellipsis until it fits `maxWidth` at the
 * context's current font. Returns the original label untouched when it
 * already fits. */
function fitLabelText(
  context: CanvasRenderingContext2D,
  label: string,
  maxWidth: number,
): { text: string; width: number } {
  const fullWidth = context.measureText(label).width;
  if (fullWidth <= maxWidth) {
    return { text: label, width: Math.ceil(fullWidth) };
  }

  let truncated = label;
  while (truncated.length > 1) {
    truncated = truncated.slice(0, -1);
    const candidate = `${truncated}…`;
    if (context.measureText(candidate).width <= maxWidth) {
      return { text: candidate, width: Math.ceil(context.measureText(candidate).width) };
    }
  }
  return { text: `${truncated}…`, width: Math.ceil(context.measureText(`${truncated}…`).width) };
}

export const drawAegisNodeLabel: NodeLabelDrawingFunction = (context, rawData, settings) => {
  if (!rawData.label) {
    return;
  }

  const data = rawData as typeof rawData & AegisNodeCanvasData;
  const fontSize = settings.labelSize;
  context.save();
  context.font = `${settings.labelWeight} ${String(fontSize)}px ${settings.labelFont}`;
  const { text, width: textWidth } = fitLabelText(context, rawData.label, MAX_LABEL_TEXT_WIDTH);
  const markerSize = 4;
  const textStartOffset = 23;
  const rightPadding = 15;
  const height = fontSize + 15;
  const left = rawData.x + rawData.size + 8;
  const top = rawData.y - height / 2;
  const width = textWidth + textStartOffset + rightPadding;

  roundedRect(context, left, top, width, height, 6);
  context.fillStyle = 'rgba(12, 12, 17, 0.88)';
  context.fill();
  context.strokeStyle = data.selected ? 'rgba(242, 202, 107, 0.75)' : 'rgba(150, 148, 158, 0.28)';
  context.lineWidth = 1;
  context.stroke();

  drawShape(context, data.shape ?? 'circle', left + 11, rawData.y, markerSize);
  context.fillStyle = rawData.color;
  context.fill();

  context.fillStyle = data.selected ? '#faf7ef' : '#cdced4';
  context.textBaseline = 'middle';
  context.fillText(text, left + textStartOffset, rawData.y + 0.5);
  context.restore();
};

export const drawAegisNodeHover: NodeHoverDrawingFunction = (context, rawData) => {
  const data = rawData as typeof rawData & AegisNodeCanvasData;
  const radius = rawData.size + 4;
  const riskEmphasized = data.riskBand === 'high' || data.riskBand === 'critical';

  context.save();
  if (riskEmphasized && data.riskColor) {
    context.beginPath();
    context.arc(rawData.x, rawData.y, radius + 4, 0, Math.PI * 2);
    context.strokeStyle = data.riskColor;
    context.lineWidth = data.riskBand === 'critical' ? 6 : 4;
    context.shadowBlur = data.riskBand === 'critical' ? 18 : 12;
    context.shadowColor = data.riskColor;
    context.stroke();
    context.shadowBlur = 0;
  }

  drawShape(context, data.shape ?? 'circle', rawData.x, rawData.y, rawData.size + 2.5);
  context.globalAlpha = 0.78;
  context.strokeStyle = rawData.color;
  context.lineWidth = data.shape === 'circle' ? 1.25 : 2;
  context.stroke();
  context.globalAlpha = 1;

  if (data.selected || data.hovered || data.showHoverLabel) {
    context.beginPath();
    context.arc(rawData.x, rawData.y, radius, 0, Math.PI * 2);
    context.strokeStyle = data.selected ? '#f2ca6b' : '#d8d5c9';
    context.lineWidth = data.selected ? 3 : 2;
    context.stroke();
  }

  if (data.statusIndicator && data.statusIndicator !== 'transparent') {
    context.beginPath();
    context.arc(
      rawData.x + rawData.size * 0.72,
      rawData.y - rawData.size * 0.72,
      3,
      0,
      Math.PI * 2,
    );
    context.fillStyle = data.statusIndicator;
    context.fill();
    context.strokeStyle = '#0c0c11';
    context.lineWidth = 1.5;
    context.stroke();
  }

  // Incident overlay: red dashed containment rim around the node.
  if (data.incidentMarked) {
    context.beginPath();
    context.setLineDash([4, 3]);
    context.arc(rawData.x, rawData.y, radius + 8, 0, Math.PI * 2);
    context.strokeStyle = '#fb5b65';
    context.lineWidth = 2;
    context.stroke();
    context.setLineDash([]);
  }

  // Evidence overlay: amber diamond badge at the lower-right of the node.
  if (data.evidenceMarked) {
    drawShape(
      context,
      'diamond',
      rawData.x + rawData.size * 0.85,
      rawData.y + rawData.size * 0.85,
      4,
    );
    context.fillStyle = '#fbbf24';
    context.fill();
    context.strokeStyle = '#0c0c11';
    context.lineWidth = 1.25;
    context.stroke();
  }
  context.restore();

  // Labels are no longer drawn from here: this hover pass runs on Sigma's
  // 'hovers'/'hoverNodes' layers, which sit above the 'labels' canvas and
  // (for hoverNodes) get a full WebGL node-body redraw on top of any
  // overlapping label text. LabelTopcoat repaints every currently-displayed
  // label on a canvas above all of that instead, so labels always win
  // regardless of which nodes Sigma or this function draws on top of.
};
