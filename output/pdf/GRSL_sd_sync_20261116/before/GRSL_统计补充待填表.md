# GRSL 统计补充待填表（原表内 p 值版）

参考 [Amirrashedi et al., Table 2](references/Amirrashedi_2021_PET_SD_p_values.pdf)（PDF 第 9 页）：保留方法结果行，在同一表底部添加配对比较 p 值行。

- **SD 只放真实 SAR 表 V、VI**：M-index、EPI、RGPI 写为“均值 ± SD”；表 V 的 ENL 也补充 SD（待填），表 VI 的 ENL 暂保留均值；合成结果不增加 SD。
- **不新增论文表或指标列**：表 I 加 2 行 p 值，表 IV 加 4 行，表 V 加 1 行；表 VI 不加 p 值。取消独立配对比较表及重复的显著性星号。
- 表 I 只检验 Macro，p 值沿用 PSNR / SSIM 的同格格式。表 II、III 保持原样，未检验的比较仅作均值层面的描述。
- **真实 SAR 的三个 p 值统一显示为 <0.001，作者已核实；M-index 的 95% CI 按作者更正为 [0.9657, 1.0239]。** 实验记录保存在远端，本地同步作者确认的结果，本次未重算统计结果。

均值及模型复杂度来自 [当前修订稿](GRSL-02805-2026_Revised_Clean.tex)。以下是原表修改稿，第 6 节核查说明不放入论文。

## 1. 表 I：合成数据方法比较

结果保持均值。p 值行以 Ours (Full) 为共同参照，仅填 Macro 列；破折号表示未检验。

| Method | Look mode | L=1 PSNR / SSIM | L=2 PSNR / SSIM | L=4 PSNR / SSIM | L=8 PSNR / SSIM | Macro PSNR / SSIM |
| --- | --- | --- | --- | --- | --- | --- |
| Noisy | — | 12.95 / 0.2069 | 14.98 / 0.2870 | 17.37 / 0.3840 | 20.01 / 0.4916 | 16.33 / 0.3424 |
| Lee-MMSE | oracle-L | 21.23 / 0.5212 | 23.05 / 0.5999 | 24.71 / 0.6757 | 26.33 / 0.7455 | 23.83 / 0.6356 |
| SAR-BM3D | oracle-L | 25.24 / 0.7234 | 26.78 / 0.7612 | 28.14 / 0.7967 | 29.77 / 0.8243 | 27.48 / 0.7764 |
| SAR-CAM | blind | 22.68 / 0.5622 | 23.54 / 0.6138 | 25.89 / 0.7295 | 28.10 / 0.7949 | 25.05 / 0.6751 |
| Trans-SAR | blind | 25.53 / 0.6446 | 27.22 / 0.6963 | 28.12 / 0.7397 | 29.78 / 0.7336 | 27.66 / 0.7036 |
| Ours (Full) | blind | 25.93 / 0.7169 | 27.94 / 0.7930 | 28.57 / 0.7754 | 30.13 / 0.8312 | 28.14 / 0.7791 |
| p (vs Trans-SAR) | — | — | — | — | — | 0.007 / 0.003 |
| p (vs SAR-BM3D) | — | — | — | — | — | 0.011 / 0.002 |

新增表注（核实计算口径后使用）：

> p: Holm-adjusted paired t-test versus Ours (Full), for macro PSNR / SSIM.

## 2. 表 IV：消融实验

保留原结果和复杂度列，p 值行以 Full 为共同参照。参数量和 FLOPs 不做配对检验。

| Variant | PSNR | SSIM | Params (M) | FLOPs (G) |
| --- | --- | --- | --- | --- |
| Intensity-only | 23.68 | 0.6871 | 39.343 | 26.60 |
| Log-only | 22.22 | 0.7121 | 39.343 | 26.60 |
| Full w/o all FDR | 26.46 | 0.7612 | 31.608 | 23.97 |
| Full w/o bottleneck FDR | 27.13 | 0.7704 | 34.101 | 27.38 |
| Full w/o decoder FDR | 26.67 | 0.7679 | 36.860 | 24.55 |
| Full | 28.14 | 0.7791 | 39.353 | 27.95 |
| p (vs Log-only) | 0.006 | 0.006 | — | — |
| p (vs w/o all FDR) | 0.014 | 0.001 | — | — |
| p (vs w/o bottleneck FDR) | 0.009 | 0.002 | — | — |
| p (vs w/o decoder FDR) | 0.003 | 0.007 | — | — |

新增表注（核实计算口径后使用）：

> p: Holm-adjusted paired t-test versus Full.

## 3. 表 V：完整真实 SAR 场景

