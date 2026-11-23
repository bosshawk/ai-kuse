import json,re,collections,random
corp=json.load(open("corp_clean.json")); size=json.load(open("tok_counts.json"))["size"]
SOU_OK=("サービス|アプリケーション|アプリ|プレゼンテーション|ドメイン|インフラストラクチャ|インフラ|データアクセス|ビジネスロジック|永続化|"
 "ネットワーク|トランスポート|データリンク|物理|セッション|中間|隠れ|出力|入力|全結合|畳み込み|プーリング|ノーマライゼーション|正規化|埋め込み|"
 "最終|上位|下位|最上位|経営|読者|若年|ベテラン|富裕|中間|利用者|顧客|ユーザー|イノベータ|アーリーアダプタ|得意|苦手|"
 "ユースケース|リポジトリ|コントローラ|コントローラー|Web|DB|ストレージ|Attention|Conv|Transformer")
SOU_EN=r"(?i:domain|usecase|use ?case|infra|infrastructure|repository|controller|service|presentation|application|ui|view|model|persistence|adapters?|ports?|handler|interface|web|db)"
sou_ex=[re.compile(p) for p in [
 rf"({SOU_OK})層", rf"{SOU_EN}\s?層",
 r"階層|深層|表層|地層|断層|成層|層別|層状|高層|一層|大層|重層|多層防御|上層部|下層階級|オゾン層|電離層",
 r"[0-9０-９二三四五六七八九十N]+\s?層(構造|構成|アーキテクチャ|システム|の(MLP|ニューラル|CNN|全結合|LSTM))",
 r"(第[0-9０-９一二三四五六七]+|L[1-7])層"]]
sou=re.compile(r"層")
KATA=[r"」型",r"(ホスト|リモートホスト|リモート|ローカル|パス|サブドメイン|アップロード|インストール|アプリインストール|相談|巻き込み|カタログ|トークン|プロキシ)型",
 r"(?<![一-龥々ァ-ヴーA-Za-z])(く|れ|ち|み|え|け|せ|び|り|い)型(?![一-龥々])",r"型で(縛|固め|しば)",r"[0-9０-９一二三四五六七八九]つの型(?!で)",
 r"(話|節|章|文章|説明|報告|会話|運用|体制|チーム|進め方|書き方|構成|失敗|成功|議論|提案|設計|作業|返答|応答の仕方)の型(?![一-龥々])",r"(よく見た|よくある|共通の|いつもの)型"]
kata=[re.compile(p) for p in KATA]
def sou_hits(line):
    ex=[m.span() for p in sou_ex for m in p.finditer(line)]
    return [m for m in sou.finditer(line) if not any(s<=m.start()<e for s,e in ex)]
def kata_hits(line):
    return [m for p in kata for m in p.finditer(line)]
random.seed(11)
for name,fn in (("層",sou_hits),("型",kata_hits)):
    print("=====",name)
    for k in ("AI","H2021","Q2026"):
        hs=[]
        for t in corp[k]:
            for line in t.splitlines():
                for m in fn(line): hs.append(line[max(0,m.start()-18):m.end()+10].strip())
        print(f"■ {k}: {len(hs)}（10万字 {len(hs)/size[k]*1e5:.2f}）")
        random.shuffle(hs)
        for h in hs[:10 if k!='Q2026' else 4]: print("   …"+h)
