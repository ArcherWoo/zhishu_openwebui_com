# 本地 NLTK 数据说明

这个目录专门用来放本地 `nltk_data`。

当前项目已经做了适配，默认会把仓库根目录下的 `nltk_data` 当成 `NLTK_DATA` 搜索路径，并默认设置：

- `NLTK_DATA=<项目根目录>/nltk_data`
- `AUTO_DOWNLOAD_NLTK=False`

也就是说，只要你把需要的 NLTK 数据完整放到这个目录里，程序启动时就会优先走本地文件，不再每次尝试联网下载。

目前为了兼容 Open WebUI 里的文档解析链路，至少建议准备下面两个资源：

- `tokenizers/punkt_tab`
- `taggers/averaged_perceptron_tagger_eng`

如果你们是内网环境，而且目标是“尽量一次准备齐，别后面再报缺包”，那我建议不要只下这两个，最好把下面 README 里“推荐顺手一起下”的常用资源也一起准备好。

## 一、最终应该放成什么样

你最终需要把目录放成这样：

```text
open-webui-main/
├─ nltk_data/
│  ├─ README.md
│  ├─ tokenizers/
│  │  └─ punkt_tab/
│  │     └─ english/
│  │        ├─ abbrev_types.txt
│  │        ├─ collocations.tab
│  │        ├─ ortho_context.tab
│  │        └─ sent_starters.txt
│  └─ taggers/
│     └─ averaged_perceptron_tagger_eng/
│        ├─ averaged_perceptron_tagger_eng.classes.json
│        ├─ averaged_perceptron_tagger_eng.tagdict.json
│        └─ averaged_perceptron_tagger_eng.weights.json
```

注意：

1. 不要只放压缩包，必须解压成目录结构。
2. 不要多套一层目录。
3. `punkt_tab` 和 `averaged_perceptron_tagger_eng` 这两个目录名尽量保持完全一致。

## 二、最推荐的傻瓜式做法

最稳妥的方式是：

1. 在一台能访问外网的电脑上，临时安装 Python。
2. 用 NLTK 官方下载器把资源下载到一个单独目录。
3. 把下载好的整个目录拷贝回公司内网。
4. 放到当前项目根目录下的 `nltk_data/`。

这样最不容易漏文件，也不需要你手动一个个点网页下载。

## 三、外网电脑上怎么下

### 方法 A：用 Python 命令下载

这是最推荐的方法。

先在外网电脑上打开终端，进入一个你方便操作的目录。

执行：

```bash
python -m pip install nltk
```

如果你只想满足当前 Open WebUI 上传文档解析的最低要求，执行：

```bash
python -c "import nltk; nltk.download('punkt_tab', download_dir='nltk_data'); nltk.download('averaged_perceptron_tagger_eng', download_dir='nltk_data')"
```

如果你想按“宁可多准备一点”的方式一次多下，推荐直接执行下面这条：

```bash
python -c "import nltk; targets = ['punkt_tab', 'averaged_perceptron_tagger_eng', 'stopwords', 'wordnet', 'omw-1.4', 'words', 'maxent_ne_chunker_tab', 'gazetteers', 'names', 'nonbreaking_prefixes', 'udhr', 'swadesh', 'sinica_treebank', 'jeita', 'knbc']; [nltk.download(t, download_dir='nltk_data') for t in targets]"
```

上面这条命令的思路是：

- 先把 Open WebUI 当前最可能用到的基础包下齐
- 再把常见英文资源一起补上
- 再把你提到的中文、日语方向里，当前 NLTK 里比较常见、并且本机这版确实存在的资源一起补上

这样后面如果你们自己还有别的 NLTK 脚本、实验代码或者一些语言处理小工具，也更不容易因为少一个资源再卡住。

执行完成后，你当前目录下会出现一个 `nltk_data/` 文件夹。

它里面应该至少有：

```text
nltk_data/
├─ tokenizers/
│  └─ punkt_tab/
└─ taggers/
   └─ averaged_perceptron_tagger_eng/
```

### 方法 B：打开 NLTK 图形下载器

如果你更喜欢点界面，也可以这样：

```bash
python
```

然后在 Python 里输入：

```python
import nltk
nltk.download()
```

接着：

1. 打开下载窗口后，设置下载目录为你自己新建的 `nltk_data` 文件夹。
2. 先搜索并下载：
   - `punkt_tab`
   - `averaged_perceptron_tagger_eng`
