import {useEffect,useRef,useState} from 'react';
import type {Project} from '../../lib/projects';
import type {EstimateCorrections} from '../../lib/estimate-input';
import {fieldValue,parseEditor,sourceFields,type EditField} from '../../lib/editor-input';
import {EditorError,editorRequest,type EditorPreview} from '../../lib/editor';

export const editorButton='min-h-11 px-4 rounded-lg border border-border text-sm hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground disabled:opacity-50 disabled:cursor-not-allowed';
const money=(n:number)=>n.toLocaleString('en-PH',{style:'currency',currency:'PHP'});
const empty:EstimateCorrections={quantities:{},unit_prices:{},reason:null};

export function EstimateEditor({project,onSaved,onDirty}:{project:Project;onSaved:()=>Promise<void>;onDirty:(dirty:boolean)=>void}) {
  const original=project.saved_scan!.original_input;
  const revision=project.active_revision!;
  const initial=revision.corrections??empty;
  const source=sourceFields(original);
  const priceFields:EditField[]=original.prices.items.filter(row=>revision.estimate.line_items.some(li=>li.item_id===row.item_id)).map(row=>({key:`price.${row.item_id}`,label:`${row.item_name} · ${row.item_id} · ${row.unit??'per item'}`,original:row.price,provenance:'Catalog'}));
  const fields=[...source,...priceFields];
  const [values,setValues]=useState<Record<string,string>>(()=>Object.fromEntries(fields.map(f=>[f.key,fieldValue(f,initial)])));
  const [reason,setReason]=useState(initial.reason??'');
  const [errors,setErrors]=useState<Record<string,string>>({});
  const [error,setError]=useState('');
  const [conflict,setConflict]=useState(false);
  const [busy,setBusy]=useState('');
  const [preview,setPreview]=useState<EditorPreview|null>(null);
  const [touched,setTouched]=useState(false);
  const [resetAll,setResetAll]=useState(false);
  const pending=useRef<{key:string;corrections:EstimateCorrections}|null>(null);
  const inFlight=useRef(false);
  const errorRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{onDirty(touched);},[touched,onDirty]);
  useEffect(()=>{if(error||Object.keys(errors).length) errorRef.current?.focus();},[error,errors]);
  function change(key:string,value:string) {setValues(v=>({...v,[key]:value}));setTouched(true);setPreview(null);pending.current=null;setError('');setErrors(e=>{const copy={...e};delete copy[key];return copy;});}
  function reset() {setResetAll(true);setValues(Object.fromEntries(fields.map(f=>[f.key,String(f.original??'')])));setReason('');setTouched(true);setPreview(null);pending.current=null;setError('');setErrors({});}
  async function recalc() {
    const parsed=parseEditor(fields,values,{...structuredClone(resetAll?empty:initial),reason:reason||null});
    setErrors(parsed.errors);
    if(Object.keys(parsed.errors).length||inFlight.current)return;
    inFlight.current=true;setBusy('recalculate');setError('');setConflict(false);
    try {
      const result=await editorRequest<EditorPreview>('editor/preview',{project_id:project.id,scan_revision_id:revision.scan_revision_id,corrections:parsed.corrections});
      setPreview(result);pending.current={key:crypto.randomUUID(),corrections:parsed.corrections};
    }catch(e){setError(e instanceof Error?e.message:'Recalculation failed. Your entries are retained.');}
    finally {setBusy('');inFlight.current=false;}
  }
  async function save() {
    if(!pending.current||!preview||inFlight.current)return;
    inFlight.current=true;setBusy('save');setError('');
    try {
      await editorRequest('editor/revisions',{project_id:project.id,scan_revision_id:revision.scan_revision_id,corrections:pending.current.corrections,
        precondition:{expected_active_revision_id:revision.id,idempotency_key:pending.current.key}});
      await onSaved();setTouched(false);onDirty(false);
    }catch(e){setError(e instanceof Error?e.message:'Saving failed. Retry with this tab open.');setConflict(e instanceof EditorError&&e.status===409);}
    finally{setBusy('');inFlight.current=false;}
  }
  const renderField=(f:EditField)=>{
    const id=`edit-${f.key}`;
    const changed=values[f.key]!==String(f.original??'');
    return <div key={f.key} className="py-3 border-b border-border last:border-0">
      <label htmlFor={id} className="block text-sm font-medium mb-1">{f.label}</label>
      <div className="flex items-center gap-2">
        <input id={id} type="number" min={f.min??0} max={f.max} step={f.integer?1:'any'} value={values[f.key]??''} disabled={!!busy}
          onChange={e=>change(f.key,e.target.value)} aria-invalid={!!errors[f.key]} aria-describedby={`${id}-help`}
          className="min-h-11 w-full min-w-0 rounded-lg border border-border bg-background px-3 text-base tabular-nums focus-visible:outline-2 focus-visible:outline-foreground"/>
        <button type="button" className={editorButton} disabled={!!busy||!changed} onClick={()=>change(f.key,String(f.original??''))} aria-label={`Reset ${f.label}`}>Reset</button>
      </div>
      <p id={`${id}-help`} className={`text-sm mt-1 ${errors[f.key]?'text-red-400':'text-muted-foreground'}`}>
        {errors[f.key]??`${changed?'Edited':original.plan.source==='manual'&&f.provenance!=='Catalog'?'Entered':f.provenance} · Original: ${f.original??'Not read'}`}
      </p>
    </div>;
  };
  return <section aria-labelledby="editor-title" className="border border-border rounded-lg bg-card p-5 sm:p-6">
    <h2 id="editor-title" className="text-xl font-semibold">Correct quantities and prices</h2>
    <p className="text-sm text-muted-foreground mt-2 mb-5">Compare with the original plan. Recalculate to review the changes, then save a new version.</p>
    <p role="status" className="text-sm mb-4">{touched?'Unsaved changes':'Showing saved inputs'}</p>
    {(error||Object.keys(errors).length>0)&&<div ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-red-400 mb-4">
      {error||'Check the highlighted fields.'}{Object.entries(errors).map(([key,msg])=><a key={key} href={`#edit-${key}`} className="block underline">{fields.find(f=>f.key===key)?.label}: {msg}</a>)}
      {conflict&&<p className="mt-2">A newer version may be saved. Copy your entries before reopening the project; this draft has not overwritten it.</p>}
    </div>}
    {source.length>0&&<fieldset disabled={!!busy}><legend className="text-base font-semibold">Source quantities</legend>
      {source.map(renderField)}
    </fieldset>}
    {original.plan.plan_type==='Electrical Plan'&&<p className="text-sm text-muted-foreground mt-3">{original.plan.electrical_review && original.plan.electrical_review.estimate_scope!=='standard'?'Device and box counts are tied to the reviewed assemblies. Replace / rescan the plan to revise them.':'Outlet variants are catalog choices. Switch and AC classifications are not available for editing yet.'}</p>}
    <details className="mt-6"><summary className="min-h-11 cursor-pointer text-base font-semibold">Project material prices (PHP)</summary>
      <p className="text-sm text-muted-foreground my-2">These prices apply only to this project, per the purchase units shown.</p>{priceFields.map(renderField)}
    </details>
    <label htmlFor="edit-reason" className="block text-sm mt-5 mb-2">Reason for changes (optional)</label>
    <textarea id="edit-reason" value={reason} maxLength={2000} disabled={!!busy} onChange={e=>{setReason(e.target.value);setTouched(true);setPreview(null);pending.current=null;}}
      className="w-full rounded-lg bg-background border border-border p-3 text-base focus-visible:outline-2 focus-visible:outline-foreground" rows={2}/>
    <div className="flex flex-wrap gap-2 mt-4">
      <button className={`${editorButton} bg-foreground text-background hover:opacity-90 hover:bg-foreground`} disabled={!!busy} onClick={recalc}>{busy==='recalculate'?'Recalculating…':'Recalculate'}</button>
      <button className={editorButton} disabled={!!busy} onClick={reset}>Reset to original</button>
    </div>
    {preview&&<div className="mt-6 border-t border-border pt-5" aria-live="polite">
      <h3 className="font-semibold">Review before saving</h3>
      <p className="text-sm mt-2">Saved: {money(revision.estimate.grand_total)} → Revised: {money(preview.estimate.grand_total)}</p>
      <p className="text-sm text-muted-foreground mt-1">Difference: {money(preview.estimate.grand_total-revision.estimate.grand_total)}</p>
      <ul className="text-sm my-3 space-y-1">{preview.estimate.line_items.filter(li=>{const old=revision.estimate.line_items.find(x=>x.item_id===li.item_id);return !old||old.quantity!==li.quantity||old.unit_price!==li.unit_price;}).map(li=>{
        const old=revision.estimate.line_items.find(x=>x.item_id===li.item_id);
        return <li key={li.item_id}>{li.item_id}: {old?.quantity??0} → {li.quantity} {li.unit??''}; {money(old?.unit_price??0)} → {money(li.unit_price)}</li>;
      })}{revision.estimate.line_items.filter(li=>!preview.estimate.line_items.some(x=>x.item_id===li.item_id)).map(li=><li key={li.item_id}>{li.item_id}: {li.quantity} → 0 (removed)</li>)}</ul>
      <button className={`${editorButton} bg-foreground text-background hover:bg-foreground hover:opacity-90`} disabled={!!busy||conflict} onClick={save}>{busy==='save'?'Saving…':error?'Retry saving':'Save changes'}</button>
      <p className="text-sm text-muted-foreground mt-3">The saved total and export update only after a successful save.</p>
    </div>}
  </section>;
}
