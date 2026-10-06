const assert=require('node:assert/strict');
const api=require('../site/js/api-client.js');
(async()=>{
  assert.deepEqual(await api.readJSON(new Response('{"ok":true,"photos":[]}'),'/backend/api/studio/library?token=SECRET'),{ok:true,photos:[]});
  for(const [body,status,code] of [
    ['<!doctype html><h1>Not found</h1>',404,'api_missing'],
    ['<!doctype html><h1>Login</h1>',200,'invalid_response'],
    ['upstream unavailable',503,'invalid_response'],
    ['{"ok":',200,'invalid_response'],
    ['null',200,'invalid_response'],
    ['[]',200,'invalid_response'],
    ['{"ok":false,"error":"API route unavailable"}',404,'api_missing']
  ]){
    await assert.rejects(api.readJSON(new Response(body,{status}),'/backend/api/studio/library?token=SECRET'),e=>{
      assert.equal(e.code,code);assert.equal(e.status,status);assert.equal(e.path,'/backend/api/studio/library');
      assert.ok(!/JSON.parse|Unexpected token|doctype|SECRET/.test(e.message));return true;
    });
  }
  await assert.rejects(api.readJSON(new Response('{"error":"Sign in again"}',{status:403}),'/api/photos'),/Sign in again/);
  const oldFetch=global.fetch;global.fetch=async()=>{throw new TypeError('Failed to fetch');};
  try{await assert.rejects(api.request('/api/photos?api_key=SECRET'),e=>e.code==='network_error'&&!e.message.includes('SECRET'));}finally{global.fetch=oldFetch;}
  console.log('API JSON, HTML failures, auth, malformed responses and network errors passed.');
})().catch(e=>{console.error(e);process.exit(1);});