3. 再搜索并下载下面这些常用资源：
   - `stopwords`
   - `wordnet`
   - `omw-1.4`
   - `words`
   - `maxent_ne_chunker_tab`
   - `gazetteers`
   - `names`
   - `nonbreaking_prefixes`
   - `udhr`
   - `swadesh`
4. 如果你也想把中文、日语方向顺手准备好，再继续下载：
   - `sinica_treebank`
   - `jeita`
   - `knbc`
5. 下载完成后退出。

## 四、推荐你至少准备哪些包

为了避免“只差一个包又报错”，这里我按用途分成几组。

### 1. 当前 Open WebUI 基本必下

这两个是当前这版项目里最关键的：

- `punkt_tab`
- `averaged_perceptron_tagger_eng`

如果少了它们，聊天里上传文件触发 `unstructured` 解析时，最容易直接报错。

### 2. 推荐顺手一起下的常用包

这一组不是当前 Open WebUI 上传链路的硬性必需，但非常建议一起下，原因是它们在 NLTK 生态里很常见，很多示例、脚本和后续分析代码都会顺手用到：

- `stopwords`
  - 常用停用词表，做清洗、过滤、关键词分析时经常会用到。
- `wordnet`
  - 英文词汇语义资源，很多英文 NLP 示例都会依赖它。
- `omw-1.4`
  - Open Multilingual WordNet，多语言词网数据，通常和 `wordnet` 一起准备更稳。
- `words`
  - 英文词表，某些分词、命名实体或词典类示例会用到。
- `maxent_ne_chunker_tab`
  - 英文命名实体识别相关资源。
- `gazetteers`
  - 地名、人名等词表类资源。
- `names`
  - 常见英文名字语料。
- `nonbreaking_prefixes`
  - 一些分句、分词相关流程可能会用到的前缀规则数据。
- `udhr`
  - 多语言《世界人权宣言》语料，属于很常见的多语言示例数据。
- `swadesh`
  - 多语言基础词表，做一些跨语言小实验时常见。

如果你不想一点点挑，最省事的做法就是把这一组和上面的必下包一起都准备好。

### 3. 英文、中文、日语、韩语怎么准备

#### 英文

英文是 NLTK 支持最完整、最常见的方向，推荐至少准备：

- `punkt_tab`
- `averaged_perceptron_tagger_eng`
- `stopwords`
- `wordnet`
- `omw-1.4`
- `words`
- `maxent_ne_chunker_tab`
- `gazetteers`
- `names`
- `nonbreaking_prefixes`

#### 中文

如果你希望 README 里把中文方向也顺手覆盖上，推荐再加：

- `sinica_treebank`
- `udhr`
- `swadesh`
- `omw-1.4`

说明：

1. `sinica_treebank` 是当前这版 NLTK 里我确认存在的中文相关语料。
2. `udhr`、`swadesh`、`omw-1.4` 属于多语言资源，对中文也有帮助。
3. 但请注意，NLTK 对中文并不是它最强的主场。如果你们以后要做更重的中文分词、词性标注、NER，通常还是专门中文工具更合适。
4. 对于当前 Open WebUI 文件上传解析这条链路来说，中文并没有一个额外“必须先下”的 NLTK 包；核心问题还是前面的 `punkt_tab` 和 `averaged_perceptron_tagger_eng`。

#### 日语

如果你想把日语也顺手准备上，推荐再加：

- `jeita`
- `knbc`
- `udhr`
- `swadesh`
- `omw-1.4`

说明：

1. `jeita` 和 `knbc` 是当前这版 NLTK 里确实存在的日语相关语料。
2. 它们更偏语料和实验用途，不是当前 Open WebUI 上传解析的必需项。
3. 如果你们公司后面会做一些日语文本实验，顺手一起下会更省事。

#### 韩语

韩语这里要特别说明一下：

1. 我当前核对的这版 NLTK 本地资源里，没有看到一个像英文 `punkt_tab` / `averaged_perceptron_tagger_eng` 那样常见、明确、专门给韩语准备的基础包。
2. 所以如果你的目标只是保证当前 Open WebUI 文件上传别报错，不需要为了“韩语”额外硬找一个韩语专属 NLTK 包。
3. 对韩语方向，建议至少准备这些通用多语言资源：
   - `udhr`
   - `swadesh`
   - `omw-1.4`
4. 如果以后你们要认真做韩语分词、词法分析或句法处理，通常也会更建议用专门的韩语 NLP 工具，而不是只靠 NLTK。
## 五、下载完以后怎么拷回内网

假设你在外网电脑上已经得到了这样的目录：

