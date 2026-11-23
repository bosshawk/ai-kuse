# /// script
# dependencies = ["pyyaml>=6"]
# ///
import json, re, sys, glob, pathlib, hashlib, collections, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]/"scripts"))
from ai_kuse_core import load_terms, scan, visible_lines
THIS = "29995342-7580-4b23-ba0d-373114a33f7a"
JA = re.compile(r"[ぁ-んァ-ヴ一-龥]")

def ai_docs():
    root = pathlib.Path.home()/".claude/projects"; seen=set(); docs=[]
    for f in root.rglob("*.jsonl"):
        sess = f.parent.name if f.parent.name == "subagents" else f.stem
        if THIS in str(f): continue
        for line in open(f, encoding="utf-8", errors="ignore"):
            try: d=json.loads(line)
            except: continue
            if d.get("type")!="assistant": continue
            for c in d.get("message",{}).get("content",[]) or []:
                t=None
                if c.get("type")=="text": t=c.get("text")
                elif c.get("type")=="tool_use" and c.get("name")=="Write" and str(c.get("input",{}).get("file_path","")).endswith(".md"):
                    t=c["input"].get("content")
                if not t or len(JA.findall(t))<30: continue
                h=hashlib.md5(t.encode()).hexdigest()
                if h in seen: continue
                seen.add(h); docs.append((str(f.relative_to(root)).split("/")[0]+"/"+f.stem, t))
    return docs

def qiita(k):
    docs=[]
    for f in sorted(glob.glob(f"qiita/{k}_*.json")):
        for it in json.load(open(f)): docs.append((it["id"], it["body"]))
    return docs

def clean(t): return "\n".join(m for _,m,_ in visible_lines(t))
corp = {"AI": ai_docs(), "H2021": qiita("h"), "Q2026": qiita("n")}
corp = {k:[(s,clean(t)) for s,t in v] for k,v in corp.items()}
size = {k: sum(len(JA.findall(t)) for _,t in v) for k,v in corp.items()}
print("size(ja chars):", size, {k:len(v) for k,v in corp.items()})

# 1) 登録済みのワードの頻度（10万字あたり）と、出た文書の数
terms = load_terms()
res = {}
for k,v in corp.items():
    cnt=collections.Counter(); df=collections.defaultdict(set)
    for s,t in v:
        for h in scan(t, terms):
            cnt[h.term.id]+=1; df[h.term.id].add(s)
    res[k]=(cnt,{i:len(x) for i,x in df.items()})
rows=[]
for t in terms:
    r=[t.id,t.term]
    for k in corp:
        c=res[k][0][t.id]; r+= [c, round(c/size[k]*1e5,2), res[k][1].get(t.id,0)]
    rows.append(r)
json.dump({"size":size,"docs":{k:len(v) for k,v in corp.items()},"registered":rows}, open("registered.json","w"), ensure_ascii=False)
print(f"{'id':12}{'term':6} AI(n,/10万字,docs)   H2021   Q2026")
for r in sorted(rows,key=lambda r:-r[3]): print(f"{r[0]:12}{r[1]:6} {r[2:5]}  {r[5:8]}  {r[8:11]}")

# 2) 新しい候補: 漢字の連なり（2〜4字）とカタカナ語。AI に多く、2021年の人の記事に少ないもの
TOK = re.compile(r"[一-龥々]{2,4}(?![一-龥々])|(?<![一-龥々])[一-龥々]{2,4}|[ァ-ヴー]{3,}")
def toks(v):
    cnt=collections.Counter(); df=collections.defaultdict(set)
    for s,t in v:
        for m in set(re.findall(r"[一-龥々]+|[ァ-ヴー]{3,}", t)) and re.findall(r"[一-龥々]+|[ァ-ヴー]{3,}", t):
            if 2<=len(m)<=4 or (m[0] in "ァアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヴ" and len(m)>=3):
                cnt[m]+=1; df[m].add(s)
    return cnt,df
A,Adf=toks(corp["AI"]); H,Hdf=toks(corp["H2021"]); N,Ndf=toks(corp["Q2026"])
out=[]
for w,c in A.items():
    if c<20 or len(Adf[w])<10: continue
    a=c/size["AI"]*1e6; h=(H[w]+0.5)/size["H2021"]*1e6; n=N[w]/size["Q2026"]*1e6
    out.append((round(math.log2(a/h),2), w, c, len(Adf[w]), H[w], N[w], round(a,1), round(h,1), round(n,1)))
out.sort(reverse=True)
json.dump(out, open("discover.json","w"), ensure_ascii=False)
print("\n候補（log2 比 AI/H2021、AI件数、AI文書数、H件数、Q2026件数）上位300")
for o in out[:300]: print(o[0],o[1],o[2],o[3],o[4],o[5])
