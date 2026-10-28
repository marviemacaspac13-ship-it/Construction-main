import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {PGlite} from '@electric-sql/pglite';

test('private plan migration: ownership, immutable version linkage, retries and cleanup', async t => {
  const db = new PGlite();
  const owner='10000000-0000-0000-0000-000000000001', other='10000000-0000-0000-0000-000000000002';
  const project='20000000-0000-0000-0000-000000000001', foreign='20000000-0000-0000-0000-000000000002';
  const upload='30000000-0000-0000-0000-000000000001', refused='30000000-0000-0000-0000-000000000002', abandoned='30000000-0000-0000-0000-000000000003';
  await db.exec(`CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;
    CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
      $$ SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
    GRANT USAGE ON SCHEMA auth TO authenticated; GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated;
    CREATE TABLE projects(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users,
      name text,description text,plan_type text,status text,grand_total numeric,line_items jsonb,unmatched_detections jsonb,
      extraction jsonb,error_message text,created_at timestamptz DEFAULT now(),updated_at timestamptz DEFAULT now());
    ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
    CREATE POLICY owner_all ON projects TO authenticated USING(user_id=auth.uid()) WITH CHECK(user_id=auth.uid());
    GRANT ALL ON projects TO authenticated;
    INSERT INTO auth.users VALUES('${owner}'),('${other}');
    INSERT INTO projects(id,user_id,name,plan_type,status) VALUES('${project}','${owner}','First','Floor Plan','processing'),
      ('${foreign}','${other}','Other','Floor Plan','processing');
    CREATE SCHEMA storage;
    CREATE TABLE storage.buckets(id text PRIMARY KEY,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
    CREATE TABLE storage.objects(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),bucket_id text,name text);
    ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
    GRANT USAGE ON SCHEMA storage TO anon,authenticated;
    GRANT SELECT,INSERT,UPDATE,DELETE ON storage.objects TO anon,authenticated;
    CREATE POLICY preexisting_broad_policy ON storage.objects FOR ALL TO authenticated USING(true) WITH CHECK(true);
    INSERT INTO storage.objects(bucket_id,name) VALUES('trace-plans','private.png'),('unrelated','other.png');
  `);
  for (const name of ['003_estimate_revisions.sql','004_revision_conflict_response.sql','005_private_plan_assets.sql','006_correction_editor.sql']) {
    await db.exec(await readFile(new URL('../supabase/migrations/'+name,import.meta.url),'utf8'));
  }
  const rpc = async (sql,args=[]) => {
    await db.exec('SET ROLE service_role');
    try {return (await db.query(sql,args)).rows[0]?.value;} finally {await db.exec('RESET ROLE');}
  };
  const asUser = async (who,sql,args=[]) => {
    await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)",[who]);
    await db.exec('SET ROLE authenticated');
    try {return await db.query(sql,args);} finally {await db.exec('RESET ROLE');}
  };
  const metadata={source_sha256:'a'.repeat(64),original_filename:'plan.png',media_type:'image/png',byte_size:1024,pixel_width:100,pixel_height:200};
  const begin=(id=upload,who=owner,pid=project,meta=metadata)=>rpc('SELECT begin_plan_upload($1,$2,$3,$4) AS value',[who,pid,id,JSON.stringify(meta)]);
  const finish=(id=upload,who=owner,pid=project)=>rpc('SELECT finish_plan_upload($1,$2,$3) AS value',[who,pid,id]);
  let asset;
  await t.test('bucket stays private and restrictive policy defeats a broad existing grant',async()=>{
    assert.equal((await db.query("SELECT public FROM storage.buckets WHERE id='trace-plans'")).rows[0].public,false);
    assert.equal((await asUser(owner,"SELECT * FROM storage.objects WHERE bucket_id='trace-plans'")).rows.length,0);
    assert.equal((await asUser(owner,"SELECT * FROM storage.objects WHERE bucket_id='unrelated'")).rows.length,1);
    await assert.rejects(asUser(owner,"INSERT INTO storage.objects(bucket_id,name) VALUES('trace-plans','hack.png')"),/row-level security/);
  });
  await t.test('foreign and missing projects cannot reserve or finalize an upload',async()=>{
    await assert.rejects(begin(upload,other),/project not found/);
    await assert.rejects(finish(upload,other),/project not found/);
    await assert.rejects(begin(upload,owner,foreign),/project not found/);
  });
  await t.test('stable upload ID and original metadata make retries idempotent',async()=>{
    const reserved=await begin();
    assert.equal(reserved.storage_path,`${owner}/${project}/${upload}/original.png`);
    assert.deepEqual(await begin(),reserved);
    await assert.rejects(begin(upload,owner,project,{...metadata,source_sha256:'b'.repeat(64)}),/upload conflict/);
    asset=await finish();
    assert.equal(asset.storage_path,reserved.storage_path);
    assert.equal(asset.pixel_width,100);
    assert.deepEqual(await finish(),asset);
    assert.equal((await begin()).state,'ready');
  });
  await t.test('another owner cannot read metadata or obtain a viewing capability',async()=>{
    assert.equal((await asUser(other,'SELECT * FROM plan_assets')).rows.length,0);
    await assert.rejects(rpc('SELECT owned_plan_asset($1,$2,$3) AS value',[other,project,upload]),/plan not found/);
    assert.deepEqual(await rpc('SELECT owned_plan_asset($1,$2,$3) AS value',[owner,project,upload]),asset);
    await assert.rejects(asUser(owner,'SELECT owned_plan_asset($1,$2,$3)',[owner,project,upload]),/permission denied/);
  });
  const result={original_input:{schema_version:1,rules_version:'test',plan:{plan_type:'Floor Plan'},params:{},prices:{}},
    scan:{source_sha256:metadata.source_sha256},estimate:{plan_type:'Floor Plan',rules_version:'test',grand_total:123,line_items:[]},
    extraction:null,unmatched_detections:[]};
  const savedAsset={...metadata,asset_id:upload};
  const save=(key,expected=null,a=savedAsset)=>rpc('SELECT save_scan_estimate($1,$2,$3,$4,$5,$6) AS value',
    [owner,project,expected,key,JSON.stringify(result),JSON.stringify(a)]);
  let revision;
  await t.test('estimate links the exact uploaded asset and preserves immutable originals',async()=>{
    revision=await save('40000000-0000-0000-0000-000000000001');
    assert.equal((await db.query('SELECT asset_id FROM scan_revisions')).rows[0].asset_id,upload);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM plan_assets')).rows[0].n,1);
    assert.equal(await save('40000000-0000-0000-0000-000000000001'),revision);
    await assert.rejects(save('40000000-0000-0000-0000-000000000002',revision,{...savedAsset,byte_size:42}),/asset differs/);
    await assert.rejects(db.exec("UPDATE plan_assets SET storage_path='changed'"),/immutable/);
  });
  await t.test('correction save is owner-scoped, atomic, immutable and retryable',async()=>{
    const scan=(await db.query('SELECT * FROM scan_revisions')).rows[0];
    const correctionKey='40000000-0000-0000-0000-000000000099';
    const corrections={quantities:{wall_height_m:3.2},unit_prices:{},reason:null};
    const edited={...result.estimate,grand_total:456};
    const saveEdit=(who=owner,expected=revision,key=correctionKey,c=corrections,sid=scan.id)=>rpc(
      'SELECT save_corrected_estimate($1,$2,$3,$4,$5,$6,$7,$8) AS value',
      [who,project,sid,expected,key,JSON.stringify(c),JSON.stringify(result.original_input),JSON.stringify(edited)]);
    assert.deepEqual((await rpc('SELECT owned_estimate_scan($1,$2,$3) AS value',[owner,project,scan.id])).original_input,scan.original_input);
    await assert.rejects(rpc('SELECT owned_estimate_scan($1,$2,$3) AS value',[other,project,scan.id]),/scan not found/);
    await assert.rejects(saveEdit(other),/project not found/);
    await assert.rejects(asUser(owner,'SELECT owned_estimate_scan($1,$2,$3)',[owner,project,scan.id]),/permission denied/);
    const originalRevision=revision;
    const saved=await saveEdit();
    assert.equal(await saveEdit(),saved);
    await assert.rejects(saveEdit(owner,originalRevision,correctionKey,{...corrections,reason:'different'}),/key reused/);
    await assert.rejects(saveEdit(owner,originalRevision,'40000000-0000-0000-0000-000000000098'),/revision changed/);
    const reopened=(await asUser(owner,'SELECT * FROM estimate_revisions WHERE id=$1',[saved])).rows[0];
    assert.deepEqual(reopened.corrections,corrections); assert.deepEqual(reopened.estimate,edited);
    assert.equal(reopened.parent_revision_id,originalRevision); assert.equal(reopened.scan_revision_id,scan.id);
    assert.equal((await db.query('SELECT grand_total FROM projects WHERE id=$1',[project])).rows[0].grand_total,'456');
    assert.deepEqual((await db.query('SELECT original_input FROM scan_revisions WHERE id=$1',[scan.id])).rows[0].original_input,result.original_input);
    assert.equal((await asUser(other,'SELECT * FROM estimate_revisions')).rows.length,0);
    revision=saved;
  });
  await t.test('refused-scan originals survive; cleanup only claims stale incomplete uploads',async()=>{
    await begin(refused); await finish(refused); await begin(abandoned);
    await db.exec("UPDATE plan_uploads SET touched_at=now()-interval '2 days'");
    const paths=await rpc('SELECT claim_plan_file_cleanup($1) AS value',[owner]);
    assert.deepEqual(paths,[`${owner}/${project}/${abandoned}/original.png`]);
    assert.deepEqual(await rpc('SELECT claim_plan_file_cleanup($1) AS value',[other]),[]);
    await assert.rejects(begin(abandoned),/upload conflict/);
    await assert.rejects(finish(abandoned),/upload expired/);
    await rpc('SELECT finish_plan_file_cleanup($1,$2) AS value',[owner,paths[0]]);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM plan_assets')).rows[0].n,2);
  });
  await t.test('replacement uploads cannot switch the original under a saved estimate',async()=>{
    const linked=(await db.query('SELECT a.id FROM plan_assets a JOIN scan_revisions s ON s.asset_id=a.id JOIN estimate_revisions e ON e.scan_revision_id=s.id WHERE e.id=$1',[revision])).rows[0];
    assert.equal(linked.id,upload);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM plan_assets')).rows[0].n,2);
  });
  await t.test('project deletion queues all originals and cleanup remains owner scoped',async()=>{
    await asUser(owner,'DELETE FROM projects WHERE id=$1',[project]);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM plan_assets')).rows[0].n,0);
    assert.deepEqual(await rpc('SELECT claim_plan_file_cleanup($1) AS value',[owner]),[]);
    await db.exec("UPDATE plan_file_cleanup SET created_at=now()-interval '2 days'");
    const paths=await rpc('SELECT claim_plan_file_cleanup($1) AS value',[owner]);
    assert.equal(paths.length,2);
    for(const path of paths) await rpc('SELECT finish_plan_file_cleanup($1,$2) AS value',[owner,path]);
    assert.deepEqual(await rpc('SELECT claim_plan_file_cleanup($1) AS value',[owner]),[]);
  });
  await db.close();
});
