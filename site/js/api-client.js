/* JSON API responses must never be treated as HTML, or as an empty library. */
(function(root){
  'use strict';
  function failure(code,status,path,message){
    var error=new Error(message);error.code=code;error.status=status;error.path=path;
    return error;
  }
  function safePath(url){try{return new URL(url||'/', 'https://oddhobb.com').pathname;}catch(e){return '/';}}
  function unavailable(path){return path.indexOf('/studio/')>=0?'The photo library is temporarily unavailable. Please try again shortly.':'This service is temporarily unavailable. Please try again shortly.';}
  async function readJSON(response,url){
    var path=safePath(url||response.url),status=response.status;
    var text=await response.text(),data;
    try{data=JSON.parse(text);}catch(e){
      throw failure(status===404?'api_missing':'invalid_response',status,path,unavailable(path));
    }
    if(!data||typeof data!=='object'||Array.isArray(data))throw failure('invalid_response',status,path,unavailable(path));
    if(!response.ok){
      var message=(status===401||status===403)?'Your session could not be verified. Reload this page and try again.':unavailable(path);
      if(typeof data.error==='string'&&status!==404&&status<500)message=data.error.slice(0,400);
      throw failure(status===404?'api_missing':'http_error',status,path,message);
    }
    return data;
  }
  async function request(url,options){
    try{return await readJSON(await root.fetch(url,options),url);}catch(e){
      if(!e.code)e=failure('network_error',0,safePath(url),'Could not connect. Please check your connection and try again.');
      if(root.document&&root.CustomEvent)root.document.dispatchEvent(new root.CustomEvent('oddhobb:api-error',{detail:{code:e.code,status:e.status,path:e.path}}));
      throw e;
    }
  }
  var api={request:request,readJSON:readJSON,safePath:safePath};
  if(typeof module!=='undefined')module.exports=api;
  root.OddHobbAPI=api;
})(typeof window==='undefined'?globalThis:window);
