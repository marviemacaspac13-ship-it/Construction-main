import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '@electric-sql/pglite';
import ts from 'typescript';

const owner = '10000000-0000-0000-0000-000000000001';
const other = '10000000-0000-0000-0000-000000000002';
const project = '20000000-0000-0000-0000-000000000001';
const foreignProject = '20000000-0000-0000-0000-000000000002';
const key = '30000000-0000-0000-0000-000000000001';
const key2 = '30000000-0000-0000-0000-000000000002';
const result = {
  original_input: {schema_version: 1, rules_version: 'test-v1', plan: {plan_type: 'Electrical Plan', fixtures: [{item_id: 'OT01', count: 12}]},
    params: {default_wall_height_m: 2.7}, prices: {captured_at: '2026-10-10T00:00:00Z', snapshot_id: 'f'.repeat(64), items: [{item_id: 'OT01', price: 50}] }},
  scan: {source_sha256: 'a'.repeat(64), pipeline_version: 'image-v1', method: 'detection'},
  extraction: null, unmatched_detections: [{label: 'UNKNOWN', confidence: .8, bbox: [1,2,3,4]}],
  estimate: {plan_type: 'Electrical Plan', rules_version: 'test-v1', priced_at: '2026-10-10T00:00:00Z',
    line_items: [{item_id: 'OT01', quantity: 12, unit_price: 50, line_total: 600}], grand_total: 600,
    unpriced: [{item_id: 'UTB01', quantity: 12, rule: 'boxes', derivation: 'one per outlet', inputs: {count: 12}}], assumptions: ['Retain me']},
};
const asset = {source_sha256: 'a'.repeat(64), original_filename: 'plan.png', media_type: 'image/png', byte_size: 1024};

