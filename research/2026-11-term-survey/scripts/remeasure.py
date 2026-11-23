# /// script
# dependencies = ["pyyaml>=6"]
# ///
import json,re,sys,pathlib,collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]/"scripts"))
from ai_kuse_core import load_terms, scan
corp=json.load(open("corp_clean.json")); size=json.load(open("tok_counts.json"))["size"]
terms=load_terms(); rows={}
for k,docs in corp.items():
    for t in docs:
        seen=set()
        for h in scan(t,terms):
            r=rows.setdefault(h.term.id,{c:[0,0] for c in corp}); r[k][0]+=1
            if h.term.id not in seen: r[k][1]+=1; seen.add(h.term.id)
out=[]
for t in terms:
    r=rows.get(t.id,{c:[0,0] for c in corp})
    per={k:round(r[k][0]/size[k]*1e5,2) for k in corp}
    out.append({"id":t.id,"term":t.term,"severity":t.severity,**{f"{k}_n":r[k][0] for k in corp},**{f"{k}_per100k":per[k] for k in corp},**{f"{k}_docs":r[k][1] for k in corp}})
json.dump({"size_ja_chars":size,"rows":out},open("remeasure.json","w"),ensure_ascii=False,indent=1)
for o in out: print(f"{o['id']:12} {o['term']:6} AI {o['AI_per100k']:6} ({o['AI_n']})  H {o['H2021_per100k']:5} ({o['H2021_n']})  Q {o['Q2026_per100k']:5} ({o['Q2026_n']})")
