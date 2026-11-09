# GRSL 精简稿

本目录是独立的 GRSL 稿件，原始 `docs/ICSPS2026_LaTeX` 目录未修改。

## 返修工作流程

后续论文修改只编辑 `GRSL-02805-2026_Revised_Clean.tex`，用 `\rev{...}` 累积标记相对固定投稿基线的改动。Clean 模式正常显示内容；`GRSL-02805-2026_Revised_Marked.tex` 仅开启标记模式并载入同一份 Clean 源码，不独立维护正文。Marked PDF 将 `\rev{...}` 内容显示为蓝色，并附页眉说明；当前蓝色内容为修改后的数值。两份 PDF 始终使用同一份论文正文。

- `revision_baseline/GRSL-02805-2026_Submitted.tex` / `.pdf`：2026-09-28 V3 投稿包的逐字节副本，作为固定比较基线，后续修改和编译均不得覆盖；来源和 SHA-256 记录在 `revision_baseline/baseline_manifest.json`。
- `GRSL-02805-2026_Response.tex`：独立维护的逐项审稿回复。当前已完成 Reviewer 2 第 1、4 条，其余意见仍待处理。
- 固定交付文件名：`GRSL-02805-2026_Revised_Clean.pdf`、`GRSL-02805-2026_Revised_Marked.pdf`、`GRSL-02805-2026_Response.pdf`。

2026-11-10：完成 R2.1，新增表 II（第 4 页），使用作者提供的 NWPU 与真实 SAR 验证集参数扫描结果，更新 II-C、III-B 的参数说明；正文精简后，Clean 和 Marked 均保持 5 页。当前最新回复为 `GRSL-02805-2026_Response_R2_1.pdf`（第 3 页为 R2.1），因原 `Response.pdf` 被阅读器占用而另存；回复源码仍为 `GRSL-02805-2026_Response.tex`，解除占用后正常编译即可更新固定文件名。

随后在 III-B 明确表 II 使用的验证图像与表 I、V 的测试图像不同。清稿已更新；标记版因原 PDF 被占用，最新文件另存为 `GRSL-02805-2026_Revised_Marked_R2_1.pdf`。两版仍为 5 页。

从仓库根目录运行 `& .\docs\GRSL_LaTeX\build_revision.ps1`，编译以上三份 PDF。后续修改继续保留已有修订标记，并为新增改动添加标记；固定投稿基线不随返修更新。

以下为此前工作记录。`GRSL_paper.tex` / `.pdf` 是既有工作文件，后续返修不再以它们为编辑入口；下文的旧 `build.ps1` 编译流程不用于返修交付。

## 文件

- `GRSL_paper.tex` / `GRSL_paper.pdf`：主稿，**5 页，包含全部参考文献**。
- `GRSL_method_diagrams.tex` / `GRSL_method_diagrams.pdf`：1 页独立补充方法示意图；当前主稿未引用 Fig. S1、S2。
- `IEEEtran.cls`、`figures/`：本地模板类及主稿、补充稿编译所需图形资源。
- `GRSL_REVISION_NOTES.md`：精简策略、图表对应关系、官方及论文来源、校验结果。
- `build.ps1`：同时生成主稿和补充方法图 PDF。
- `FIG1_DESIGN_NOTES.md`：图 1 的绘图依据、重绘说明及可编辑资源。

作者顺序：Hongyu Chen；Peng Liu（Senior Member, IEEE）。通讯作者：Peng Liu，邮箱 pliu@fudan.edu.cn。

全体作者单位：Key Laboratory of Information Science of Electromagnetic Waves, Fudan University, Shanghai, China。

## 内容保留

5 张实验结果表及其所有数值、精度、粗体和下划线均保留在主稿中。Fig. 2 的 8 个模拟实验面板保持不变。Fig. 3 的 8 个面板已按 V3 Word 的可见顺序同步，标签、图注和 2×4 排列保持与 V3 一致。总体架构图仍为 Fig. 1，现已按用户要求重绘为“网络总览、解码顺序、强度重构”三个分区。

原 Fig. 2、3 是局部方法示意图，现作为补充 Fig. S1、S2 单独保存。其必要运算、训练条件及 8 个公式均已写入主稿，主稿不依赖补充文件来说明关键方法或结果。22 条参考文献全部保留，并按正文首次引用顺序编号。

采用 IEEEtran 期刊模式，保留标准 10 pt 正文字体及页边距。末页按先填左栏、再排右栏的顺序流动。

## 编译

在本仓库根目录执行：

```powershell
& .\docs\GRSL_LaTeX\build.ps1
```

脚本优先查找已安装的 Tectonic，否则使用仓库 `tmp/latex_runtime/tectonic.exe`。其他电脑可显式传入 `-TectonicPath`。

也可将整个目录上传至 Overleaf，选择 `GRSL_paper.tex` 为主文件、使用 XeLaTeX 编译；补充材料以 `GRSL_method_diagrams.tex` 为主文件另行编译。两份文稿都使用同一目录内的图形资源，无需原 ICSPS 目录。

已在本机通过 Tectonic 编译并逐页检查，主稿仍为 5 页。其他 TeX 发行版的换行和浮动位置可能略有差别，重新编译后应再次核对页数。

## 投稿文件区分

主稿与补充方法图是两份独立 PDF。补充图提供可选的直观说明；不能把两份 PDF 合并后当作 5 页主稿。提交时按 GRSL 投稿系统的文件类别分别上传，README 和改稿说明无需当作论文正文上传。本次仅完成稿件准备，未进行线上投稿。