test('isolated PostgreSQL revision migration and ownership boundary', async (t) => {
  const db = new PGlite();
  await db.exec(`
    CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;
    CREATE SCHEMA auth;
    CREATE TABLE auth.users(id uuid PRIMARY KEY);
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
      $$ SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
    GRANT USAGE ON SCHEMA auth TO authenticated;
    GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated;
    CREATE TABLE public.projects(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id),
      name text, description text, plan_type text, status text, grand_total numeric, line_items jsonb,
      unmatched_detections jsonb, extraction jsonb, error_message text, created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
    ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
    CREATE POLICY owner_all ON public.projects TO authenticated USING(user_id = auth.uid()) WITH CHECK(user_id = auth.uid());
    GRANT ALL ON public.projects TO authenticated;
    INSERT INTO auth.users VALUES ('${owner}'), ('${other}');
    INSERT INTO public.projects(id, user_id, name, plan_type, status, grand_total, line_items) VALUES
      ('${project}', '${owner}', 'Legacy', 'Electrical Plan', 'completed', 100, '[]'),
      ('${foreignProject}', '${other}', 'Other', 'Electrical Plan', 'completed', 200, '[]');
  `);
  await db.exec(await readFile(new URL('../supabase/migrations/003_estimate_revisions.sql', import.meta.url), 'utf8'));
  await db.exec(await readFile(new URL('../supabase/migrations/004_revision_conflict_response.sql', import.meta.url), 'utf8'));
  const save = async (expected = null, idempotency = key, payload = result, metadata = asset, who = owner, projectId = project) => {
    await db.exec('SET ROLE service_role');
    try {
      const r = await db.query('SELECT public.save_scan_estimate($1,$2,$3,$4,$5,$6) AS id', [who, projectId, expected, idempotency, JSON.stringify(payload), JSON.stringify(metadata)]);
      return r.rows[0].id;
    } finally { await db.exec('RESET ROLE'); }
  };
  const asUser = async (who, sql, values = []) => {
    await db.query("SELECT set_config('request.jwt.claim.sub', $1, false)", [who]);
    await db.exec('SET ROLE authenticated');
    try { return await db.query(sql, values); } finally { await db.exec('RESET ROLE'); }
  };
  let first, second;
  await t.test('legacy rows remain unchanged and readable', async () => {
    const r = await asUser(owner, 'SELECT grand_total, active_revision_id FROM projects');
    assert.equal(r.rows.length, 1); assert.equal(Number(r.rows[0].grand_total), 100); assert.equal(r.rows[0].active_revision_id, null);
  });
  await t.test('atomically retains complete input/output and compatibility summary', async () => {
    first = await save();
    const revision = (await asUser(owner, 'SELECT * FROM estimate_revisions WHERE id=$1', [first])).rows[0];
    assert.deepEqual(revision.estimate, result.estimate);
    assert.deepEqual(revision.effective_input, result.original_input);
    assert.equal(revision.created_by, owner); assert.equal(revision.parent_revision_id, null);
    const scan = (await asUser(owner, 'SELECT * FROM scan_revisions')).rows[0];
    assert.deepEqual(scan.original_input, result.original_input); assert.deepEqual(scan.unmatched_detections, result.unmatched_detections);
    const p = (await asUser(owner, 'SELECT * FROM projects')).rows[0];
    assert.equal(p.active_revision_id, first); assert.equal(Number(p.grand_total), 600);
    assert.deepEqual(p.unmatched_detections, result.unmatched_detections);
  });
  await t.test('lost-response retry returns the same revision with no duplicate records', async () => {
    assert.equal(await save(), first);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM plan_assets')).rows[0].n, 1);
  });
  await t.test('same key with changed content fails', async () => {
    await assert.rejects(save(null, key, {...result, extraction: {changed: true}}), /idempotency key reused/);
  });
  await t.test('second revision links its predecessor and keeps original history', async () => {
    second = await save(first, key2);
    assert.notEqual(second, first);
    const records = (await asUser(owner, 'SELECT id,parent_revision_id FROM estimate_revisions')).rows;
    assert.equal(records.length, 2); assert.equal(records.find(r => r.id === second).parent_revision_id, first);
  });
  await t.test('retry of an older committed save does not rewind active pointer', async () => {
    assert.equal(await save(), first);
    assert.equal((await db.query('SELECT active_revision_id FROM projects WHERE id=$1', [project])).rows[0].active_revision_id, second);
  });
  await t.test('stale tab cannot silently overwrite the newer revision', async () => {
    await assert.rejects(save(first, '30000000-0000-0000-0000-000000000003'), e => e.code === 'PT409' && /active revision changed/.test(e.message));
    assert.equal((await db.query('SELECT count(*)::int AS n FROM estimate_revisions')).rows[0].n, 2);
  });
  await t.test('failed insert rolls back asset, scan, revision and summary together', async () => {
    await assert.rejects(save(second, '30000000-0000-0000-0000-000000000004', {...result, unmatched_detections: null}));
    assert.equal((await db.query('SELECT count(*)::int AS n FROM plan_assets')).rows[0].n, 2);
    assert.equal((await db.query('SELECT active_revision_id FROM projects WHERE id=$1', [project])).rows[0].active_revision_id, second);
  });
  await t.test('owner check also applies to service-role writes', async () => {
    await assert.rejects(save(null, key, result, asset, other), /project not found/);
    await assert.rejects(save(null, key, result, asset, owner, foreignProject), /project not found/);
  });
  await t.test('another owner cannot read assets or revision history', async () => {
    for (const table of ['plan_assets', 'scan_revisions', 'estimate_revisions']) {
      assert.equal((await asUser(other, `SELECT * FROM ${table}`)).rows.length, 0);
    }
  });
  await t.test('browser cannot call trusted RPC or update active pointer/results', async () => {
    await assert.rejects(asUser(owner, 'SELECT public.save_scan_estimate($1,$2,$3,$4,$5,$6)', [owner, project, second, key, JSON.stringify(result), JSON.stringify(asset)]), /permission denied/);
    await assert.rejects(asUser(owner, 'UPDATE projects SET active_revision_id=NULL WHERE id=$1', [project]), /permission denied/);
    await assert.rejects(asUser(owner, 'UPDATE projects SET grand_total=0 WHERE id=$1', [project]), /permission denied/);
    await assert.rejects(asUser(owner, 'INSERT INTO estimate_revisions DEFAULT VALUES'), /permission denied/);
    await assert.rejects(asUser(owner, 'DELETE FROM estimate_revisions'), /permission denied/);
  });
  await t.test('even administrative updates cannot rewrite revisions', async () => {
    await assert.rejects(db.exec("UPDATE estimate_revisions SET estimate='{}'"), /immutable/);
    await assert.rejects(db.exec("UPDATE scan_revisions SET scan='{}'"), /immutable/);
    await assert.rejects(db.exec("UPDATE plan_assets SET original_filename='new.png'"), /immutable/);
  });
  await t.test('rename and project creation still work under column grants', async () => {
    await asUser(owner, "UPDATE projects SET name='Renamed' WHERE id=$1", [project]);
    const r = await asUser(owner, "INSERT INTO projects(name,description,plan_type,status) VALUES('New','','Floor Plan','processing') RETURNING user_id");
    assert.equal(r.rows[0].user_id, owner);
  });
  await t.test('failed scan does not hide a completed legacy or revision result', async () => {
    await db.exec('SET ROLE service_role');
    await db.query('SELECT record_scan_failure($1,$2,$3)', [owner, project, 'Scan failed']);
    await db.query('SELECT record_scan_failure($1,$2,$3)', [other, foreignProject, 'Scan failed']);
    await db.exec('RESET ROLE');
    assert.equal((await db.query('SELECT status FROM projects WHERE id=$1', [project])).rows[0].status, 'completed');
    assert.equal((await db.query('SELECT status FROM projects WHERE id=$1', [foreignProject])).rows[0].status, 'completed');
  });
  await t.test('additive electrical review JSON survives save, reopen and exact retry without a migration', async () => {
    const reviewed = structuredClone(result);
    const proposed = Array.from({length:12}, (_, i) => ({id:`device-${i}`,assembly_id:`assembly-${i}`,
      box_2d:[i*20,10,i*20+10,20],device_class:'convenience_outlet',raw_mark:null,
      adjacent_text:null,socket_configuration:'duplex',gang_count:null,switching_function:null,uncertainty:null}));
    const unsupported = {id:'unsupported',assembly_id:'unsupported',box_2d:[500,500,510,510],
      device_class:'switch',raw_mark:'S3w',adjacent_text:null,socket_configuration:null,
      gang_count:null,switching_function:'three_way',uncertainty:'No approved product mapping'};
    const evidence = {version:'electrical-review-v1',source_sha256:asset.source_sha256,
      image_width:1000,image_height:1000,owner_id:owner,provider:'template',model:'offline-test',
      proposed:[...proposed,unsupported],confirmed_at:'2026-10-26T00:00:00Z',choices:[
        ...proposed.map(observation=>({observation,disposition:'include',selected_sku:null,exclusion_reason:null})),
        {observation:unsupported,disposition:'exclude',selected_sku:null,exclusion_reason:'Explicitly excluded from this estimate; unresolved product and wiring.'}]};
    reviewed.original_input.plan.electrical_review=evidence;
    // Roll back this isolated round-trip so the existing two-revision lifecycle
    // assertions still exercise their original fixture unchanged.
    await db.exec('BEGIN');
    try {
      const reviewedKey='30000000-0000-0000-0000-000000000099';
      const id=await save(second,reviewedKey,reviewed);
      const reopened=(await asUser(owner,'SELECT effective_input,scan_revision_id FROM estimate_revisions WHERE id=$1',[id])).rows[0];
      assert.deepEqual(reopened.effective_input.plan.electrical_review,evidence);
      const scan=(await asUser(owner,'SELECT original_input FROM scan_revisions WHERE id=$1',[reopened.scan_revision_id])).rows[0];
      assert.deepEqual(scan.original_input.plan.electrical_review,evidence);
      assert.equal(await save(second,reviewedKey,reviewed),id);
    } finally { await db.exec('ROLLBACK'); }
  });
  await t.test('owner project deletion cascades without exposing another project', async () => {
    await asUser(other, 'DELETE FROM projects WHERE id=$1', [project]);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM estimate_revisions')).rows[0].n, 2);
    await asUser(owner, 'DELETE FROM projects WHERE id=$1', [project]);
    for (const table of ['plan_assets', 'scan_revisions', 'estimate_revisions']) assert.equal((await db.query(`SELECT count(*)::int AS n FROM ${table}`)).rows[0].n, 0);
  });
  await db.close();
});

