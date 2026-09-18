# 快速开始

整个 skill 文件夹可以独立复制到另一台电脑。脚本不依赖此次项目中的 `scripts/`、固定工作目录或你的个人配置。需要 Python 3.10+ 和 MuseScore；只有 PDF 裁图额外需要 PyMuPDF。

## 先跑完整例子

在 skill 根目录执行（把程序路径换成实际路径；输出目录必须尚不存在）：

```powershell
python scripts/demo.py --musescore "C:/Program Files/MuseScore 4/bin/MuseScore4.exe" --out "D:/new-score-demo"
```

它会生成一首完整的《Ode to Joy》，同时从附带的原站 LilyPond 文件独立解析参考音符。得到：

```text
new-score-demo/
  entry.musicxml
  reference.musicxml
  result/
    score.mscz
    score.pdf
    score-1.png
    roundtrip.musicxml
    audit.json
    review.json
    provenance.json
    ...命令与日志
```

自动检查通过后，`review.json` 仍是待复核状态。这是必要的：参考文件中的表头、记号或人眼录入本身也可能出错，不能拿一份错误输入循环导出后称为正确。

## 对新原谱打谱

1. 先建立专用项目目录，保存原谱、来源页和许可。需要保护已有文件时，先记录快照，排除整个新项目：

   ```powershell
   python scripts/source_project.py snapshot --root "D:/scores" --exclude "D:/scores/new-project" --out "D:/scores/new-project/before.json"
   python scripts/source_project.py fetch --url "https://example.org/original.pdf" --license "填写核实后的许可及其来源" --out "D:/scores/new-project/original.pdf"
   ```

2. 查看环境：

   ```powershell
   python scripts/score_pipeline.py doctor --musescore "C:/path/to/MuseScore4.exe"
   ```

   Windows 需要严格保护既有 MuseScore 设置时，用项目内便携版；普通安装的系统偏好设置不保证完全被环境变量隔离。脚本不修改安装、不调用恢复出厂设置。

3. 裁图方便逐段读谱。可把依赖装在项目内部：

   ```powershell
   python -m pip install --target "D:/scores/new-project/deps" pymupdf
   python scripts/pdf_review.py --source "D:/scores/new-project/original.pdf" --out "D:/scores/new-project/source-pages" --deps "D:/scores/new-project/deps"
   ```

4. 复制 `examples/pickup-entry.json` 作为短谱起点，或参考完整四声部 `examples/ode-entry.json`。按原谱填写，运行：

   ```powershell
   python scripts/build_score.py "D:/scores/new-project/entry.json" --out "D:/scores/new-project/entry.musicxml"
   ```

   输入格式见 [input-format.md](input-format.md)。脚本提前检查各声部的小节拍数、音名语法、重复和弦音、无效连线目标、延音线两端音高以及未知字段。普通 F 是 F 自然音，调号不会自动把它改成 F♯。

5. 建立独立参考。原站有 MusicXML 时保存并检查其版本是否与 PDF 一致；本工具支持的绝对音高 LilyPond 子集可用：

   ```powershell
   python scripts/lilypond_reference.py --source examples/greensleeves-original.ly --map examples/greensleeves-reference-map.json --out "D:/scores/new-project/reference.musicxml"
   ```

   此命令只展示用法；新曲目必须填写它自己的映射。相对音高、复杂宏、反复及其他未实现语法会被拒绝，不能强行当作普通音符处理。仅有 PDF 时，独立重读或第二次录入作为参考；不要复制候选文件充当“独立参考”。

6. 生成并回读真实 MSCZ：

   ```powershell
   python scripts/score_pipeline.py convert --input "D:/scores/new-project/entry.musicxml" --expected "D:/scores/new-project/reference.musicxml" --source "D:/scores/new-project/original.pdf" --out "D:/scores/new-project/run-01" --musescore "C:/path/to/MuseScore4.exe" --expected-role independent-reference
   ```

   输出包含 MSCZ、PDF、PNG、导回 MusicXML、源与成品哈希、命令日志、逐项差异及复核清单。发现差异按报告的 part / measure / staff / onset 修正，再用新目录 `run-02` 重跑，不覆盖旧轮次。

7. 对比导出与原 PDF：

   ```powershell
   python scripts/pdf_review.py --source "D:/scores/new-project/original.pdf" --render "D:/scores/new-project/run-01/score.pdf" --out "D:/scores/new-project/comparison-01" --deps "D:/scores/new-project/deps"
   ```

   打开生成的 `index.html`。逐小节核对所有声部、变音显示、附点、休止、符杠、连线、速度力度、反复与其他音乐文字。字体、边距等可以不同；不能漏掉会改变音乐含义的内容。

8. 在 `run-01/review.json` 中填写真实复核结果与证据，并执行：

   ```powershell
   python scripts/score_pipeline.py finalize "D:/scores/new-project/run-01"
   python scripts/source_project.py check "D:/scores/new-project/before.json" --report "D:/scores/new-project/after.json"
   ```

   未核对的小节、没有解决的不支持记号、语义差异或复核后文件变化都会阻止验收。脚本不自动勾选人工/代理复核项。

## 独立调用核查器

```powershell
python scripts/musicxml_audit.py --expected reference.musicxml --actual roundtrip.musicxml --report differences.json
```

`--display` 增加对显式变音、符干、符杠的检查；`--layout` 增加手动换行检查。参考 MusicXML 没有写入自动排版产生的字段时，不能靠盲目删除字段消除差异，需读谱确认。`--merge-voices` 只适用于明确合并打印的版本，独立声部文件仍须保留并严格校验。

## 使用前验证工具

```powershell
python -m unittest discover -s tests -v
```

测试包含故意错音、漏音、改拍号、丢连线、错误声部、未知记谱及过期文件哈希。覆盖范围与限制见 [verification.md](verification.md)。这套工具能省去重复编码、裁图、转换和比对，但不能保证任意模糊扫描件未经独立读谱就“自动完美”。
