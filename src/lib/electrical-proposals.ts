import { authHeaders } from './supabase';
import type { FixtureBox } from './plumbing-proposals';
import type { ElectricalDeviceId } from './estimate-input';

export type ElectricalObservation = {
  id: string; assembly_id: string; box_2d: FixtureBox;
  device_class: 'light_point' | 'convenience_outlet' | 'switch' | 'ac_outlet' | 'unknown';
  raw_mark: string | null; adjacent_text: string | null;
  socket_configuration: 'single' | 'duplex' | 'triplex' | null;
  gang_count: number | null;
  switching_function: 'one_way' | 'three_way' | 'four_way' | null;
  uncertainty: string | null;
};
export type ElectricalChoice = {
  observation: ElectricalObservation; disposition: 'include' | 'exclude';
  selected_sku: ElectricalDeviceId | null; exclusion_reason: string | null;
  box_item_id: 'UTB01' | 'JCB01' | null; box_compatibility_confirmed: boolean;
  box_exclusion_reason: string | null;
};
export type ElectricalProposal = {
  proposed: ElectricalObservation[]; receipt: string; source_sha256: string;
  image_width: number; image_height: number; limitations: string[];
  provider?: 'gemini' | 'template'; model?: string; message?: string;
  attempts?: {provider:'gemini';model:string;outcome:string;elapsed_ms:number;returned_model:string|null}[];
};
export type ElectricalConfirmation = {
  receipt: string; confirmed: true; choices: ElectricalChoice[]; estimate_scope: 'devices_and_boxes' | 'reviewed_device_allowances';
};
export type ElectricalReview = {
  version: string; source_sha256: string; image_width: number; image_height: number;
  owner_id: string; provider: string; model: string; proposed: ElectricalObservation[];
  choices: ElectricalChoice[]; confirmed_at: string; estimate_scope: 'standard' | 'devices_and_boxes' | 'reviewed_device_allowances';
  prompt_version?: 'electrical-devices-v1' | null;
  attempts?: ElectricalProposal['attempts']; limitations?: string[];
};

export const deviceNames = { light_point: 'Ceiling outlet', convenience_outlet: 'Convenience outlet',
  switch: 'Switch assembly', ac_outlet: 'AC outlet', unknown: 'Unresolved device' };
export const productOptions: Record<ElectricalObservation['device_class'], string[]> = {
  light_point: ['CLR01', 'CLR02', 'CLR03'], convenience_outlet: ['OT01', 'OT02', 'OT03'],
  switch: ['SW01', 'SW02', 'SW03'], ac_outlet: ['ACO01'], unknown: [],
};
export function initialElectricalChoice(observation: ElectricalObservation): ElectricalChoice {
  return { observation, disposition: 'include', selected_sku: null, exclusion_reason: null,
    box_item_id: null, box_compatibility_confirmed: false, box_exclusion_reason: null };
}

/** Form feedback only; the backend independently checks all semantics and geometry. */
export function electricalChoiceError(c: ElectricalChoice): string {
  if(c.disposition==='exclude') return c.exclusion_reason?.trim() ? '' : 'Explain why this device is excluded.';
  const o=c.observation;
  if(!c.selected_sku || !productOptions[o.device_class].includes(c.selected_sku)) return 'Select a matching catalog product.';
  if(o.device_class==='switch' && (o.switching_function!=='one_way' || o.gang_count!==Number(c.selected_sku.slice(-1))))
    return 'Confirm one-way switching and the matching gang count. Three-way and four-way switches have no approved product.';
  if(o.device_class==='convenience_outlet' && o.gang_count!==null && o.gang_count!==Number(c.selected_sku.slice(-1))) return 'The gang count conflicts with the product.';
  if(o.device_class==='ac_outlet' && o.gang_count!==null && o.gang_count!==1) return 'ACO01 is a generic one-gang product.';
  if(c.box_item_id) return c.box_compatibility_confirmed ? '' : 'Confirm the selected box fits this assembly.';
  return c.box_exclusion_reason?.trim() ? '' : 'Select a compatible box or explain its exclusion.';
}

