# 本地 Embedding 模型说明

这个目录专门用来放本地 embedding 模型。

当前程序已经做了适配，会优先从下面这个路径读取默认 RAG 模型：

`embedding_model/sentence-transformers/all-MiniLM-L6-v2`

也就是说，只要你把模型完整放到这个目录里，程序启动时就会优先走本地文件，不再先去 Hugging Face 下载。

## 一、最终应该放成什么样

你最终需要把目录放成这样：

```text
open-webui-main/
├─ embedding_model/
│  ├─ README.md
│  └─ sentence-transformers/
│     └─ all-MiniLM-L6-v2/
│        ├─ 1_Pooling/
│        │  └─ config.json
│        ├─ config.json
│        ├─ config_sentence_transformers.json
│        ├─ modules.json
│        ├─ model.safetensors
│        ├─ sentence_bert_config.json
│        ├─ special_tokens_map.json
│        ├─ tokenizer.json
│        ├─ tokenizer_config.json
│        ├─ vocab.txt
│        └─ 其他模型原始文件
```

注意：

1. 最稳妥的做法是把 Hugging Face 页面里的整个模型仓库内容原样下载下来。
2. 不要只放 `model.safetensors` 一个文件。
3. `1_Pooling` 这个子目录要保留。
4. 目录名也尽量保持不变，尤其是 `sentence-transformers/all-MiniLM-L6-v2` 这一层路径不要改。

## 二、去哪里下载

模型页面：

`https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2`

文件列表页面：

`https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/main`

## 三、怎么从网站上下载

推荐你在一台能访问外网的电脑上操作，然后再把文件夹拷到公司内网机器。

### 方法 A：网页手动下载

这是最直接、最容易理解的方法。

1. 用浏览器打开模型页面：
   `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2`
2. 进入 `Files and versions` 页面。
3. 把页面里的文件和文件夹按原始结构下载下来。
4. 如果页面里看到子目录，比如 `1_Pooling/`，要点进去，把里面的文件也下载下来。
5. 在你自己的电脑上，手动整理成下面这个目录结构：

```text
embedding_model/
└─ sentence-transformers/
   └─ all-MiniLM-L6-v2/
      ├─ 1_Pooling/
      ├─ config.json
      ├─ config_sentence_transformers.json
      ├─ modules.json
      ├─ model.safetensors
      ├─ sentence_bert_config.json
      ├─ special_tokens_map.json
      ├─ tokenizer.json
      ├─ tokenizer_config.json
      ├─ vocab.txt
      └─ ...
```

### 方法 B：如果网页下载嫌麻烦

如果你在外网电脑上装了 Git 和 Git LFS，也可以先把整个模型仓库拉下来，再拷进来。这样最不容易漏文件。

示例命令：

```bash
git lfs install
git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
```

拉下来以后，把整个 `all-MiniLM-L6-v2` 目录放到：

```text
embedding_model/sentence-transformers/
```

最终仍然要变成：

```text
embedding_model/sentence-transformers/all-MiniLM-L6-v2
```

## 四、下载完以后，内网机器上怎么放

假设你的项目根目录是：

`C:\Users\ArcherWoo\Desktop\open-webui-main\open-webui-main`

那么模型最终应该放到：

`C:\Users\ArcherWoo\Desktop\open-webui-main\open-webui-main\embedding_model\sentence-transformers\all-MiniLM-L6-v2`

你可以这样理解：

1. `embedding_model` 是总目录
2. `sentence-transformers` 是模型作者或命名空间目录
3. `all-MiniLM-L6-v2` 是具体模型目录

只要这三层路径对上，程序就能识别。

## 五、放好以后怎么启动

在项目根目录执行：

```bash
python start.py
```

当前仓库已经默认是离线优先模式，启动时会优先从本地找模型，不会先去 Hugging Face 下载。

## 六、程序怎么识别这个目录

程序现在会优先检查本地目录：

`embedding_model/sentence-transformers/all-MiniLM-L6-v2`

如果这个目录存在，就直接把它当作 embedding 模型路径使用。

所以你不需要再额外配置：

- `HF_HOME`
- `SENTENCE_TRANSFORMERS_HOME`
- `EMBEDDING_MODEL_DIR`

启动脚本已经帮你处理好了。

## 七、怎么判断是不是已经识别成功

启动后，如果程序正常起来，而且没有再出现反复访问 Hugging Face 的报错，通常就说明已经走本地模型了。

如果你想更稳一点，可以重点检查这几件事：

1. 模型目录是不是准确放在：
   `embedding_model/sentence-transformers/all-MiniLM-L6-v2`
2. `all-MiniLM-L6-v2` 下面是不是有多个文件，而不是只有一个权重文件
3. `1_Pooling/config.json` 是否存在
4. `modules.json` 是否存在
5. `model.safetensors` 是否存在

## 八、最常见的错误

### 1. 少了一层目录

错误示例：

```text
embedding_model/all-MiniLM-L6-v2
```

这样不对。

正确的是：

```text
embedding_model/sentence-transformers/all-MiniLM-L6-v2
```

### 2. 只下载了权重文件

错误示例：

```text
all-MiniLM-L6-v2/
└─ model.safetensors
```

这样通常不够，因为 Sentence Transformers 还需要配置文件、tokenizer 文件和 pooling 配置。

### 3. 漏掉 `1_Pooling`

这个目录经常被漏掉，但它对 sentence-transformers 模型是重要的。

### 4. 把文件解压错位置

有些压缩包解开后会多一层目录，例如：

```text
embedding_model/sentence-transformers/all-MiniLM-L6-v2/all-MiniLM-L6-v2/...
```

这种多套了一层也不对。

正确应该是：

```text
embedding_model/sentence-transformers/all-MiniLM-L6-v2/...
```

## 九、最短操作版

如果你只想看最短步骤，就按下面做：

1. 在外网电脑打开：
   `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/main`
2. 把整个模型仓库内容下载完整
3. 放到项目根目录下面这个位置：
   `embedding_model/sentence-transformers/all-MiniLM-L6-v2`
4. 确保 `1_Pooling`、`modules.json`、`config.json`、`model.safetensors`、tokenizer 相关文件都在
5. 回到项目根目录执行：
   `python start.py`

## 十、补充说明

如果你后面还要换别的 Hugging Face embedding 模型，也可以继续按同样规则放：

```text
embedding_model/<模型作者或命名空间>/<模型名>
```

例如：

```text
embedding_model/BAAI/bge-small-zh-v1.5
```

但前提是你在系统配置里把使用的 embedding 模型名称也改成对应的模型名。
