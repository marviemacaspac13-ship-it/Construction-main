import type { EstimateCorrections, EstimateInputSnapshot, SourceQuantityOverrides } from './estimate-input';

export type EditField = { key: string; label: string; original?: number; integer?: boolean; min?: number; max?: number; provenance: string };
export const electricalLabels: Record<string,string> = { OT01:'1-gang outlet · OT01', OT02:'2-gang outlet · OT02', OT03:'3-gang outlet · OT03', CLR01:'Ceiling outlet · CLR01', CLR02:'Ceiling outlet · CLR02', CLR03:'Ceiling outlet · CLR03' };
export const plumbingLabels: Record<string,string> = { water_closet:'Water closets', lavatory:'Lavatories', urinal:'Urinals', floor_drain:'Floor drains', cleanout:'Cleanouts (count only)' };

export function sourceFields(input: EstimateInputSnapshot): EditField[] {
  const p=input.plan;
  if(p.electrical_review && p.electrical_review.estimate_scope!=='standard') return [];
  if(p.plan_type==='Floor Plan') {
    const slab=p.concrete.find(e=>e.kind==='slab')??p.concrete_basis?.find(e=>e.kind==='slab');
    const col=p.concrete.find(e=>e.kind==='column')??p.concrete_basis?.find(e=>e.kind==='column');
    return [
      ...(p.walls.length ? [{key:'wall_height_m',label:'All-wall height (m)', original:input.params.default_wall_height_m,min:0.01,max:10,provenance:'Estimated'}] : []),
      ...(slab ? [{key:'slab_area_m2',label:'Slab area (m²)',original:p.concrete.some(e=>e.kind==='slab')?(slab.slab_area_m2 ?? slab.count*(slab.width_m??0)*(slab.length_m??0)):0,provenance:'Estimated'}] : []),
      ...(col ? [{key:'column_count',label:'Columns and linked footings',original:p.concrete.some(e=>e.kind==='column')?col.count:0,integer:true,provenance:col.counted?'Read':'Estimated'}] : []),
    ];
  }
  const labels=p.plan_type==='Electrical Plan'?electricalLabels:plumbingLabels;
  return Object.entries(labels).map(([key,label])=>({key:`${p.plan_type==='Electrical Plan'?'electrical_counts':'plumbing_counts'}.${key}`,label,integer:true,
    original:p.plan_type==='Electrical Plan' ? (p.fixtures.some(f=>f.item_id===key)?p.fixtures.filter(f=>f.item_id===key).reduce((n,f)=>n+f.count,0):undefined) : p.fixture_tags[key],
    provenance:p.source==='manual'?'Entered':'Read'}));
}

export function fieldValue(f: EditField, corrections: EstimateCorrections): string {
  const [group,key]=f.key.split('.');
  const value=group==='price'?corrections.unit_prices[key]:key
    ? (corrections.quantities[group as 'electrical_counts'|'plumbing_counts'] as Record<string,number>|undefined)?.[key]
    : corrections.quantities[group as 'wall_height_m'|'slab_area_m2'|'column_count'];
  return String(value ?? f.original ?? '');
}

export function parseEditor(fields: EditField[], values: Record<string,string>, previous: EstimateCorrections) {
  const corrections: EstimateCorrections=structuredClone(previous);
  const errors: Record<string,string>={};
  for(const f of fields) {
    const raw=(values[f.key]??'').trim();
    const value=Number(raw);
    if(!raw && f.original===undefined) {
      const [group,key]=f.key.split('.');
      if(key) delete (corrections.quantities[group as 'electrical_counts'|'plumbing_counts'] as Record<string,number>|undefined)?.[key];
      continue;
    }
    if(!raw || !Number.isFinite(value) || value<(f.min??0) || (f.max!==undefined && value>f.max) || (f.integer && !Number.isSafeInteger(value))) {
      errors[f.key]=f.integer?'Enter a whole count of zero or more.':`Enter a number ${f.min?`from ${f.min}`:'of zero or more'}${f.max?` to ${f.max}`:''}.`; continue;
    }
    const [group,key]=f.key.split('.');
    const target=group==='price'?corrections.unit_prices:key
      ? (corrections.quantities[group as 'electrical_counts'|'plumbing_counts'] ??= {})
      : corrections.quantities;
    const prop=key??group;
    const record=target as Record<string,number|undefined>;
    if(value===f.original) delete record[prop]; else record[prop]=value;
  }
  return {corrections,errors};
}

export function csvEstimate(rows: {item_id:string;item_name:string;unit:string|null;unit_price:number;quantity:number;line_total:number}[]) {
  const cell=(v:string|number)=>`"${String(v).replace(/"/g,'""')}"`;
  return 'Item ID,Material,Unit,Unit Price,Quantity,Line Total\r\n'+rows.map(r=>[r.item_id,r.item_name,r.unit??'',r.unit_price,r.quantity,r.line_total].map(cell).join(',')).join('\r\n');
}
