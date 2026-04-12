# graphify

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [Türkçe](README.tr-TR.md)

[![CI](https://github.com/safishamsi/graphify/actions/workflows/ci.yml/badge.svg?branch=v4)](https://github.com/safishamsi/graphify/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/graphifyy)](https://pypi.org/project/graphifyy/)
[![Downloads](https://static.pepy.tech/badge/graphifyy/month)](https://pepy.tech/project/graphifyy)
[![Sponsor](https://img.shields.io/badge/sponsor-safishamsi-ea4aaa?logo=github-sponsors)](https://github.com/sponsors/safishamsi)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Safi%20Shamsi-0077B5?logo=linkedin)](https://www.linkedin.com/in/safi-shamsi)

**Yapay zeka kod asistanı için bir beceri (skill).** Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, Aider, OpenClaw, Factory Droid veya Trae üzerinde `/graphify` yazın; dosyalarınızı okur, bir bilgi grafı oluşturur ve farkında olmadığınız yapısal ilişkileri size geri verir. Bir kod tabanını daha hızlı anlayın, mimari kararların ardındaki "neden"i bulun.

Tamamen çok modludur. Kod, PDF, markdown, ekran görüntüsü, diyagram, beyaz tahta fotoğrafı, farklı dillerdeki görseller, video ve ses dosyalarını tek klasöre bırakın; graphify hepsinden kavramları ve ilişkileri çıkarır ve hepsini tek bir grafa bağlar. Videolar, derleminizden türetilen alan-duyarlı bir istem ile Whisper kullanılarak transkribe edilir. tree-sitter AST ile 20 dil desteklenir (Python, JS, TS, Go, Rust, Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, Lua, Zig, PowerShell, Elixir, Objective-C, Julia).

> Andrej Karpathy makaleleri, tweetleri, ekran görüntülerini ve notları attığı bir `/raw` klasörü tutuyor. graphify tam olarak bu probleme verilen cevap: ham dosyaları okumaya göre her sorgu başına 71.5x daha az token, oturumlar arası kalıcı, ne bulduğu ve ne tahmin ettiği konusunda dürüst.

```
/graphify .                        # herhangi bir klasörde çalışır - kod tabanınız, notlarınız, makaleleriniz, her şey
```

```
graphify-out/
├── graph.html       etkileşimli graf - düğümlere tıklayın, arayın, topluluğa göre filtreleyin
├── GRAPH_REPORT.md  tanrı düğümler, şaşırtıcı bağlantılar, önerilen sorular
├── graph.json       kalıcı graf - haftalar sonra tekrar okumadan sorgulayın
└── cache/           SHA256 önbelleği - yeniden çalıştırmalar yalnızca değişen dosyaları işler
```

Grafa dahil etmek istemediğiniz klasörleri dışlamak için bir `.graphifyignore` dosyası ekleyin:

```
# .graphifyignore
vendor/
node_modules/
dist/
*.generated.py
```

Söz dizimi `.gitignore` ile aynıdır. Desenler, graphify'ı çalıştırdığınız klasöre göre göreli dosya yollarıyla eşleşir.

## Nasıl çalışır

graphify üç aşamada çalışır. İlk olarak, deterministik bir AST aşaması kod dosyalarından yapıyı çıkarır (sınıflar, fonksiyonlar, import'lar, çağrı grafları, docstring'ler, gerekçe yorumları) ve hiçbir LLM gerektirmez. İkinci aşamada video ve ses dosyaları, derlemin tanrı düğümlerinden türetilen alan-duyarlı bir istem ile faster-whisper aracılığıyla yerel olarak transkribe edilir; transkriptler önbelleğe alınır, bu nedenle yeniden çalıştırmalar anında biter. Üçüncü aşamada Claude alt ajanları, belgeler, makaleler, görseller ve transkriptler üzerinde paralel olarak çalışarak kavramları, ilişkileri ve tasarım gerekçelerini çıkarır. Sonuçlar bir NetworkX grafına birleştirilir, Leiden topluluk tespiti ile kümelenir ve etkileşimli HTML, sorgulanabilir JSON ve sade dilde bir denetim raporu olarak dışa aktarılır.

**Kümeleme graf-topolojisi tabanlıdır, gömleme (embedding) yoktur.** Leiden, toplulukları kenar yoğunluğuna göre bulur. Claude'un çıkardığı semantik benzerlik kenarları (`semantically_similar_to`, INFERRED olarak işaretli) zaten grafta olduğundan, topluluk tespitini doğrudan etkiler. Graf yapısı benzerlik sinyalinin kendisidir; ayrı bir gömleme adımı veya vektör veritabanına gerek yoktur.

Her ilişki `EXTRACTED` (doğrudan kaynakta bulundu), `INFERRED` (güven skoru ile makul bir çıkarım) veya `AMBIGUOUS` (inceleme için işaretli) etiketlerinden biriyle etiketlenir. Ne bulunduğunu ve ne tahmin edildiğini her zaman bilirsiniz.

## Kurulum

**Gerekenler:** Python 3.10+ ve şunlardan biri: [Claude Code](https://claude.ai/code), [Codex](https://openai.com/codex), [OpenCode](https://opencode.ai), [Cursor](https://cursor.com), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli), [Aider](https://aider.chat), [OpenClaw](https://openclaw.ai), [Factory Droid](https://factory.ai) veya [Trae](https://trae.ai)

```bash
pip install graphifyy && graphify install
```

> **Resmi paket:** PyPI paketinin adı `graphifyy`'dir (`pip install graphifyy` ile kurulur). PyPI üzerinde `graphify*` ile başlayan diğer paketlerin bu proje ile bir ilişkisi yoktur. Tek resmi depo [safishamsi/graphify](https://github.com/safishamsi/graphify)'dir. CLI ve beceri komutu hala `graphify`'dir.

### Platform desteği

| Platform | Kurulum komutu |
|----------|----------------|
| Claude Code (Linux/Mac) | `graphify install` |
| Claude Code (Windows) | `graphify install` (otomatik algılanır) veya `graphify install --platform windows` |
| Codex | `graphify install --platform codex` |
| OpenCode | `graphify install --platform opencode` |
| GitHub Copilot CLI | `graphify install --platform copilot` |
| Aider | `graphify install --platform aider` |
| OpenClaw | `graphify install --platform claw` |
| Factory Droid | `graphify install --platform droid` |
| Trae | `graphify install --platform trae` |
| Trae CN | `graphify install --platform trae-cn` |
| Gemini CLI | `graphify install --platform gemini` |
| Cursor | `graphify cursor install` |

Codex kullanıcılarının ayrıca paralel çıkarım için `~/.codex/config.toml` dosyasındaki `[features]` altında `multi_agent = true` ayarına ihtiyacı vardır. Factory Droid, paralel alt ajan dağıtımı için `Task` aracını kullanır. OpenClaw ve Aider sıralı çıkarım kullanır (bu platformlarda paralel ajan desteği henüz yeni). Trae, paralel alt ajan dağıtımı için Agent aracını kullanır ve PreToolUse kancalarını **desteklemez**; her zaman açık mekanizma AGENTS.md'dir.

Ardından yapay zeka kod asistanınızı açın ve yazın:

```
/graphify .
```

Not: Codex, beceri çağrısı için `/` yerine `$` kullanır, bu yüzden `$graphify .` yazın.

### Asistanınızın her zaman grafı kullanmasını sağlayın (önerilen)

Bir graf oluşturduktan sonra projenizde şunu bir kez çalıştırın:

| Platform | Komut |
|----------|-------|
| Claude Code | `graphify claude install` |
| Codex | `graphify codex install` |
| OpenCode | `graphify opencode install` |
| GitHub Copilot CLI | `graphify copilot install` |
| Aider | `graphify aider install` |
| OpenClaw | `graphify claw install` |
| Factory Droid | `graphify droid install` |
| Trae | `graphify trae install` |
| Trae CN | `graphify trae-cn install` |
| Cursor | `graphify cursor install` |
| Gemini CLI | `graphify gemini install` |

**Claude Code** iki şey yapar: Claude'a mimari soruları yanıtlamadan önce `graphify-out/GRAPH_REPORT.md` dosyasını okumasını söyleyen bir `CLAUDE.md` bölümü yazar ve her Glob ile Grep çağrısından önce tetiklenen bir **PreToolUse kancası** (`settings.json`) kurar. Bir bilgi grafı varsa Claude şunu görür: _"graphify: Bilgi grafı mevcut. Ham dosyaları aramadan önce tanrı düğümler ve topluluk yapısı için GRAPH_REPORT.md'yi okuyun."_ Böylece Claude, her dosyada grep yerine graf üzerinden gezer.

**Codex** `AGENTS.md` dosyasına yazar ve ayrıca `.codex/hooks.json` içinde her Bash aracı çağrısından önce tetiklenen bir **PreToolUse kancası** kurar; Claude Code ile aynı her zaman açık mekanizmadır.

**OpenCode** `AGENTS.md` dosyasına yazar ve ayrıca `tool.execute.before` eklentisini (`.opencode/plugins/graphify.js` + `opencode.json` kaydı) kurar; bu eklenti bash aracı çağrılarından önce tetiklenir ve graf mevcut olduğunda graf hatırlatmasını araç çıktısına enjekte eder.

**Cursor** `.cursor/rules/graphify.mdc` dosyasını `alwaysApply: true` ile yazar; Cursor bunu her konuşmaya otomatik olarak dahil eder, kancaya gerek yoktur.

**Gemini CLI** beceriyi `~/.gemini/skills/graphify/SKILL.md`'ye kopyalar, bir `GEMINI.md` bölümü yazar ve `.gemini/settings.json` içinde dosya okuma aracı çağrılarından önce tetiklenen bir `BeforeTool` kancası kurar; Claude Code ile aynı her zaman açık mekanizmadır.

**Aider, OpenClaw, Factory Droid ve Trae** aynı kuralları proje kök dizininizdeki `AGENTS.md` dosyasına yazar. Bu platformlar araç kancalarını desteklemediği için her zaman açık mekanizma AGENTS.md'dir.

**GitHub Copilot CLI** beceriyi `~/.copilot/skills/graphify/SKILL.md`'ye kopyalar. Kurulum için `graphify copilot install` komutunu çalıştırın.

Kaldırmak için eşleşen kaldırma komutunu kullanın (örneğin `graphify claude uninstall`).

**Her zaman açık mod ile açık tetikleme arasındaki fark nedir?**

Her zaman açık kanca, bir sayfalık tanrı düğümler, topluluklar ve şaşırtıcı bağlantılar özetini içeren `GRAPH_REPORT.md` dosyasını yüzeye çıkarır. Asistanınız dosya aramadan önce bunu okur, bu sayede anahtar kelime eşleşmesi yerine yapı üzerinden gezer. Bu, günlük soruların çoğunu karşılar.

`/graphify query`, `/graphify path` ve `/graphify explain` daha derine iner: ham `graph.json` üzerinde adım adım gezer, düğümler arasındaki kesin yolları izler ve kenar düzeyinde ayrıntıyı (ilişki tipi, güven skoru, kaynak konumu) yüzeye çıkarır. Bunları, genel bir yönlendirme yerine graftan belirli bir sorunun yanıtlanmasını istediğinizde kullanın.

Şu şekilde düşünün: her zaman açık kanca asistanınıza bir harita verir. `/graphify` komutları ise haritayı hassas bir şekilde gezmesini sağlar.

## LLM ile `graph.json` kullanımı

`graph.json`, bir kerede istem içine yapıştırılmak üzere tasarlanmamıştır. Yararlı akış şudur:

1. Üst düzey bakış için `graphify-out/GRAPH_REPORT.md` ile başlayın.
2. Yanıtlamak istediğiniz belirli soru için daha küçük bir alt graf almak üzere `graphify query` kullanın.
3. Bu odaklanmış çıktıyı asistanınıza tam ham derlemi boşaltmak yerine verin.

Örneğin, bir projede graphify çalıştırdıktan sonra:

```bash
graphify query "auth akışını göster" --graph graphify-out/graph.json
graphify query "DigestAuth'u Response'a ne bağlıyor?" --graph graphify-out/graph.json
```

Çıktı düğüm etiketlerini, kenar tiplerini, güven etiketlerini, kaynak dosyaları ve kaynak konumlarını içerir. Bu, onu bir LLM için iyi bir ara bağlam bloğu yapar:

```text
Soruyu yanıtlamak için bu graf sorgu çıktısını kullanın. Tahmin yerine
graf yapısını tercih edin ve mümkün olduğunda kaynak dosyaları referans gösterin.
```

Asistanınız araç çağrısını veya MCP'yi destekliyorsa, metin yapıştırmak yerine grafı doğrudan kullanın. graphify, `graph.json`'u bir MCP sunucusu olarak sunabilir:

```bash
python -m graphify.serve graphify-out/graph.json
```

Bu, asistana `query_graph`, `get_node`, `get_neighbors` ve `shortest_path` gibi tekrarlanan sorgular için yapılandırılmış graf erişimi sağlar.

<details>
<summary>Manuel kurulum (curl)</summary>

```bash
mkdir -p ~/.claude/skills/graphify
curl -fsSL https://raw.githubusercontent.com/safishamsi/graphify/v4/graphify/skill.md \
  > ~/.claude/skills/graphify/SKILL.md
```

`~/.claude/CLAUDE.md` dosyasına ekleyin:

```
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - herhangi bir girdiden bilgi grafı. Tetikleyici: `/graphify`
Kullanıcı `/graphify` yazdığında, başka bir şey yapmadan önce Skill aracını `skill: "graphify"` ile çağırın.
```

</details>

## Kullanım

```
/graphify                          # geçerli dizinde çalıştırır
/graphify ./raw                    # belirli bir klasörde çalıştırır
/graphify ./raw --mode deep        # daha agresif INFERRED kenar çıkarımı
/graphify ./raw --update           # yalnızca değişen dosyaları yeniden çıkarır, mevcut grafa birleştirir
/graphify ./raw --directed         # yönlü graf oluşturur (kenar yönünü korur: kaynak→hedef)
/graphify ./raw --cluster-only     # mevcut graf üzerinde kümelemeyi yeniden çalıştırır, yeniden çıkarım yoktur
/graphify ./raw --no-viz           # HTML'i atlar, sadece rapor + JSON üretir
/graphify ./raw --obsidian                          # Obsidian vault da üretir (isteğe bağlı)
/graphify ./raw --obsidian --obsidian-dir ~/vaults/myproject  # vault'u belirli bir dizine yazar

/graphify add https://arxiv.org/abs/1706.03762        # bir makale getirir, kaydeder, grafı günceller
/graphify add https://x.com/karpathy/status/...       # bir tweet getirir
/graphify add <video-url>                              # sesi indirir, transkribe eder, grafa ekler
/graphify add https://... --author "Name"             # orijinal yazarı etiketler
/graphify add https://... --contributor "Name"        # derleme eklenen kişiyi etiketler

/graphify query "attention'ı optimizer'a ne bağlıyor?"
/graphify query "attention'ı optimizer'a ne bağlıyor?" --dfs   # belirli bir yolu izler
/graphify query "attention'ı optimizer'a ne bağlıyor?" --budget 1500  # N token ile sınırlar
/graphify path "DigestAuth" "Response"
/graphify explain "SwinTransformer"

/graphify ./raw --watch            # dosyalar değiştikçe grafı otomatik eşitler (kod: anında, belgeler: bildirim)
/graphify ./raw --wiki             # ajan tarayabilir wiki oluşturur (index.md + topluluk başına makale)
/graphify ./raw --svg              # graph.svg dışa aktarır
/graphify ./raw --graphml          # graph.graphml dışa aktarır (Gephi, yEd)
/graphify ./raw --neo4j            # Neo4j için cypher.txt üretir
/graphify ./raw --neo4j-push bolt://localhost:7687    # çalışan bir Neo4j örneğine doğrudan gönderir
/graphify ./raw --mcp              # MCP stdio sunucusunu başlatır

# git kancaları - platform-bağımsız, commit ve branch değişiminde grafı yeniden oluşturur
graphify hook install
graphify hook uninstall
graphify hook status

# her zaman açık asistan talimatları - platform-özgü
graphify claude install            # CLAUDE.md + PreToolUse kancası (Claude Code)
graphify claude uninstall
graphify codex install             # AGENTS.md (Codex)
graphify opencode install          # AGENTS.md + tool.execute.before eklentisi (OpenCode)
graphify cursor install            # .cursor/rules/graphify.mdc (Cursor)
graphify cursor uninstall
graphify gemini install            # GEMINI.md + BeforeTool kancası (Gemini CLI)
graphify gemini uninstall
graphify copilot install           # beceri dosyası (GitHub Copilot CLI)
graphify copilot uninstall
graphify aider install             # AGENTS.md (Aider)
graphify aider uninstall
graphify claw install              # AGENTS.md (OpenClaw)
graphify droid install             # AGENTS.md (Factory Droid)
graphify trae install              # AGENTS.md (Trae)
graphify trae uninstall
graphify trae-cn install           # AGENTS.md (Trae CN)
graphify trae-cn uninstall

# grafı doğrudan terminalden sorgulayın (yapay zeka asistanı gerekmez)
graphify query "attention'ı optimizer'a ne bağlıyor?"
graphify query "auth akışını göster" --dfs
graphify query "CfgNode nedir?" --budget 500
graphify query "..." --graph path/to/graph.json
```

Herhangi bir dosya türü karışımıyla çalışır:

| Tür | Uzantılar | Çıkarım |
|-----|-----------|---------|
| Kod | `.py .ts .js .jsx .tsx .go .rs .java .c .cpp .rb .cs .kt .scala .php .swift .lua .zig .ps1 .ex .exs .m .mm .jl` | tree-sitter üzerinden AST + çağrı grafı + docstring/yorum gerekçesi |
| Belgeler | `.md .txt .rst` | Claude üzerinden kavramlar + ilişkiler + tasarım gerekçesi |
| Office | `.docx .xlsx` | Markdown'a dönüştürülüp Claude üzerinden çıkarılır (`pip install graphifyy[office]` gerektirir) |
| Makaleler | `.pdf` | Alıntı madenciliği + kavram çıkarımı |
| Görseller | `.png .jpg .webp .gif` | Claude vision - ekran görüntüleri, diyagramlar, herhangi bir dil |
| Video / Ses | `.mp4 .mov .mkv .webm .avi .m4v .mp3 .wav .m4a .ogg` | faster-whisper ile yerel olarak transkribe edilir, transkript Claude çıkarımına beslenir (`pip install graphifyy[video]` gerektirir) |
| YouTube / URL'ler | herhangi bir video URL'si | yt-dlp ile ses indirilir, ardından aynı Whisper boru hattı çalışır (`pip install graphifyy[video]` gerektirir) |

## Video ve ses derlemi

Video veya ses dosyalarını kod ve belgelerin yanına derleme klasörünüze bırakın, graphify bunları otomatik olarak alır:

```bash
pip install 'graphifyy[video]'   # tek seferlik kurulum
/graphify ./my-corpus            # bulduğu video/ses dosyalarını transkribe eder
```

Bir YouTube videosunu (veya herhangi bir genel video URL'sini) doğrudan ekleyin:

```bash
/graphify add <video-url>
```

yt-dlp yalnızca sesi indirir (hızlı, küçük), Whisper bunu yerel olarak transkribe eder ve transkript diğer belgelerinizle aynı çıkarım boru hattına beslenir. Transkriptler `graphify-out/transcripts/` içinde önbelleğe alınır, bu yüzden yeniden çalıştırmalar zaten transkribe edilmiş dosyaları atlar.

Teknik içerikte daha iyi doğruluk için daha büyük bir model kullanın:

```bash
/graphify ./my-corpus --whisper-model medium
```

Ses makinenizden hiç çıkmaz. Tüm transkripsiyon yerel olarak çalışır.

## Ne elde edersiniz

**Tanrı düğümler** - en yüksek dereceli kavramlar (her şeyin üzerinden geçtiği noktalar)

**Şaşırtıcı bağlantılar** - birleşik skora göre sıralanır. Kod-makale kenarları kod-kod kenarlarından daha yüksek sıralanır. Her sonuç bir cümlelik sade bir neden içerir.

**Önerilen sorular** - grafın benzersiz şekilde yanıtlayabileceği 4-5 soru

**"Neden"** - docstring'ler, satır içi yorumlar (`# NOTE:`, `# IMPORTANT:`, `# HACK:`, `# WHY:`) ve belgelerden tasarım gerekçeleri `rationale_for` düğümleri olarak çıkarılır. Yalnızca kodun ne yaptığı değil, neden bu şekilde yazıldığı.

**Güven skorları** - her INFERRED kenarın bir `confidence_score` değeri vardır (0.0-1.0). Yalnızca neyin tahmin edildiğini değil, modelin ne kadar emin olduğunu da bilirsiniz. EXTRACTED kenarlar her zaman 1.0'dır.

**Semantik benzerlik kenarları** - yapısal bağlantısı olmayan dosya-üstü kavramsal bağlar. Birbirini çağırmadan aynı problemi çözen iki fonksiyon, koddaki bir sınıf ile aynı algoritmayı anlatan bir makaledeki kavram.

**Hiperkenarlar** - ikili kenarların ifade edemediği, 3 veya daha fazla düğümü bağlayan grup ilişkileri. Ortak bir protokolü uygulayan tüm sınıflar, bir auth akışındaki tüm fonksiyonlar, tek bir fikri oluşturan bir makale bölümündeki tüm kavramlar.

**Token kıyaslaması** - her çalıştırmadan sonra otomatik olarak yazdırılır. Karışık bir derlemde (Karpathy depoları + makaleler + görseller): ham dosyaları okumaya göre sorgu başına **71.5x** daha az token. İlk çalıştırma çıkarır ve grafı oluşturur (bu token harcar). Sonraki her sorgu ham dosyalar yerine kompakt grafı okur; kazanımlar orada birikir. SHA256 önbelleği sayesinde yeniden çalıştırmalar yalnızca değişen dosyaları yeniden işler.

**Otomatik eşitleme** (`--watch`) - arka plan terminalinde çalıştırın, kod tabanınız değiştikçe graf kendini günceller. Kod dosyası kayıtları anında yeniden oluşturma tetikler (yalnızca AST, LLM yok). Belge/görsel değişiklikleri LLM yeniden geçişi için `--update` çalıştırmanızı bildirir.

**Git kancaları** (`graphify hook install`) - post-commit ve post-checkout kancalarını kurar. Graf, her commit ve her branch değişiminden sonra otomatik olarak yeniden oluşturulur. Yeniden oluşturma başarısız olursa kanca sıfır olmayan bir kodla çıkar, bu sayede git hata mesajını yüzeye çıkarır, sessizce devam etmez. Arka plan süreci gerekmez.

**Wiki** (`--wiki`) - topluluk ve tanrı düğüm başına Wikipedia tarzı markdown makaleleri, bir `index.md` giriş noktasıyla birlikte. Herhangi bir ajanı `index.md`'ye yönlendirin ve bilgi tabanını JSON ayrıştırmak yerine dosya okuyarak gezebilsin.

## İşlenmiş örnekler

| Derlem | Dosyalar | Azaltma | Çıktı |
|--------|----------|---------|-------|
| Karpathy depoları + 5 makale + 4 görsel | 52 | **71.5x** | [`worked/karpathy-repos/`](worked/karpathy-repos/) |
| graphify kaynağı + Transformer makalesi | 4 | **5.4x** | [`worked/mixed-corpus/`](worked/mixed-corpus/) |
| httpx (sentetik Python kütüphanesi) | 6 | ~1x | [`worked/httpx/`](worked/httpx/) |

Token azaltması derlem boyutu ile ölçeklenir. 6 dosya zaten bir bağlam penceresine sığar, dolayısıyla orada graf değeri sıkıştırma değil, yapısal netliktir. 52 dosyada (kod + makaleler + görseller) 71x'in üzerine çıkarsınız. Her `worked/` klasörü ham girdi dosyalarını ve gerçek çıktıyı (`GRAPH_REPORT.md`, `graph.json`) içerir, böylece kendiniz çalıştırıp sayıları doğrulayabilirsiniz.

## Gizlilik

graphify, belge, makale ve görseller için semantik çıkarım için dosya içeriklerini yapay zeka kod asistanınızın temel model API'sine gönderir: Anthropic (Claude Code), OpenAI (Codex) veya platformunuzun kullandığı hangi sağlayıcı ise o. Kod dosyaları yerel olarak tree-sitter AST üzerinden işlenir, kod için dosya içerikleri makinenizden ayrılmaz. Video ve ses dosyaları faster-whisper ile yerel olarak transkribe edilir, ses makinenizden hiç çıkmaz. Hiçbir telemetri, kullanım takibi veya analitik yoktur. Tek ağ çağrıları, kendi API anahtarınızla çıkarım sırasında platformunuzun model API'sinedir.

## Teknoloji yığını

NetworkX + Leiden (graspologic) + tree-sitter + vis.js. Semantik çıkarım Claude (Claude Code), GPT-4 (Codex) veya platformunuzun çalıştırdığı hangi model ise o üzerinden yapılır. Video transkripsiyonu faster-whisper + yt-dlp ile (isteğe bağlı, `pip install graphifyy[video]`). Neo4j gerekmez, sunucu gerekmez, tamamen yerel çalışır.

## Sırada ne var

graphify graf katmanıdır. Bunun üzerine [Penpax](https://safishamsi.github.io/penpax.ai) inşa ediyoruz: toplantılarınızı, tarayıcı geçmişinizi, dosyalarınızı, e-postalarınızı ve kodunuzu sürekli güncellenen tek bir bilgi grafına bağlayan cihaz-üstü bir dijital ikiz. Bulut yok, verilerinizle eğitim yok. [Bekleme listesine katılın.](https://safishamsi.github.io/penpax.ai)

## Yıldız geçmişi

[![Star History Chart](https://api.star-history.com/svg?repos=safishamsi/graphify&type=Date)](https://star-history.com/#safishamsi/graphify&Date)

<details>
<summary>Katkıda bulunma</summary>

**İşlenmiş örnekler** en fazla güven oluşturan katkıdır. `/graphify`'ı gerçek bir derlemde çalıştırın, çıktıyı `worked/{slug}/` altına kaydedin, grafın neyi doğru ve neyi yanlış bulduğunu değerlendiren dürüst bir `review.md` yazın, bir PR gönderin.

**Çıkarım hataları** - girdi dosyası, önbellek girişi (`graphify-out/cache/`) ve neyin kaçırıldığı veya uydurulduğu ile bir issue açın.

Modül sorumlulukları ve nasıl dil ekleneceği için [ARCHITECTURE.md](ARCHITECTURE.md) dosyasına bakın.

</details>
