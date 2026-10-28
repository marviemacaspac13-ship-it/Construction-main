import {authHeaders} from './supabase';
import type {RecalculatedEstimate} from './estimate';
import type {EstimateCorrections, PriceSnapshot, SourceQuantityOverrides} from './estimate-input';
const base=import.meta.env.VITE_SCAN_API_URL??'http://localhost:8000';
export class EditorError extends Error {constructor(message:string,public status:number){super(message);}}
export async function editorRequest<T>(route:string,body:unknown):Promise<T> {
  const response=await fetch(`${base}/api/estimate/${route}`,{method:'POST',headers:{...await authHeaders(),'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json().catch(()=>null);
  if(!response.ok) throw new EditorError(typeof data?.detail==='string'?data.detail:`Could not complete this request (${response.status}). Your entries are retained.`,response.status);
  return data;
}
export type ManualInputs={quantities:SourceQuantityOverrides;width_m?:number;length_m?:number;exterior_wall_m?:number;interior_wall_m?:number;doors?:number;windows?:number;confirmed:boolean};
export type EditorPreview=RecalculatedEstimate;
export type CorrectionPayload={project_id:string;scan_revision_id:string;corrections:EstimateCorrections};
export type ManualPayload={project_id:string;asset_id:string;inputs:ManualInputs;prices?:PriceSnapshot};
