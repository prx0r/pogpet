/* Offline functional checks of the real TypeScript extension, no LLM calls.
   Run: NODE_PATH=pi/node_modules node tests/test_pi_cards.cjs
   (typescript + typebox resolve from the vendored pi workspace.) */
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 // Execute the actual injected shim: URL-string calls must carry identity
 // headers with both a plain header object and a Headers instance.
 const shim=require('node:child_process').execFileSync('python3',['-c',
  "import ast,json; from pathlib import Path; tree=ast.parse(Path('bridge/llm_bridge.py').read_text()); node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='inject' for t in n.targets)); print(eval(compile(ast.Expression(node.value),'shim','eval'),{'json':json,'TOKEN':'test-bridge-token'}).decode())"
 ],{cwd:path.join(__dirname,'..'),encoding:'utf8'}).trim().replace(/^<script>|<\/script>$/g,'');
 let outgoing=[];const window={fetch:async(i,o)=>{outgoing.push({i,o});return {};}};
 require('node:vm').runInNewContext(shim,{window,Headers,Request,localStorage:{getItem:k=>({'pogpet.owner':'pog_pi_tests','pogpet.ownersig':'test-bound-signature','pogpet.apikey':'test-user-key'})[k]}});
 await window.fetch('/api/ai/chat',{method:'POST'});
 assert.equal(outgoing[0].o.headers['X-Figg-Owner'],'pog_pi_tests');
 assert.equal(outgoing[0].o.headers['X-Owner-Sig'],'test-bound-signature');
 assert.equal(outgoing[0].o.headers['X-API-Key'],'test-user-key');
 await window.fetch('/backend/api/accounts',{method:'POST',headers:new Headers({'Content-Type':'application/json'})});
 assert.equal(outgoing[1].o.headers.get('X-Owner-Sig'),'test-bound-signature');
 assert.equal(outgoing[1].o.headers.get('Content-Type'),'application/json');
 await window.fetch('https://example.invalid/api/chat',{});
 assert.equal(outgoing[2].o.headers,undefined);
 const ts=require('typescript');process.env.FIGG_OWNER='pog_pi_tests';process.env.FIGG_OWNER_SIG='test-bound-signature';process.env.FIGG_API_KEY='';process.env.FIGG_API_TOKEN='local-service-test';
 const source=fs.readFileSync(path.join(__dirname,'../pi/.pi/extensions/figgsite.ts'),'utf8');
 const result=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true});
 assert.equal(result.diagnostics.length,0);
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pi-cards-test-'));
 try{
  const modulePath=path.join(dir,'extension.mjs');
  fs.writeFileSync(modulePath,result.outputText.replace(/from "typebox"/g,'from '+JSON.stringify(pathToFileURL(require.resolve('typebox')).href)));
  const tools=new Map();(await import(pathToFileURL(modulePath).href)).default({registerTool:t=>tools.set(t.name,t)});
  for(const name of ['library','save','scene','render','job','cutout','reserve'])assert(tools.has('figg_card_'+name));
  let requests=[];
  global.fetch=async(url,init)=>{requests.push({url,init});return new Response(JSON.stringify({ok:true}),{status:200,headers:{'Content-Type':'application/json'}});};
  const run=(name,args)=>tools.get('figg_card_'+name).execute('call-id',args);
  await run('library',{});assert.equal(requests.length,3);
  for(const r of requests){assert.equal(new URL(r.url).searchParams.get('owner'),'pog_pi_tests');assert.equal(r.init.headers['X-Owner-Sig'],'test-bound-signature');}
  await run('save',{spec:{template:'typography',headline:'From Pi'}});
  assert.equal(JSON.parse(requests.at(-1).init.body).owner,'pog_pi_tests');
  await run('scene',{design_id:'card_test',revision:2});assert.equal(new URL(requests.at(-1).url).searchParams.get('revision'),'2');
  await run('render',{design_id:'card_test',revision:2,kind:'motion'});
  assert.equal(JSON.parse(requests.at(-1).init.body).revision,2);
  await run('job',{job_id:'job_test'});await run('cutout',{photo_id:'photo_test',crop:[0,0,1,1]});
  await run('reserve',{design_id:'card_test',revision:2,idempotency_key:'reserve-from-pi-123'});assert.equal(JSON.parse(requests.at(-1).init.body).qty,1);
  const before=requests.length;const denied=await run('library',{owner:'pog_foreign'});assert(denied.details.error);assert.equal(requests.length,before);
  await tools.get('figg_studio_state').execute('legacy',{});assert.equal(new URL(requests.at(-1).url).searchParams.get('owner'),'pog_pi_tests');
  console.log('PASS: fetch shim identity headers; 7 card tools; bound GET/POST identity; foreign owner blocked; legacy Studio default preserved.');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