export type ElectricalGroupDecision =
  | {kind: 'product'; sku: ElectricalDeviceId; confirmSwitchSpecs?: boolean}
  | {kind: 'box'; itemId: ElectricalChoice['box_item_id']; confirmed: boolean; reason: string}
  | {kind: 'exclude'; reason: string};

export function switchProductConflicts(c: ElectricalChoice, sku: string): boolean {
  const o = c.observation;
  return o.device_class === 'switch' && productOptions.switch.includes(sku) &&
    (o.switching_function !== null && o.switching_function !== 'one_way' ||
      o.gang_count !== null && o.gang_count !== Number(sku.slice(-1)));
}

export function applyElectricalGroupDecision(
  choices: ElectricalChoice[], ids: string[], decision: ElectricalGroupDecision,
): ElectricalChoice[] {
  const selected = choices.filter(c => ids.includes(c.observation.id) && c.disposition === 'include');
  if (!selected.length) throw new Error('Select included devices first.');
  const family = selected[0].observation.device_class;
  if (family === 'unknown' || selected.some(c => c.observation.device_class !== family))
    throw new Error('Classify devices individually before applying a shared decision.');
  if (decision.kind === 'exclude' && !decision.reason.trim()) throw new Error('Enter a reason for this exclusion.');
  const changes = new Map<string, ElectricalChoice>();
  for (const c of selected) {
    let next: ElectricalChoice;
    if (decision.kind === 'product') {
      next = {...c, selected_sku: decision.sku, box_compatibility_confirmed: false};
      if (family === 'switch' && decision.confirmSwitchSpecs && productOptions.switch.includes(decision.sku)) {
        if (switchProductConflicts(c, decision.sku))
          throw new Error(`Device ${choices.indexOf(c) + 1} conflicts with this product. Edit it or uncheck it before applying.`);
        next.observation = {...c.observation, switching_function: 'one_way', gang_count: Number(decision.sku.slice(-1))};
      }
      // Validate product semantics without requiring the later box decision yet.
      const error = electricalChoiceError({...next, box_item_id: null, box_exclusion_reason: 'Pending box review'});
      if (error) throw new Error(error);
    } else if (decision.kind === 'box') {
      next = {...c, box_item_id: decision.itemId, box_compatibility_confirmed: !!decision.itemId && decision.confirmed,
        box_exclusion_reason: decision.itemId ? null : decision.reason.trim()};
      const error = electricalChoiceError(next);
      if (error) throw new Error(error);
    } else {
      next = {...c, disposition: 'exclude', exclusion_reason: decision.reason.trim(), selected_sku: null,
        box_item_id: null, box_compatibility_confirmed: false, box_exclusion_reason: null};
    }
    changes.set(c.observation.id, next);
  }
  return choices.map(c => changes.get(c.observation.id) ?? c);
}

export async function proposeElectrical(file: File): Promise<ElectricalProposal> {
  const form=new FormData(); form.append('file',file);
  const response=await fetch(`${import.meta.env.VITE_SCAN_API_URL ?? 'http://localhost:8000'}/api/electrical/proposals`,
    {method:'POST', headers:await authHeaders(), body:form});
  if(!response.ok) {
    const body=await response.json().catch(()=>null);
    throw new Error(typeof body?.detail==='string' ? body.detail : 'Could not prepare electrical review. Retry the scan.');
  }
  return response.json();
}

/** Zero proposals is most often an image too small to read, not a sheet with no devices. */
export function emptyProposalHint(proposal: {proposed: unknown[]}): string {
  return proposal.proposed.length ? '' : 'No devices were found on this drawing. If its symbols are small or blurry, '
    + 'upload a clearer export of the original. Otherwise, add each device on the drawing.';
}