test('browser retains exact attempt on failure and handles conflict without rebasing', async () => {
  const source = await readFile(new URL('../src/lib/revision-save.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022}}).outputText;
  const {prepareEstimateSave, submitEstimateSave, EstimateSaveError} = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
  const sourceResult = structuredClone(result);
  const assetId = '50000000-0000-0000-0000-000000000001';
  const attempt = prepareEstimateSave(project, null, sourceResult, {name: 'plan.png', type: 'image/png', size: 1024}, key, assetId);
  assert.equal(attempt.asset.asset_id, assetId);
  sourceResult.estimate.grand_total = 999;
  assert.equal(attempt.result.estimate.grand_total, 600);
  const bodies = [];
  const request = async (_url, options) => { bodies.push(options.body); if (bodies.length === 1) throw new Error('network timeout'); return new Response(JSON.stringify({revision_id: key2})); };
  await assert.rejects(submitEstimateSave(attempt, 'http://test', {Authorization: 'Bearer test'}, request), /network timeout/);
  assert.equal(await submitEstimateSave(attempt, 'http://test', {}, request), key2);
  assert.equal(bodies[0], bodies[1]); assert.deepEqual(attempt.result.estimate.unpriced, result.estimate.unpriced);
  await assert.rejects(submitEstimateSave(attempt, 'http://test', {}, async () => new Response(JSON.stringify({detail: 'Revision changed'}), {status:409})), e => e instanceof EstimateSaveError && e.status === 409);
  assert.equal(attempt.precondition.expected_active_revision_id, null);
});
