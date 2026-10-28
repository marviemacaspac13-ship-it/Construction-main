import { useEffect, useState } from 'react';
import { applyElectricalGroupDecision, deviceNames, electricalChoiceError, productOptions, switchProductConflicts,
  type ElectricalChoice, type ElectricalGroupDecision, type ElectricalObservation } from '../../lib/electrical-proposals';

const button = 'min-h-11 rounded-lg border border-border px-3 text-sm hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground disabled:opacity-50';
const field = 'mt-1 min-h-11 w-full rounded-lg border border-border bg-background px-3 text-base';
type Family = ElectricalObservation['device_class'];

export function ElectricalReviewGroups({choices, family, selectedIds, productLabels, onGroup, onSelection, onEdit, onChange}: {
  choices: ElectricalChoice[]; family: Family; selectedIds: string[]; productLabels: Record<string, string>;
  onGroup: (family: Family) => void; onSelection: (ids: string[]) => void;
  onEdit: (id: string) => void; onChange: (choices: ElectricalChoice[]) => void;
}) {
  const [action, setAction] = useState<ElectricalGroupDecision['kind']>('product');
  const [sku, setSku] = useState('');
  const [box, setBox] = useState('');
  const [compatible, setCompatible] = useState(false);
  const [switchSpecsConfirmed, setSwitchSpecsConfirmed] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {setCompatible(false); setSwitchSpecsConfirmed(false); setError('');}, [selectedIds, choices]);
  const members = choices.filter(c => c.observation.device_class === family);
  const included = members.filter(c => c.disposition === 'include');
  const selected = included.filter(c => selectedIds.includes(c.observation.id));
  const switchConflicts = action === 'product' ? selected.filter(c => switchProductConflicts(c, sku)) : [];
  const unresolved = members.filter(c => electricalChoiceError(c));
  function apply() {
    setError('');
    if (action === 'product' && !sku) {setError('Choose a product first.'); return;}
    if (action === 'product' && family === 'switch' && !switchSpecsConfirmed) {setError('Confirm the selected switches match the product’s one-way function and gang count.'); return;}
    if (action === 'box' && !box) {setError('Choose a box or explicitly exclude boxes.'); return;}
    const decision: ElectricalGroupDecision = action === 'product'
      ? {kind: 'product', sku: sku as ElectricalChoice['selected_sku'] & string, confirmSwitchSpecs: family === 'switch' && switchSpecsConfirmed}
      : action === 'box'
        ? {kind: 'box', itemId: box === 'omit' ? null : box as ElectricalChoice['box_item_id'], confirmed: compatible, reason}
        : {kind: 'exclude', reason};
    try {
      onChange(applyElectricalGroupDecision(choices, selected.map(c => c.observation.id), decision));
    } catch (e) {setError(e instanceof Error ? e.message : 'Check the selected devices.');}
  }
  return <div className="space-y-4">
    <h2 className="text-lg font-medium">Decide by device group</h2>
    <div className="grid grid-cols-2 gap-2" aria-label="Device groups">
      {(Object.keys(deviceNames) as Family[]).filter(f => choices.some(c => c.observation.device_class === f)).map(f => {
        const group = choices.filter(c => c.observation.device_class === f);
        const pending = group.filter(c => electricalChoiceError(c)).length;
        return <button key={f} type="button" className={`${button} py-2 text-left ${family === f ? 'bg-accent border-foreground' : ''}`} aria-pressed={family === f} onClick={() => onGroup(f)}>
          <span className="block font-medium">{deviceNames[f]} ({group.length})</span>
          <span className="block text-xs mt-1">{pending ? `${pending} need decisions` : 'Decisions complete'}</span>
        </button>;
      })}
    </div>
    {!members.length && <p className="text-sm">No devices yet. Add missing devices on the drawing.</p>}
    {!!members.length && <>
      <div className="flex items-center justify-between gap-2 text-sm">
        <span role="status">{selected.length} selected · {unresolved.length} need decisions</span>
        {family !== 'unknown' && <button type="button" className={button} onClick={() => onSelection(selected.length === included.length ? [] : included.map(c => c.observation.id))}>
          {selected.length === included.length && included.length ? 'Clear selection' : 'Select included'}
        </button>}
      </div>
      <ul className="max-h-60 overflow-auto divide-y divide-border border-y border-border" aria-label={`${deviceNames[family]} devices`}>
        {members.map(c => {
          const id = c.observation.id;
          const index = choices.findIndex(item => item.observation.id === id) + 1;
          return <li key={id} className="flex items-center gap-2 py-2">
            {family !== 'unknown' && <label className="flex min-h-11 min-w-11 items-center justify-center">
              <input type="checkbox" className="size-5" aria-label={`Select device ${index}`} checked={selectedIds.includes(id) && c.disposition === 'include'} disabled={c.disposition === 'exclude'}
                onChange={e => onSelection(e.target.checked ? [...selectedIds, id] : selectedIds.filter(v => v !== id))}/>
            </label>}
            <div className="min-w-0 flex-1 text-sm"><span className="font-medium">Device {index}</span>
              <span className="block text-xs text-muted-foreground">{c.disposition === 'exclude' ? `Excluded: ${c.exclusion_reason || 'reason needed'}` : electricalChoiceError(c) || `${c.selected_sku} · decisions complete`}</span>
              {switchConflicts.includes(c) && <span className="block text-xs text-destructive">Conflicts with selected product. Edit or uncheck this device.</span>}
            </div>
            <button type="button" className={button} aria-label={`Edit device ${index}`} onClick={() => onEdit(id)}>Edit</button>
          </li>;
        })}
      </ul>
      {family === 'unknown' ? <p className="text-sm">Edit each unresolved device to identify its type before applying shared decisions.</p> : <>
        <div className="flex flex-wrap gap-2" aria-label="Shared decision">
          {(['product', 'box', 'exclude'] as const).map(kind => <button type="button" key={kind} className={`${button} ${action === kind ? 'bg-accent border-foreground' : ''}`} aria-pressed={action === kind} onClick={() => {setAction(kind); setCompatible(false); setSwitchSpecsConfirmed(false); setReason(''); setError('');}}>
            {kind === 'product' ? 'Product' : kind === 'box' ? 'Boxes' : 'Exclude devices'}
          </button>)}
        </div>
        {action === 'product' && <>
          <label className="block text-sm">Product for selected devices<select className={field} value={sku} onChange={e => {setSku(e.target.value); setSwitchSpecsConfirmed(false); setError('');}}>
            <option value="">Choose product</option>{productOptions[family].map(v => <option key={v} value={v}>{productLabels[v]}</option>)}
          </select></label>
          {family === 'switch' && <>
            <p className="text-sm text-muted-foreground">Choose matching assemblies only. Gang count is the number of switches on a plate; it does not mean three-way switching.</p>
            {!!switchConflicts.length && <p role="alert" className="text-sm text-destructive">{switchConflicts.length} selected devices conflict with this product. Edit or uncheck the flagged devices first.</p>}
            {!!sku && <label className="flex gap-3 text-sm"><input type="checkbox" className="size-5 shrink-0" checked={switchSpecsConfirmed} disabled={!selected.length || !!switchConflicts.length} onChange={e => setSwitchSpecsConfirmed(e.target.checked)}/>I verified all {selected.length} selected assemblies are {Number(sku.slice(-1))}-gang, one-way switches.</label>}
          </>}
        </>}
        {action === 'box' && <>
          <label className="block text-sm">Box decision for selected devices<select className={field} value={box} onChange={e => {setBox(e.target.value); setCompatible(false); setReason(''); setError('');}}>
            <option value="">Choose box decision</option><option value="UTB01">Utility box · UTB01</option><option value="JCB01">Junction box with cover · JCB01</option><option value="omit">Exclude boxes from scope</option>
          </select></label>
          {box && box !== 'omit' && <label className="flex gap-3 text-sm"><input type="checkbox" className="size-5 shrink-0" checked={compatible} onChange={e => setCompatible(e.target.checked)}/>I verified this box fits every selected assembly.</label>}
        </>}
        {(action === 'exclude' || action === 'box' && box === 'omit') && <label className="block text-sm">Reason applying to all selected devices<textarea className={`${field} py-2`} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)}/></label>}
        <p className="text-xs text-muted-foreground">Applies only to the {selected.length} checked devices. Existing choices on those devices will be replaced; other devices keep their choices.</p>
        <button type="button" className={`${button} w-full bg-foreground text-background hover:opacity-90 hover:bg-foreground`} disabled={!selected.length} onClick={apply}>Apply {action === 'product' ? 'product' : action === 'box' ? 'box decision' : 'exclusion'} to {selected.length} devices</button>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </>}
    </>}
  </div>;
}