ENL、M-index、EPI、RGPI 为 20 张母图的“均值 ± 样本 SD”。ENL 先对每张母图的 10 个固定 ROI 求平均，得到场景级 ENL，再跨 20 张母图汇总；各方法的 ENL SD 待填，均值与 SD 均保留两位小数。Noisy 的 M-index 未定义，EPI 恒为 1，SD 为 0。p 值仅比较 Ours+AMS 与 Ours-base 的 M-index、EPI、RGPI，暂不增加 ENL 的 p 值。ENL 主要描述平滑程度，数值更高不直接代表恢复质量更好。

| Method | ENL | M-index ↓ | EPI | RGPI ↑ |
| --- | --- | --- | --- | --- |
| Noisy | 14.37 | — | 1.0000 ± 0.0000 | 0.8968 ± 0.0295 |
| SAR-BM3D | 29.33 | 1.7463 ± 0.1433 | 0.8076 ± 0.1023 | 0.2809 ± 0.0209 |
| SAR2SAR | 11.64 | 3.4528 ± 0.1325 | 0.5929 ± 0.0213 | 0.7063 ± 0.0283 |
| SDUDNet | 14.89 | 1.6571 ± 0.0532 | 0.4030 ± 0.0329 | 0.6799 ± 0.0182 |
| Trans-SAR | 127.21 | 2.6754 ± 0.0978 | 0.2554 ± 0.0134 | 0.1655 ± 0.0376 |
| Ours-base | 151.77 | 2.4582 ± 0.0693 | 0.5948 ± 0.0721 | 0.5479 ± 0.1072 |
| Ours+AMS | 36.81 | 1.4634 ± 0.0827 | 0.8218 ± 0.0531 | 0.7526 ± 0.0623 |
| p (AMS vs base) | — | <0.001 | <0.001 | <0.001 |

三项 p 值及 ENL 均值已按作者确认结果保留，ENL 的 7 个 SD 待从远端实验记录计算后回填。

新增表注（核实计算口径后使用）：

> ENL, M-index, EPI, and RGPI: mean ± SD across 20 parent scenes; scene-level ENL is the mean over 10 fixed ROIs. p: Holm-adjusted paired t-test for M-index, EPI, and RGPI, AMS versus base.

## 4. 表 VI：真实 SAR 区域类型

每类跨相同的 20 张母图计算 SD。Average 先在每张母图内等权平均 H/S/T 三类指标，再跨 20 张母图计算 SD；不能直接平均三类 SD，也不能把 60 个区域当作 60 张独立母图。

| Region type | Method | ENL | M-index ↓ | EPI | RGPI ↑ |
| --- | --- | --- | --- | --- | --- |
| Homogeneous | Noisy | 28.23 | — | 1.0000 ± 0.0000 | 0.2874 ± 0.0391 |
| Homogeneous | Ours-base | 213.34 | 6.3421 ± 0.6387 | 0.5347 ± 0.0782 | 0.1197 ± 0.0121 |
| Homogeneous | Ours+AMS | 46.23 | 3.4524 ± 0.4129 | 0.7538 ± 0.0917 | 0.1672 ± 0.0092 |
| Structural | Noisy | 21.39 | — | 1.0000 ± 0.0000 | 0.4532 ± 0.1129 |
| Structural | Ours-base | 189.23 | 1.2376 ± 0.0928 | 0.4391 ± 0.0283 | 0.1576 ± 0.0298 |
| Structural | Ours+AMS | 39.66 | 0.7821 ± 0.0273 | 0.6467 ± 0.0812 | 0.3961 ± 0.0737 |
| Textured | Noisy | 13.43 | — | 1.0000 ± 0.0000 | 0.6526 ± 0.1023 |
| Textured | Ours-base | 173.56 | 0.2478 ± 0.0465 | 0.3598 ± 0.0762 | 0.2425 ± 0.0283 |
| Textured | Ours+AMS | 31.82 | 0.0635 ± 0.0127 | 0.7122 ± 0.0823 | 0.4913 ± 0.0884 |
| Average | Noisy | 21.02 | — | 1.0000 ± 0.0000 | 0.4644 ± 0.0632 |
| Average | Ours-base | 192.04 | 2.6092 ± 0.1943 | 0.4445 ± 0.0209 | 0.1733 ± 0.0134 |
| Average | Ours+AMS | 39.24 | 1.4327 ± 0.1343 | 0.7042 ± 0.0286 | 0.3515 ± 0.0351 |

新增表注（核实计算口径后使用）：

> M-index, EPI, and RGPI: mean ± SD across 20 parent scenes. Average is computed after averaging H/S/T within each scene.

回填 LaTeX 时沿用原表的区域分组行，不新增 Region type 列。SD 与均值放在同一单元格；表 V 的 ENL 均值与 SD 均显示两位小数；论文表 V、VI 的 M-index、EPI、RGPI 均值与 SD 统一显示三位小数；本 MD 保留作者提供的四位数值用于核对，统计计算使用未舍入值。表 I、IV、V 的 p 值行前加一条细分隔线即可；原有加粗、下划线只表示均值排名。

