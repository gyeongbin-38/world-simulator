#!/usr/bin/env python3
"""Small real llama.cpp protocol qualification for EXP-STIG-001-R3."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, platform, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from alifelm.experiments import stigmergy as s
from alifelm.experiments import action_codec as codec

_spec=importlib.util.spec_from_file_location('stig_runner',ROOT/'tools/exp_stig_001.py')
_runner=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_runner)


class ConstrainedServer(_runner.Server):
    """R3-only transport extension; the frozen R2 runner remains unchanged."""
    def generate(self, prompt, seed, generation, *, grammar=None):
        if grammar is None:
            return super().generate(prompt, seed, generation)
        started = time.monotonic()
        payload = {**generation, "prompt": prompt.decode("utf-8"), "seed": seed, "grammar": grammar}
        request = urllib.request.Request(self.url + "/completion", data=s.encode(payload),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
        if not isinstance(result.get("content"), str) or result.get("truncated", False):
            raise RuntimeError("invalid runtime response or context truncation")
        result["observed_wall_seconds"] = time.monotonic() - started
        return result["content"].encode(), result


def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def encode(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=Path); ap.add_argument('--server',required=True,type=Path); ap.add_argument('--models',required=True,nargs=2,type=Path); ap.add_argument('--port',type=int,default=18971); args=ap.parse_args()
 out=args.output.resolve()
 if out.exists() and any(out.iterdir()): raise SystemExit('qualification output already exists')
 out.mkdir(parents=True,exist_ok=True)
 generation={"temperature":0.0,"top_k":1,"top_p":1.0,"min_p":0.0,"repeat_penalty":1.0,"n_predict":128,"cache_prompt":False,"stream":False}
 runtime={"context":4096,"gpu_layers":12,"threads":4,"parallel":1,"request_timeout_seconds":900,"model_load_timeout_seconds":600}
 records=[]; totals={"generations":0,"completed_generations":0,"exactly_one_object":0,"parser_valid_candidates":0,"gateway_valid_candidates":0,"generation_runtime_failures":0,"parser_failures":0,"kernel_rejections":0}
 policies={c:codec.policy(c) for c in 'ABC'}
 started=time.monotonic()
 for mi,model in enumerate(args.models):
  model=Path(model).resolve(strict=True)
  server_model=Path('E:/'+str(model).split('/mnt/e/',1)[1]) if str(model).startswith('/mnt/e/') else model
  server=ConstrainedServer(args.server.resolve(strict=True),server_model,runtime,out/f'server-{mi}.log',args.port)
  try:
   for ci,c in enumerate('ABC'):
    cas=s.FileSystemArtifactStore(out/'cas')
    state=s.initial_state(f'QUAL-R3-{mi}-{c}',c,cas)
    actor=s.AGENTS[ci]
    prompt=s.render(state,actor,cas)
    totals['generations']+=1
    rec={"model_index":mi,"model_path":str(model),"model_sha256":sha(model),"condition":c,"actor":actor,"grammar_policy_id":codec.POLICY_ID,"grammar_sha256":policies[c]['grammar_sha256'],"prompt_sha256":hashlib.sha256(prompt).hexdigest()}
    try:
     raw,response=server.generate(prompt,1000+mi*10+ci,generation,grammar=policies[c]['grammar'])
     totals['completed_generations']+=1
     rec.update({"raw_sha256":hashlib.sha256(raw).hexdigest(),"raw_length":len(raw),"raw_text":raw.decode('utf-8','replace'),"response":response})
     try:
      candidate=codec.strict_candidate(raw,c); totals['exactly_one_object']+=1; totals['parser_valid_candidates']+=1; rec['parser']='PASS'
      try:s.validate(state,actor,candidate,cas); totals['gateway_valid_candidates']+=1; rec['gateway']='PASS'
      except Exception as e: totals['kernel_rejections']+=1; rec.update({'gateway':'REJECTED','gateway_error':type(e).__name__+': '+str(e)})
     except Exception as e:
      totals['parser_failures']+=1; rec.update({'parser':'REJECTED','parser_error':type(e).__name__+': '+str(e)})
    except Exception as e:
     totals['generation_runtime_failures']+=1; rec.update({'generation':'FAILED','generation_error':type(e).__name__+': '+str(e)})
    records.append(rec)
  finally: server.close()
 report={"status":"PASS" if (totals['completed_generations']==totals['generations']==totals['exactly_one_object']==totals['parser_valid_candidates'] and totals['generation_runtime_failures']==totals['parser_failures']==0) else "FAIL","phase":"CODEC_QUALIFICATION_NOT_BEHAVIOR","codec_policy_id":codec.POLICY_ID,"policies":{c:{k:v for k,v in p.items() if k!='grammar'} for c,p in policies.items()},"generation":generation,"runtime":runtime,"server":{"path":str(args.server.resolve()),"sha256":sha(args.server)},"models":[{"path":str(Path(m).resolve()),"sha256":sha(m)} for m in args.models],"records":records,"totals":totals,"elapsed_seconds":time.monotonic()-started,"python":sys.version,"platform":platform.platform()}
 report['manifest_digest']=hashlib.sha256(encode({k:v for k,v in report.items() if k!='manifest_digest'})).hexdigest()
 (out/'qualification.json').write_bytes(encode(report)); print(json.dumps({"status":report['status'],"totals":totals,"manifest_digest":report['manifest_digest']},indent=2))
 if report['status']!='PASS':raise SystemExit(2)
if __name__=='__main__':main()
