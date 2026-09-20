# 新 PDF → 识谱 → 纠错 → MSCZ

这才是本 skill 的主流程。输入是用户提供的全新 PDF，不要求它出现在示例目录，不要求用户先准备 JSON、MusicXML 或 LilyPond。执行者负责读谱、修正与复核；不要把一张待办清单交回用户就结束。

## 1. 配好一次环境，之后反复使用

需要 Python 3.10+、MuseScore 和 Audiveris。PDF 处理需要 PyMuPDF。所有路径都可以自选；以下命令以 skill 文件夹为工作目录。Windows 可将识谱引擎和依赖放在项目内：

```powershell
python scripts/setup_omr.py --out "D:/score-tools/audiveris"
python -m pip install --target "D:/score-tools/deps" pymupdf
```

`setup_omr.py` 下载并检查固定 SHA-256，解包 Audiveris 5.11.0，不运行系统安装器。输出 `engine-config.json`，包含引擎路径和英文文字识别语言数据路径。需要约 110 MB 下载空间及更多解包空间。目录必须尚不存在。其他系统可使用 [Audiveris 官方发行包](https://github.com/Audiveris/audiveris/releases)，以 `--audiveris` 指定可执行程序。项目内解包流程只在 Windows 实测。

**语言数据必须适配引擎。** Audiveris 5.11.0 默认使用 Tesseract legacy 模式；`tessdata_fast` 的纯 LSTM 模型会初始化失败。配置脚本附带官方 `tessdata/4.1.0` 完整英文模型。中文、德文等歌词仍需相应模型及 Audiveris 语言设置，原谱上的歌词和速度文字必须单独核对。英文模型不意味着其他语言正确。

保护既有 MuseScore 设置时，使用项目内便携版。脚本为处理过程设定本地缓存目录，但这不等于隔离所有操作系统级偏好设置。

## 2. 把新 PDF 直接交给入口

```powershell
python scripts/pdf_to_mscz.py run "D:/incoming/new-score.pdf" --out "D:/scores/new-job" --engine-config "D:/score-tools/audiveris/engine-config.json" --musescore "C:/path/to/MuseScore4.exe" --deps "D:/score-tools/deps"
```

也可单独指定 `--audiveris "C:/path/to/Audiveris.exe" --tessdata "D:/tessdata"`。输出目录必须新建。`--timeout` 控制每次 OMR 最长秒数（默认 900），`--convert-timeout` 控制每次 MuseScore 最长秒数（默认 180）；长谱应按页数提高限时。

流程执行：

1. 保存原 PDF 与哈希，读取**所有页面**，输出整页和四段有重叠的高分辨率裁图。
2. 从原页像素独立估计五线谱位置，与 OMR 检测到的谱表比对，提示可能漏掉的谱表。
3. Audiveris 识谱并保存 `.omr` 工程、全部 MusicXML 曲目/乐章和日志。
4. 为每个识别结果创建真实 MSCZ，关闭后重新打开，导出 PDF、PNG、MusicXML，再检查转换差异。
5. 把低置信度、异常节奏、未完成页面、漏谱线索和导入差异汇入 `triage.json`，能定位的符号附原谱裁图。

主要文件：

```text
new-job/
  source.pdf                  始终不改的原谱
  source-pages/               全部原页及高分辨率条带
  job.json                    进度、当前版本和历史错误
  source-review.json          整页覆盖、源谱清单与输出映射
  index.html                  本地查看入口
  triage.json                 优先纠错清单，不能替代完整读谱
  crops/                      可定位问题和完整系统的裁图
  omr/attempt-001/            可继续编辑的 OMR 工程及日志
  inputs/                    每轮候选文件的独立快照
  scores/001/rev-001/
    score.mscz
    score.pdf
    roundtrip.musicxml
    audit.json
    review.json
```

一本 PDF 若含多首曲目，所有识别输出都会保留为 `001`、`002` 等，不会只取第一个。是否应合为同一份总谱需依据源谱结构判断；不要无声地丢掉第二首。若 OMR 错把不同作品合在一起，要在 MuseScore/MusicXML 分开并检查源页映射。

退出码：`run/resume/rebuild/status` 的 0 表示当前每个候选已有 MSCZ，**不表示内容已验收**；1 表示准备完成但没有完整候选，2 表示执行错误。只有最终 `finalize` 的 0 表示文档所述核验和复核记录通过。始终读取 `job.json` 的状态及审计文件。

## 3. 先核查覆盖，再改错音

打开 `index.html` 并实际查看原页。按页记录系统数、每个系统的谱表/声部数、小节范围、调拍号、弱起/末小节和所有音乐记号。封面、空白页可以排除，但必须说明依据。**引擎没有识别出谱表，不能据此宣布该页没有音乐。**

优先解决 `triage.json` 中 `kind: coverage` 的项目。像素检测只适用于较长、近水平的五线谱；斜拍、断线、手写、短谱行、六线谱可能检测不到，必须直接阅读整页。高置信度不是正确率，列表里没有问题也仍要核对原谱。

扫描谱线断裂、灰色细线导致漏识别时，保留原件，用一次明确的二值化重试：

```powershell
python scripts/pdf_to_mscz.py resume "D:/scores/new-job" --retry-omr --binarize 190 --omr-dpi 300 --engine-config "D:/score-tools/audiveris/engine-config.json" --musescore "C:/path/to/MuseScore4.exe" --deps "D:/score-tools/deps"
```

必要时根据图像调整阈值；不要无依据反复扫描整个大谱。横向或倒置原页可加 `--rotate 90/180/270`，仅用于 OMR 输入，原件不变；旋转后的识谱坐标不再直接裁原图，须看完整原页。任意角度倾斜需在有记录的图像工具或 OMR 编辑器中处理。

普通 `resume` 复用识谱结果并重试未完成的转换，不重新识谱。只有 `--retry-omr` 才会新建识谱轮次，旧候选和旧 MSCZ 都保留。引擎超时或中断会留下工程/日志；检查原因后再续跑。两次有针对性的识谱仍无法识别的区域，应直接补录该区域，不能无限换参数。

## 4. 精确修正，而不是重新打一整首

可以在 Audiveris 中打开 `.omr` 修正结构后重新导出 MusicXML；也可以在 MuseScore 中编辑 MSCZ。简单的少量改错可用 `musicxml_patch.py`，保留其他所有 MusicXML 记号。

补丁使用原文件 SHA-256 和 1 起始的**实际 part/measure 顺序**，不是印刷小节号；选择器采用 Python ElementTree 支持的有限 XPath，必须只匹配一个节点。每个改动写明来自哪页哪处原谱：

```json
{
  "input_sha256": "填写待修正 MusicXML 或 MXL 的真实 SHA-256",
  "operations": [
    {
      "part": 2,
      "measure": 3,
      "select": "note[1]/pitch/step",
      "op": "text",
      "before": "C",
      "after": "D",
      "reason": "原谱第1页第1系统中声部，本小节首音为D"
    }
  ]
}
```

支持 `text`、`attribute`、`insert`、`remove`、`replace`。文本/属性操作要求原值吻合；XML 插入/替换使用 `xml` 字段。`insert` 可指定从 0 开始的子节点位置 `index`，否则追加；MusicXML 子节点必须按其格式顺序排列。修正时值时同时检查 `duration`、`type`、附点、连音比例及后续拍位，不能只改一个数字。`replace` 可以替换整小节，以保留普通 JSON 录谱器未覆盖的复杂记号。

```powershell
python scripts/musicxml_patch.py "D:/scores/new-job/inputs/001-001.mxl" --patch "D:/scores/new-job/fix.json" --out "D:/scores/new-job/corrected.musicxml"
python scripts/pdf_to_mscz.py rebuild "D:/scores/new-job" --score 001 --candidate "D:/scores/new-job/corrected.musicxml" --musescore "C:/path/to/MuseScore4.exe" --deps "D:/score-tools/deps"
```

`rebuild` 不再调用 OMR，只生成新版本并失效旧复核。`--candidate` 也接受修好的 MSCZ。有独立出版 MusicXML 时可加 `--reference`，它必须与 PDF 同版。没有源数据时，由执行者独立看原图核对，不要求用户另找源数据。

完全漏掉的乐章/谱面可以独立录入后运行 `rebuild`，**不带 `--score`** 来新增曲目。标准简单谱可用 `build_score.py` 的 JSON 格式；复杂节拍、跨谱表、鼓谱、装饰音、歌词、六线谱等使用完整 MusicXML 或 MuseScore，不能删掉内容迎合简化格式。没有可用 OMR 时，可先 `run PDF --out JOB --prepare-only --deps DEPS` 获取全部原页，直接读图录入并 `rebuild`。

## 5. 由执行者完成逐小节复核和整页验收

两层复核缺一不可：

- 每个当前 `rev-NNN/review.json`：逐 part/measure/staff 对原谱检查音高拼写、八度、时值、休止、声部、变音显示、连线、符杠、力度速度、歌词、反复等，填写证据；明确处理审计器不支持的项。
- `source-review.json`：每页填 `classification: music/non-music`、`status: pass`、`source_inventory`、`score_ids`、`evidence`，并填写执行复核的 `reviewer` 与 `method`。`score_revisions` 记录每个已复核 score ID 对应的当前 MSCZ 哈希。`coverage_resolutions` 中每个漏谱提示要有其 `id`、`status: pass` 与修复或误报的具体证据。

`reviewer` 可以是实际读图的代理，不必把工作全部交给用户。必须真的查看原页和成品；禁止脚本统一勾选通过。音符事件对齐只是其中一部分，文字、装饰音和声部结构也不能漏。

```powershell
python scripts/pdf_to_mscz.py finalize "D:/scores/new-job"
```

这会检查全部原页、全部输出、漏谱提示、最新版本、审计差异和文件哈希。对新 PDF，不能绕过它只运行底层 `score_pipeline.py finalize`，后者并不检查整本 PDF 覆盖。

如果原图模糊到无法分辨升降号或时值，把具体页、系统、音符位置交给用户确认，同时继续其他可辨认部分。任何工具都不能从缺失的图像信息推导出确定答案；不要编造音符或声称任意扫描件都能自动百分之百正确。

## 已验证的新输入，不是模板复播

- Mutopia 的全新《Menuet in G》PDF：仅以 PDF 启动，生成可编辑 MSCZ 和 207 个事件的回读结果，未支持装饰音等保留复核状态。
- 独立 BWV 269 四声部谱的两页纯图像 PDF：首次漏掉 3 个谱表；独立像素提示能检出。二值化重试恢复 12 个谱表，识别 228 个事件；定位并局部补入一个漏音后，229 个事件与事后独立参考完全一致。歌词、装饰/表情记号和整页人工/代理复核仍未被冒充为通过。

这些是测试证据，不是支持曲目白名单。代码不按曲名、文件名、源文件哈希或示例音符路由；新文件走同一套处理流程。具体范围及不足见 [validation.md](validation.md)。

## 增量校对与记号修正（2026-09-20）

新增 `revision_review.py` 自动定位改动小节及受影响的跨小节记号；每次 rebuild 都生成 `changes.json`，校对页面直接显示全部成品页。未变化的 OMR 诊断和源页裁图复用哈希缓存，局部纠错不用重新识别整本。

`reference_patch.py` 可在存在同版独立 MusicXML 时生成歌词、连线、装饰和演奏记号的修正建议；音符事件必须先一致，模糊定位会拒绝。没有独立源文件时仍从 PDF 读图修正，不要求用户额外提供参考文件。

详见[记号范围与增量修正](notation-coverage.md)。补丁还支持 `scope: document` 修复标题或声部名称。升级检查器后旧报告会重新核验，不能沿用范围更窄的旧结论。
