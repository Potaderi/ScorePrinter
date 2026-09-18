# ScorePrinter

将 PDF / 图片原谱复刻为可编辑的 MuseScore `.mscz`，包含可复用 skill、录谱脚本、独立参考校验、逐小节复核流程和完整示例。

本项目将录入、节奏检查、MuseScore 转换、保存后重新打开、结构化比对与 PDF 对照串起来。新谱仍需要人或代理读谱；它目前不是任意 PDF 的全自动 OMR 引擎。

## 快速开始

需要 Python 3.10+ 和 MuseScore。核心脚本只使用 Python 标准库；PDF 裁图工具另外需要 PyMuPDF。已实测环境为 Windows、Python 3.13、MuseScore Studio 4.6.3。

```powershell
git clone https://github.com/Potaderi/ScorePrinter.git
cd ScorePrinter
python skill/musescore-score-reproduction/scripts/demo.py --musescore "C:/Program Files/MuseScore 4/bin/MuseScore4.exe" --out "demo-output"
```

将 MuseScore 路径替换为实际位置，输出目录必须尚不存在。示例会从随附的 JSON 录谱数据生成《Ode to Joy》，从原站 LilyPond 独立解析参考音符，再创建 MSCZ、重新打开并导出检查。

结果位于 `demo-output/result/`：

- `score.mscz`：可编辑成品。
- `score.pdf`、`score-1.png`：实际渲染结果。
- `roundtrip.musicxml`、`audit.json`：回读谱面与结构化差异。
- `review.json`：逐小节复核清单，初始为待核对。
- `provenance.json`：输入、原谱、成品哈希；另附命令日志。

请从[中文完整操作指南](skill/musescore-score-reproduction/references/quickstart.md)开始为新原谱打谱。指南中的 `scripts/...` 命令以 skill 文件夹为工作目录。

## 作为 skill 使用

复制整个 [musescore-score-reproduction](skill/musescore-score-reproduction/) 文件夹到执行者的 skills 目录，或下载并解压 [skill ZIP](dist/musescore-score-reproduction.zip)。不能只复制 `SKILL.md`，脚本、参考文档、示例和测试需要保留。

入口：[SKILL.md](skill/musescore-score-reproduction/SKILL.md)。此仓库不自带 MuseScore 安装程序，也不会自动修改全局配置。

## 工具

| 文件 | 用途 |
| --- | --- |
| `build_score.py` | JSON 简记音符转 MusicXML，提前检查小节时值和无效输入 |
| `lilypond_reference.py` | 独立解析受支持的绝对音高 LilyPond 子集 |
| `musicxml_audit.py` | 比较音高拼写、八度、节奏、声部、谱表、连线端点和记号 |
| `score_pipeline.py` | MuseScore 导入、MSCZ 回读、导出、审计与最终复核检查 |
| `source_project.py` | 原谱下载、来源哈希和已有文件保护检查 |
| `pdf_review.py` | 原谱与成品裁图、重叠条带和 HTML 并排查看 |
| `scorelib.py` | 有理数拍位与 MusicXML 规范化解析核心 |
| `demo.py` | 一条命令运行完整示例 |

所有脚本均位于 `skill/musescore-score-reproduction/scripts/`。

## 已完成谱面

| 曲目 | MSCZ | PDF | 自动审计事件数 |
| --- | --- | --- | --- |
| Ode to Joy | [四声部](scores/ode.mscz) | [查看](renders/ode.pdf) | 245 / 245 |
| Greensleeves | [合并打印版](scores/greensleeves.mscz) | [查看](renders/greensleeves.pdf) | 240 / 240 个独立打印事件 |
| Greensleeves | [保留四声部版](scores/greensleeves-four-voices.mscz) | — | 266 / 266 |

原谱 PDF、LilyPond、来源 URL 与哈希位于 [examples](skill/musescore-score-reproduction/examples/)。两首谱面来自 Mutopia，原始文件保留排版者及 Public Domain 声明：[Ode 528](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=528)、[Greensleeves 1247](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=1247)。

## 验证与验收范围

```powershell
python -m unittest discover -s skill/musescore-score-reproduction/tests -v
```

32 项测试覆盖故意错音、漏音、错误节奏、声部、拍号、连线、显示记号、未知语法、无效输入和过期哈希。独立目录运行和 ZIP 解压运行均已通过；详细范围见[验证记录](skill/musescore-score-reproduction/references/validation.md)。

自动 `PASS` 表示参考与候选在报告所列范围内一致，不能证明参考本身没有读错。默认关注音乐内容；字体、页边距等无需逐像素一致。最终验收还需要对照原谱核对每个小节及未支持的记号，`finalize` 会拒绝缺失的复核项。详见[校验约定](skill/musescore-score-reproduction/references/verification.md)与[输入格式](skill/musescore-score-reproduction/references/input-format.md)。
