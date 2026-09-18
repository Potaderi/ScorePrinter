# ScorePrinter

**把一份全新的乐谱 PDF 转成可编辑 MSCZ，并持续定位、修正识谱错误。**

输入可以是多页 PDF 或扫描 PDF，无须预先提供 JSON、MusicXML 或 LilyPond。主流程是：保留所有原页 → 本地 Audiveris 识谱 → 生成所有曲目/乐章的 MSCZ → 回读检查 → 原谱定位纠错 → 全页和逐小节复核。执行 skill 的代理负责继续纠错，示例谱只用于自检。

## 从你的 PDF 开始

需要 Python 3.10+、MuseScore、Audiveris 和 PyMuPDF。Windows 可用以下命令在项目内配置识谱引擎及依赖：

```powershell
git clone https://github.com/Potaderi/ScorePrinter.git
cd ScorePrinter
python skill/musescore-score-reproduction/scripts/setup_omr.py --out "D:/score-tools/audiveris"
python -m pip install --target "D:/score-tools/deps" pymupdf
```

配置脚本核验固定 SHA-256，解包 Audiveris 5.11.0，并附带与其默认 OCR 模式兼容的完整英文语言数据；不运行系统安装器。其他系统请使用 [Audiveris 官方包](https://github.com/Audiveris/audiveris/releases)，以 `--audiveris` 和 `--tessdata` 指定路径。MuseScore 请使用自己的安装或便携版。

直接输入任意新文件路径：

```powershell
python skill/musescore-score-reproduction/scripts/pdf_to_mscz.py run "D:/incoming/my-score.pdf" --out "D:/scores/my-job" --engine-config "D:/score-tools/audiveris/engine-config.json" --musescore "C:/Program Files/MuseScore 4/bin/MuseScore4.exe" --deps "D:/score-tools/deps"
```

`--out` 目录必须尚不存在。打开 `D:/scores/my-job/index.html` 查看原页、实际成品图和定位线索。曲谱位于 `scores/001/rev-001/score.mscz`；多首作品会保留多个 score ID。

详细步骤：[新 PDF 完整操作指南](skill/musescore-score-reproduction/references/new-pdf.md)。指南中的 `scripts/...` 命令以 skill 文件夹为工作目录。

## 有错误就继续修正

- **漏谱表/整页遗漏**：独立原页五线谱检测与识谱结果交叉检查，给出原图裁片。仍须核对全部页面，不能只看引擎识别到的部分。
- **扫描细线断裂**：可用 `resume JOB --retry-omr --binarize 190` 进行有记录的新轮次；保留原件和之前的工程。
- **错音、漏音、复杂符号**：用 MuseScore、Audiveris `.omr` 工程或带哈希前提的 `musicxml_patch.py` 修正，再运行 `rebuild`，无需重新识谱整本。
- **识谱中断**：普通 `resume` 复用已导出的 MusicXML，仅重试未完成转换。
- **OMR 不支持的谱面**：`--prepare-only` 提供完整原页工作台，执行者按原图直接使用 MuseScore 或完整 MusicXML 补录；不能删掉复杂记号去迎合简化 JSON 格式。

```powershell
python skill/musescore-score-reproduction/scripts/pdf_to_mscz.py rebuild "D:/scores/my-job" --score 001 --candidate "D:/scores/my-job/corrected.musicxml" --musescore "C:/path/to/MuseScore4.exe" --deps "D:/score-tools/deps"
python skill/musescore-score-reproduction/scripts/pdf_to_mscz.py finalize "D:/scores/my-job"
```

执行者要先完成最新 `review.json` 和全本 `source-review.json` 中的真实复核。未核对原页、遗漏曲目、未解决的漏谱提示、最新版本失败或文件变化，都会阻止验收。生成 MSCZ 本身不代表准确性通过。

## 作为 skill 使用

将整个 [musescore-score-reproduction](skill/musescore-score-reproduction/) 文件夹交给代理，或下载 [skill ZIP](dist/musescore-score-reproduction.zip)。入口 [SKILL.md](skill/musescore-score-reproduction/SKILL.md) 明确要求从用户的新 PDF 开始，执行者持续纠错并检查完整原谱，不能停在示例或待办清单。

工具包现有 13 个 Python 文件：

| 工具 | 用途 |
| --- | --- |
| `pdf_to_mscz.py` | 新 PDF 的 run / resume / rebuild / status / finalize |
| `setup_omr.py` | Windows 项目内识谱引擎配置及完整英文 OCR 数据 |
| `omr_engine.py` | Audiveris 批处理、全部输出保留及坐标诊断 |
| `staff_inventory.py` | 从原页像素独立寻找五线谱，提示漏谱 |
| `musicxml_patch.py` | 有原值和哈希前提的局部纠错 |
| `score_pipeline.py` | 生成 MSCZ、重开、导出、逐谱审计 |
| `musicxml_audit.py`、`scorelib.py` | 事件、谱表、声部、连线及支持记号的比对 |
| `build_score.py` | 简单谱段的 JSON 快速录入和节奏检查 |
| `lilypond_reference.py` | 可选的独立原站源码解析，仅支持明确子集 |
| `source_project.py` | 来源下载、哈希与既有文件保护 |
| `pdf_review.py` | 独立 PDF 图像对照 |
| `demo.py` | 环境自检，不是新谱面处理入口 |

## 实测与边界

已经在未参与旧示例的新 PDF 上跑通流程：

| 输入 | 实测结果 |
| --- | --- |
| 全新 Mutopia《Menuet in G》PDF | 识谱、MSCZ 生成、回读、裁图和待核对记号定位 |
| BWV 269 两页四声部纯扫描 PDF | 首轮独立检出漏掉的 3 个谱表；预处理后恢复全部 12 个谱表；再定位并补入一个漏音，229 个音符事件与保留的独立参考一致 |

第二项不意味着全谱已完美：独立核查还发现表情/连线等差异，歌词也需复核。报告保留这些问题，不会因为音符对齐就把整谱标成通过。测试范围及证据见 [验证说明](skill/musescore-score-reproduction/references/validation.md)和[新 PDF 集成记录](verification/new-pdf-validation.json)。

```powershell
python -m unittest discover -s skill/musescore-score-reproduction/tests -v
```

61 项测试涵盖原有比对逻辑、新 PDF 全页处理、所有乐章输出、漏谱验收拦截、超时、缓存恢复和带前提的局部修正。两项真实 PDF 准备测试需要 PyMuPDF 可导入；未安装时会明确跳过。完整测试请将本地依赖目录加入 `PYTHONPATH`。

任何现成 OMR 都不能保证所有模糊扫描件、手写谱或任意记谱法一次自动百分之百正确。这个 skill 的目标是让执行者高效完成新谱的识别和纠错流程；它不会从无法辨认的像素猜出“确定正确”的音符。默认要求音乐内容一致，不要求字体、页边距等逐像素一致。

旧的 [Ode](scores/ode.mscz)、[Greensleeves 打印版](scores/greensleeves.mscz)和[四声部版](scores/greensleeves-four-voices.mscz)保留为回归示例，**不是支持曲目白名单**。原始示例来源与 Public Domain 声明保留在 [examples](skill/musescore-score-reproduction/examples/) 中。
