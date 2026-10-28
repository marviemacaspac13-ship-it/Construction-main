import { authHeaders } from './supabase';

export type FixtureClass = 'WC' | 'LAV' | 'U' | 'FD' | 'CO';
export type FixtureProvider = 'gemini' | 'openrouter' | 'tags';
export const FIXTURE_NAMES: Record<FixtureClass, [string, string]> = {
  WC: ['toilet', 'toilets'], LAV: ['lavatory', 'lavatories'], U: ['urinal', 'urinals'],
  FD: ['floor drain', 'floor drains'], CO: ['cleanout', 'cleanouts'],
};
export const FIXTURE_COLORS: Record<FixtureClass, string> = {
  WC: '#ef4444', LAV: '#3b82f6', U: '#a855f7', FD: '#16a34a', CO: '#d97706',
};
/** A model proposes toilets and lavatories only; a printed-tag review covers every tag priced. */
export function reviewClasses(provider: FixtureProvider | undefined): FixtureClass[] {
  return provider === 'tags' ? ['WC', 'LAV', 'U', 'FD', 'CO'] : ['WC', 'LAV'];
}
export function fixtureSummary(fixtures: FixtureProposal[], classes: FixtureClass[]): string {
  const parts = classes.map(cls => {
    const n = fixtures.filter(f => f.fixture_class === cls).length;
    return `${n} ${FIXTURE_NAMES[cls][n === 1 ? 0 : 1]}`;
  });
  return parts.length < 2 ? parts.join('') : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

export type FixtureProposal = {
  id: string;
  fixture_class: FixtureClass;
  box_2d: [number, number, number, number];
  uncertainty: string | null;
};
export type FixtureProposalResult = {
  available: boolean;
  source_sha256: string;
  image_width: number;
  image_height: number;
  fixtures: FixtureProposal[];
  attempts: {provider: 'gemini' | 'openrouter'; model: string; outcome: string}[];
  provider?: FixtureProvider;
  model?: string;
  limitations: string[];
  receipt: string | null;
  message: string;
};
export type FixtureConfirmation = {receipt: string; confirmed: true; fixtures: FixtureProposal[]};
export type FixtureReview = {
  source_sha256: string; image_width: number; image_height: number;
  provider: FixtureProvider; model: string; prompt_version: string;
  attempts: FixtureProposalResult['attempts']; proposed: FixtureProposal[];
  accepted: FixtureProposal[]; limitations: string[]; confirmed_at: string;
};

export async function proposePlumbing(file: File): Promise<FixtureProposalResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${import.meta.env.VITE_SCAN_API_URL ?? 'http://localhost:8000'}/api/plumbing/proposals`, {
    method: 'POST', headers: await authHeaders(), body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'Could not find fixtures. Please retry the scan.');
  }
  return res.json();
}

export type FixtureBox = FixtureProposal['box_2d'];
export function placeFixtureBox(y:number,x:number,height=40,width=30):FixtureBox {
  const top=Math.max(0,Math.min(1000-height,y-height/2));
  const left=Math.max(0,Math.min(1000-width,x-width/2));
  return [top,left,top+height,left+width];
}
export function moveFixtureBox(box:FixtureBox,dy:number,dx:number):FixtureBox {
  const y=Math.max(-box[0],Math.min(1000-box[2],dy));
  const x=Math.max(-box[1],Math.min(1000-box[3],dx));
  return [box[0]+y,box[1]+x,box[2]+y,box[3]+x];
}
export function resizeFixtureBox(box:FixtureBox,corner:number,y:number,x:number):FixtureBox {
  const result=[...box] as FixtureBox;
  if(corner<2) result[0]=Math.max(0,Math.min(box[2]-3,y));
  else result[2]=Math.min(1000,Math.max(box[0]+3,y));
  if(corner%2===0) result[1]=Math.max(0,Math.min(box[3]-3,x));
  else result[3]=Math.min(1000,Math.max(box[1]+3,x));
  return result;
}

/** Shared by drawing, keyboard edits and confirmation. No confidence interpretation. */
export function fixtureReviewError(fixtures: FixtureProposal[], allowed: FixtureClass[] = reviewClasses('tags')): string {
  if (fixtures.length > 500) return 'Keep no more than 500 fixtures.';
  const ids = new Set<string>();
  for (const fixture of fixtures) {
    const [y1,x1,y2,x2] = fixture.box_2d;
    if (ids.has(fixture.id)) return 'Each fixture needs a unique ID.';
    ids.add(fixture.id);
    if (!allowed.includes(fixture.fixture_class)) return `This review covers ${allowed.map(c => FIXTURE_NAMES[c][1]).join(' and ')} only. Change or remove other fixture types.`;
    if (fixture.box_2d.some(v=>!Number.isFinite(v) || v<0 || v>1000) || y2<=y1 || x2<=x1) return 'Each fixture needs a valid box inside the plan.';
  }
  for (let i=0;i<fixtures.length;i++) for (let j=i+1;j<fixtures.length;j++) {
    const [ay,ax,by,bx]=fixtures[i].box_2d;
    const [cy,cx,dy,dx]=fixtures[j].box_2d;
    const intersection=Math.max(0,Math.min(by,dy)-Math.max(ay,cy))*Math.max(0,Math.min(bx,dx)-Math.max(ax,cx));
    if (intersection/((by-ay)*(bx-ax)+(dy-cy)*(dx-cx)-intersection)>.5) return 'Some fixture boxes overlap. Remove duplicates or adjust their boxes.';
  }
  return '';
}