```text
nltk_data/
├─ tokenizers/
└─ taggers/
```

接下来你只需要把整个 `nltk_data` 文件夹拷贝到当前项目根目录即可。

假设你的项目目录是：

`C:\Users\ArcherWoo\Desktop\open-webui-main\open-webui-main`

那么最终应放到：

`C:\Users\ArcherWoo\Desktop\open-webui-main\open-webui-main\nltk_data`

也就是说，最终路径应该长这样：

```text
C:\Users\ArcherWoo\Desktop\open-webui-main\open-webui-main\nltk_data\tokenizers\punkt_tab\english\...
C:\Users\ArcherWoo\Desktop\open-webui-main\open-webui-main\nltk_data\taggers\averaged_perceptron_tagger_eng\...
```

## 六、放好以后怎么启动

放好以后，回到项目根目录执行：

```bash
python start.py
```

或者你平时用生产启动方式的话：

```bash
python start_prod.py
```

当前仓库已经默认会把根目录 `nltk_data` 作为 `NLTK_DATA` 搜索路径，并关闭 `AUTO_DOWNLOAD_NLTK`，所以不需要你额外再配这两个环境变量。

## 七、怎么判断是不是已经识别成功

最简单的判断方式：

1. 程序可以正常启动。
2. 上传会触发文档解析的文件时，不再报缺少 `punkt_tab` 或 `averaged_perceptron_tagger_eng`。
3. 日志里不再反复出现 NLTK 下载失败的联网报错。

如果你想手动检查，可以在项目根目录执行：

```bash
python -c "import os, nltk; print(os.environ.get('NLTK_DATA')); print(nltk.data.find('tokenizers/punkt_tab/english')); print(nltk.data.find('taggers/averaged_perceptron_tagger_eng'))"
```

如果能正常打印出路径，没有报错，通常就说明已经放对了。

## 八、最常见的错误

### 1. 只下载了一个压缩包，没有解压

错误示例：

```text
nltk_data/
└─ punkt_tab.zip
```

这样通常不行。

正确做法是解压成目录结构。

### 2. 多套了一层目录

错误示例：

```text
nltk_data/
└─ nltk_data/
   ├─ tokenizers/
   └─ taggers/
```

这样路径会错一层。

正确的是：

```text
nltk_data/
├─ tokenizers/
└─ taggers/
```

### 3. 只放了 `punkt_tab`，没放 `averaged_perceptron_tagger_eng`

有些场景只会先报 `punkt_tab`，但后面某些文档解析流程还会继续用到词性标注器。

所以建议两个一起准备，不要只放一个。

### 4. 放错到别的目录

当前仓库默认用的是项目根目录下这个位置：

```text
open-webui-main/nltk_data
```

不是：

- `backend/nltk_data`
- `backend/data/nltk_data`
- 用户目录下随便某个 `nltk_data`

虽然 NLTK 本身支持多个搜索路径，但为了避免混乱，最建议你就按当前这个仓库约定来放。

## 九、最短操作版

如果你只想看最短步骤，就按下面做：

1. 在外网电脑执行：

```bash
python -m pip install nltk
python -c "import nltk; targets = ['punkt_tab', 'averaged_perceptron_tagger_eng', 'stopwords', 'wordnet', 'omw-1.4', 'words', 'maxent_ne_chunker_tab', 'gazetteers', 'names', 'nonbreaking_prefixes', 'udhr', 'swadesh', 'sinica_treebank', 'jeita', 'knbc']; [nltk.download(t, download_dir='nltk_data') for t in targets]"
```

2. 把生成出来的整个 `nltk_data/` 文件夹拷回当前项目根目录。
3. 确认里面至少有：
   - `tokenizers/punkt_tab`
   - `taggers/averaged_perceptron_tagger_eng`
4. 如果你是按“宁可多准备一点”的方式下的，再确认还包含：
   - `corpora/stopwords`
   - `corpora/wordnet`
   - `corpora/omw-1.4`
   - `corpora/udhr`
   - `corpora/swadesh`
   - `corpora/sinica_treebank`
   - `corpora/jeita`
   - `corpora/knbc`
   - `chunkers/maxent_ne_chunker_tab`
5. 回到项目根目录执行：

```bash
python start.py
```

## 十、补充说明

如果后面你们内网环境还有别的 NLTK 资源报缺失，也可以继续按同样方式下载，并放到这个 `nltk_data/` 目录里。

也就是说，这个目录以后就是你们项目统一的本地 NLTK 数据目录。 
