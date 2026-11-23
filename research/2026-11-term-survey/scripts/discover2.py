# /// script
# dependencies = ["pyyaml>=6"]
# ///
import re,json,collections,math,sys,pathlib
src=open("analyze.py").read().split("# 1) 登録済み")[0].split("# ///",2)[-1]
exec(src)
def toks(v):
    cnt=collections.Counter(); df=collections.defaultdict(set)
    for s,t in v:
        for m in re.findall(r"[一-龥々]+|[ァ-ヴー]+", t):
            if re.fullmatch(r"[一-龥々]{2,4}",m) or re.fullmatch(r"[ァ-ヴー]{3,}",m):
                cnt[m]+=1; df[m].add(s)
    return cnt,{k:len(x) for k,x in df.items()}
A,Ad=toks(corp["AI"]); H,Hd=toks(corp["H2021"]); N,Nd=toks(corp["Q2026"])
json.dump({"A":A,"Ad":Ad,"H":H,"Hd":Hd,"N":N,"Nd":Nd,"size":size}, open("tok_counts.json","w"), ensure_ascii=False)
json.dump({k:[t for _,t in v] for k,v in corp.items()}, open("corp_clean.json","w"), ensure_ascii=False)
out=[]
for w,c in A.items():
    if c<10 or Ad.get(w,0)<6 or N.get(w,0)<10 or Nd.get(w,0)<8: continue
    a=c/size["AI"]*1e6; h=(H.get(w,0)+0.5)/size["H2021"]*1e6; n=N[w]/size["Q2026"]*1e6
    ra=math.log2(a/h); rn=math.log2(n/h)
    if ra>=1.6 and rn>=1.3: out.append((round(min(ra,rn),2),w,c,Ad[w],H.get(w,0),N[w],Nd[w],round(ra,1),round(rn,1)))
out.sort(reverse=True)
json.dump(out,open("discover2.json","w"),ensure_ascii=False)
print(len(out))
for o in out: print(*o)