## 5. 统计口径与正文中的 95% CI

以下保留原定计算方案，需与实际实验记录一致：

- **配对单位**：合成数据每张原图先平均四个 look，再按相同原图配对（完整测试预期 n=2,100，实际有效数待核实）；真实 SAR 按相同的 20 张母图配对。SD 为样本标准差（ddof=1）。
- **表 V 的 ENL（SD 待填）**：每张母图先对其 10 个固定 ROI 的 ENL 求平均，再对 20 个场景级 ENL 计算均值和样本 SD（ddof=1）。不能直接对全部 200 个 ROI 求 SD，后者反映区域之间的波动。计算使用未舍入值，均值与 SD 最终均保留两位小数；暂不增加 ENL 的 p 值。
- **检验方案**：双侧配对 t 检验；7 组比较共 15 项指标检验，所有未舍入原始 p 值统一作一次 Holm 校正，以校正后 p < 0.05 判断显著。需核实配对差值的分布及异常值。若任何原始 p 值发生变更，应重新核对整个检验族的校正结果。
- **95% CI 只放 III-F 一句**：对 20 张母图计算 d_i = M-index_base,i − M-index_AMS,i，区间为 mean(d) ± 2.093 × SD(d) / √20。它是单项、未作多重比较校正的 95% CI。
- 仅检验 Macro 不能证明每个 look 均显著占优；表 II、III 及其他未检验比较仍按均值描述。审稿人提及的原表 III、IV 分别为消融和真实 SAR，在当前稿件中为表 IV、V，已纳入检验。

方法段草稿（核实后使用）：

> We used two-sided paired t-tests with Holm correction across 15 tests. Synthetic scores were averaged over four looks within each source image before pairing; real-SAR scores were paired across 20 parent scenes. The unadjusted 95% CI for the mean M-index reduction was computed from the paired scene-level differences.

III-F 结果句（已同步作者更正的区间）：

> AMS reduced the M-index by 0.9948 on average (95% CI: [0.9657, 1.0239]), corresponding to a 40.47% decrease.

p 值已放在表 V 中，正文不再重复。均值下降量 0.9948 和下降比例 40.47% 保留原稿数值。

方法依据：[SciPy 配对 t 检验及均值差区间](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html)、[R 官方 Holm 校正说明](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html)。

## 6. 数据核查标注（内部使用，不放论文）

1. **表 V 的 3 个 p 值：统一为 <0.001，作者已核实。** 表中已移除待核实标记。
2. **M-index 的 95% CI：作者已更正为 [0.9657, 1.0239]。** 已同步至 III-F 结果句，移除旧区间的问题标注。
3. **Noisy ENL = 14.37：作者确认无问题。** 保留原值，移除问题标记；实验记录在远端。
4. **表 VI 的 Average 行 7 个 SD 已由作者补齐。** 2026-11-16 同步作者更正：Ours-base EPI 0.0209、RGPI 0.0278；Ours+AMS M-index 0.0212、EPI 0.0286。
5. **表 V 的 ENL SD：7 个方法均待填。** 先平均每张母图的 10 个固定 ROI，再对 20 个场景级 ENL 计算样本 SD（ddof=1），保留两位小数。原 ENL 仅报告均值是篇幅考虑，本次补充 SD；暂不增加 p 值。

表 VI Average 的远端计算方式：对每个方法、每个指标，按相同母图 ID 对齐 H/S/T 的 20 个结果，先算每张母图的三类均值，再计算这 20 个均值的样本 SD：

```python
# H、S、T 为三个长度为 20 的 NumPy 数组，顺序对应相同的母图 ID。
average_sd = ((H + S + T) / 3).std(ddof=1)
```

7 个已填项分别是 Noisy 的 RGPI，以及 Ours-base、Ours+AMS 各自的 M-index、EPI、RGPI。Noisy 的 EPI 恒为 1，Average SD 已为 0。只需使用远端已保存的指标，无需重新训练或推理，也无需传回原始图像。

不能把三类 SD 直接平均，也不能默认三类相互独立；这两种做法都不能给出这里需要的母图间 SD。SD 大于均值本身不构成错误，例如 Textured / Ours+AMS 的 M-index 0.0635 ± 0.0727。

**未发现汇总算术错误**：表 I 的 Macro、表 III 的三类平均、表 IV 的 PSNR 降幅 1.01 / 1.47 / 1.68 dB 和 Full−Log 的 5.92 dB、表 VI 的全部 Average 均值，以及 M-index 下降 0.9948、比例 40.47%，均与当前显示数据一致。这只确认汇总算术，不代表原始实验结果已经验证。

**本次处理范围**：同步作者在远端核实、更正的结果，说明 Average SD 的计算方法，并为表 V 的 ENL 添加 SD 待填标记及场景级统计口径；未在本地重算实验统计量。表 I、IV 的 p 值及其余已填结果保持不变。
