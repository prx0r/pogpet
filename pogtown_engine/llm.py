from typing import Protocol
import json,os,urllib.request
class StructuredGenerator(Protocol):
    def generate_json(self,system,user,schema_hint=None)->dict:...
class OpenAICompatibleHTTPGenerator:
    def __init__(self,model,base_url=None,api_key=None,timeout=90):
        self.model=model;self.base_url=(base_url or os.getenv("POGTOWN_LLM_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
        self.api_key=api_key or os.getenv("POGTOWN_LLM_API_KEY","ollama");self.timeout=timeout
    def generate_json(self,system,user,schema_hint=None):
        body={"model":self.model,"messages":[{"role":"system","content":system},{"role":"user","content":user+"\\nReturn ONLY valid JSON. Schema: "+json.dumps(schema_hint or {})}],
              "temperature":.9,"response_format":{"type":"json_object"}}
        req=urllib.request.Request(self.base_url+"/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+self.api_key})
        with urllib.request.urlopen(req,timeout=self.timeout) as r:p=json.load(r)
        return json.loads(p["choices"][0]["message"]["content"])
