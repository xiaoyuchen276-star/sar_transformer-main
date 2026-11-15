# Fig. 3 候选：ICEYE 巴黎真实 SAR 图像

本目录保存巴黎勒布尔热机场周边的真实 SAR 场景预览、最终裁剪数据和来源记录。影像于 **2025-10-28** 由 **ICEYE-X56** 获取，采用 X 波段、VV 极化、Spot Fine 模式。官方 GRD 为 16 位幅度数据，空间分辨率约 0.5 m，像素间距为 0.25 m。

## 查看图像

| 文件 | 内容 |
|---|---|
| [full_grd_overview.png](previews/full_grd_overview.png) | 整景概览 |
| [full_grd_selected_view.png](previews/full_grd_selected_view.png) | 黄色框标出最终裁剪在整景中的位置 |
| [fig3_view.png](previews/fig3_view.png) | 3072 × 3072 像素裁剪的无标注显示图 |
| [fig3_view_regions.png](previews/fig3_view_regions.png) | H 均匀区、S 结构区、T 密集城区纹理区标注 |
| [roi_H_native.png](previews/roi_H_native.png) / [roi_S_native.png](previews/roi_S_native.png) / [roi_T_native.png](previews/roi_T_native.png) | 三个 384 × 384 像素区域的原像素显示图 |
| `previews/candidate_*.png` | 选景过程中保留的候选视野及位置 |
| [official_scene_preview.png](previews/official_scene_preview.png) | 官方缩略预览 |

## 科学数据与处理

- [fig3_view_amplitude.tif](crops/fig3_view_amplitude.tif)：从官方 GRD 逐像素提取的 uint16 幅度 DN。
- [fig3_view_sigma0.tif](crops/fig3_view_sigma0.tif)：由 `sigma0 = 1.412387683883416e-05 × DN²` 转换得到的 float32 线性强度。
- 裁剪坐标以原图左上角为原点、从 0 开始：`x=[3328,6400)`、`y=[512,3584)`，约 768 × 768 m。
- 科学 TIFF 未进行重采样、旋转或额外去斑。PNG 使用 `10 log10(sigma0)` 和统一的 −18～0 dB 显示范围；显示裁剪不改变 TIFF 数值。整景及部分标注预览经过缩小。
- [fig3_selection.json](fig3_selection.json) 保存最终裁剪、ROI 坐标、校验和及处理记录；[selection_working.json](selection_working.json) 保存初始候选记录。记录中的本机绝对路径为生成时的来源信息。

## 七种方法对比

原图与 SAR-BM3D、SAR2SAR、SDUDNet、Trans-SAR、CL-SAR、MERLIN、MuLoG-DRUNet 按指定顺序排列。展示视野为 3072 × 3072 像素，H、S、T 均使用原先选定的 384 × 384 像素区域。神经网络使用已有公开检查点直接推理。

- [八图全景对比](seven_methods/figures/comparison_8panel.png) / [聊天预览](seven_methods/figures/comparison_preview.png)
- [均匀区 H](seven_methods/figures/roi_H_8panel.png) / [结构区 S](seven_methods/figures/roi_S_8panel.png) / [纹理区 T](seven_methods/figures/roi_T_8panel.png)
- [全图比率](seven_methods/figures/ratio_8panel.png) / [H 区比率](seven_methods/figures/roi_H_ratios.png) / [S 区比率](seven_methods/figures/roi_S_ratios.png) / [T 区比率](seven_methods/figures/roi_T_ratios.png)
- [分区统计 CSV](seven_methods/figures/roi_statistics.csv) / [运行与校验记录](seven_methods/verification.json) / [预览图压缩包](seven_methods/seven_methods_previews.zip)

| 单图文件 | 方法与输入处理 |
|---|---|
| [a_noisy.png](seven_methods/figures/panels/a_noisy.png) | 原始 GRD 线性强度，采用 −18～0 dB 显示 |
| [b_sar-bm3d.png](seven_methods/figures/panels/b_sar-bm3d.png) | SAR-BM3D v1.0，幅度输入，L=5，输出平方回到强度 |
| [c_sar2sar.png](seven_methods/figures/panels/c_sar2sar.png) | SAR2SAR 官方 Single-Look Sentinel-1 检查点，原始 GRD 幅度 DN 输入，恢复后进行辐射定标 |
| [d_sdudnet.png](seven_methods/figures/panels/d_sdudnet.png) | SDUDNet real.pth，沿用已有导出流程的 8 位 dB 显示图输入 |
| [e_trans-sar.png](seven_methods/figures/panels/e_trans-sar.png) | TransSARV2 官方检查点，全局峰值归一化幅度，采用官方 `(255A+1)/256` 映射并逆变换 |
| [f_cl-sar.png](seven_methods/figures/panels/f_cl-sar.png) | CL-SAR MDN1-default，幅度按全图最小非零值和最大值归一化，恢复后平方 |
| [g_merlin.png](seven_methods/figures/panels/g_merlin.png) | MERLIN spotlight，同次获取的原生复数 SLC 输入，对齐后按输入统计匹配显示尺度 |
| [h_mulog-drunet.png](seven_methods/figures/panels/h_mulog-drunet.png) | MuLoG-DRUNet generic_model，线性强度输入，L=5，10 次 ADMM 迭代 |

图中 `*` 标出 SDUDNet 的显示域输入。原图先按 −18～0 dB 映射为 8 位 PNG，网络输出裁剪至 [0,1] 后通过 `10^((-18+18p)/10)` 映射到强度坐标。输入有 2.813% 的像素落在显示范围外。因此，该方法的强度与比率统计包含显示映射的影响。

图中 `**` 标出 MERLIN 的 SLC 输入。官方 COG 的两个波段分别为幅度和弧度相位，按 `S=A exp(jφ)` 恢复复数。MERLIN 在 4736 × 8960 的原生 SLC 窗口上推理，随后用 RPC 在共同椭球高度 0 m 下近似对齐，并以每个 GRD 像元 4 × 4 采样点积分双线性插值。输出使用 `CF × |S|² × sin(θ)` 定标。输入编码见 [ICEYE 产品说明](https://sar.iceye.com/6.0.8/productspecification/dataproducts/)，定标公式见 [ICEYE 辐射说明](https://sar.iceye.com/6.0.6/foundations/radiometric/)。

投影后的 SLC 输入在 H 区的均值约为 GRD 的 **6.050 倍**。主对比图将 MERLIN 的显示强度乘以 **0.1652902**，系数完全由两种输入在 H 区的均值比确定。未匹配尺度的图保存在[元数据定标尺度对比](seven_methods/figures/comparison_8panel_metadata_scale.png)及 [MERLIN 原尺度单图](seven_methods/figures/panels/g_merlin_metadata_scale.png)。保存的科学数组保留定标尺度，见[投影记录](seven_methods/runs/merlin/projection.json)。该产品间尺度差异仍需在论文定量比较前核实。

比率按线性强度计算 `R=输入/输出`。MERLIN 使用对应的投影 SLC 观测作为分子，其余方法使用 GRD 观测。SDUDNet 的分母来自上述显示域逆映射。比率图共用 −5～+5 dB，0 dB 表示 R=1；首幅原图仍为 −18～0 dB。统计 CSV 同时列出线性比率均值、标准差、输出与输入均值比及 H 区 ENL。

H 区的 GRD 输入 ENL 为 4.37，投影 SLC 输入 ENL 为 4.00。下表统计保存的强度数组，MERLIN 的显示匹配系数不参与计算。

| 方法 | H 区输出 ENL | H 区比率均值 | H 区输出/输入均值 |
|---|---:|---:|---:|
| SAR-BM3D | 9.33 | 0.973 | 0.997 |
| SAR2SAR | 1.64 | 130.274 | 0.653 |
| SDUDNet* | 4.38 | 1.011 | 0.988 |
| Trans-SAR | 107.21 | 0.668 | 1.486 |
| CL-SAR | 45.02 | 0.946 | 1.039 |
| MERLIN** | 11.72 | 0.926 | 1.043 |
| MuLoG-DRUNet | 36.81 | 1.007 | 0.969 |

SAR2SAR 在该场景出现明显暗斑，H 区的部分极低输出使比率均值显著增大。已在同一 H 区独立执行作者的 `u_net.py`、`model.denoiser.test` 和 `utils.py`，结果与本地适配流程逐像素一致，最大幅度误差为 0，见[核验记录](seven_methods/sar2sar_validation/verification.json)。图中保留该检查点在 ICEYE 场景的实际输出。

Trans-SAR 在 H 区更平滑，同时均值提高约 48.6%；S、T 区的亮边缘变宽，部分相邻散射点融合，其比率图中可辨认屋顶和道路轮廓。SAR-BM3D、CL-SAR 和 MuLoG-DRUNet 的 H 区比率均值较接近 1，局部图展示了不同程度的平滑及细节保留。SDUDNet 的强散射比率还受到显示裁剪影响。不同输入产品和显示域适配条件已在表格、图注及运行记录中分别标出。

SAR-BM3D 使用 512 像素核心块和 64 像素上下文。CL-SAR、SDUDNet 及 DRUNet 前向使用 512 像素核心块和 128 像素上下文。SAR2SAR 使用 256 像素块、64 像素步长；Trans-SAR 使用 256 像素块、64 像素重叠及 128 像素外侧反射填充。MERLIN 使用 256 像素块、64 像素步长，在归一化对数域按正 Hann 窗拼接。MuLoG 的 ADMM 与分位数归一化在整幅图上执行，逐像素 Newton 更新按 64 行分批，已与原函数在小图上核验一致。

科学结果位于 `seven_methods/runs/<方法>/denoised.npy`。除 MERLIN 原生 SLC 功率外，均保存为 3072 × 3072 强度数组；MERLIN 对齐后的强度为 `runs/merlin/denoised_grd_sigma0.npy`。各目录的 `run.json` 保存输入、检查点校验和及运行配置。`verification.json` 记录输入一致性、输出数值检查和图像校验和。

版本管理保留脚本、图表、CSV 和 JSON 记录；`seven_methods/` 下的 NPY 数组、MAT 文件及重复预览压缩包仅保留在本地，可按下述流程重建。

重建脚本位于 `scripts/iceye_paris/`。在仓库根目录先运行 `prepare_grd.py`，MERLIN 另需在含 rasterio 的环境运行 `prepare_slc.py`。六个神经网络分别用对应虚拟环境执行 `run_method.py <方法键>`，键为 `sar2sar`、`sdudnet`、`transsar`、`cl_sar`、`merlin`、`mulog_drunet`；Trans-SAR 使用 `.venv-ours-legacy`。SAR-BM3D 在 MATLAB 中执行 `addpath('scripts/iceye_paris'); run_sarbm3d_tiles(pwd,fullfile(pwd,'output','fig3_iceye_paris_20261109','seven_methods'))`。全部推理结束后依次运行 `project_merlin.py`、`render_results.py`、`verify_sar2sar.py`、`finalize_outputs.py`，其中 SAR2SAR 核验脚本使用 `.venv-sar2sar`。已有 `run.json` 的推理结果会跳过。

## 七种方法的 RGPI

计算日期：2026-11-13。以下为依据 Ma et al. (2022) 式 (15)、(17)、(18) 实现的 **RGPI 论文公式版**，使用保存的线性强度科学数组，不使用 PNG 或显示增益。RGPI 越大表示同一观测、同一视数下的局部梯度保持越好，数值不限定在 [0,1]。[原论文](https://doi.org/10.3390/rs14040856)

| 方法 | 整幅 3072² 视野 | H 均匀区 | S 结构区 | T 纹理区 |
|---|---:|---:|---:|---:|
| SAR-BM3D | 0.080857 | 0.038200 | 0.116456 | 0.143677 |
| SAR2SAR | -2.812588 | -1.103393 | -2.067928 | -2.237829 |
| SDUDNet* | -0.106306 | 0.045948 | -0.738128 | -0.296865 |
| Trans-SAR | -0.809936 | -0.162091 | -1.595394 | -1.823715 |
| CL-SAR | -0.165545 | -0.091541 | -0.225281 | -0.223888 |
| MERLIN** | -0.012162 | 0.010048 | -0.054738 | -0.099054 |
| MuLoG-DRUNet | -0.044997 | -0.050475 | -0.033994 | -0.024862 |

六种 GRD 方法使用共同原图和元数据名义视数 L=5。SDUDNet* 保留其显示域输入及逆映射流程。MERLIN** 使用对应的投影 SLC 观测，L_eff=4.002029450704004，由固定 H 区均值平方/样本方差估计；该值是重采样后观测的近似有效视数，MERLIN 的原始 RGPI 不与六种 GRD 方法混排。

使用四方向的两侧 3×3 邻域均值比，块中心相对像素偏移为 (±2,0)、(0,±2)、(±2,±2)。7×7 输入窗口计算异质性权重，局部样本方差 ddof=1，负权重截为 0。完整视野仅舍弃外沿 3 像素；H/S/T 按原坐标汇总，并使用完整视野提供的邻域上下文。按有效像素-方向对数量归一化，包含权重为零的项。所有本次输入、输出均严格正值且有限，因此没有零值剔除。整图共有 9,400,356 个有效中心，每个 ROI 为 147,456 个中心，每个中心四方向。

RGPI 使用 float64、gammaln 和 logaddexp 计算自然对数密度，未对概率密度设置截断下限。六项独立测试已通过：逐像素窗口及 SciPy Beta-prime 密度对照、局部方差与 ROI 上下文、全局正增益不变性、恒等输出似然上界、常数场和零值处理。RGPI 评价结构保持，原样输出观测也能得到高分；H 区的低结构权重也使其不适合作为单独的去斑质量排名，应结合 ENL、M-index 和比率图解释。

作者提供的受保护 MATLAB `.p` 程序已在同一小图上运行，但其数值与正文公式实现未一致，不能将本表称为作者程序的直接输出。两版本与测速记录保存在 `seven_methods/rgpi/author_reference/`；本表固定使用上面说明的显式公式及边界约定。

- [七方法 RGPI CSV](seven_methods/rgpi/rgpi.csv)：表中完整精度结果。
- [全部计算协议 CSV](seven_methods/rgpi/rgpi_all_protocols.csv)：另含 GRD 的 H 区有效视数 L=4.367313742898537 敏感性结果，以及 MERLIN 对共同 GRD、L=5 的辅助结果；后者包含产品及投影差异。
- [计算记录 JSON](seven_methods/rgpi/rgpi_report.json)：参数、ROI、方向得分、有效数量、输入输出 SHA-256 和运行环境。
- 脚本：`scripts/iceye_paris/rgpi_metric.py`、`scripts/iceye_paris/evaluate_rgpi.py`；测试：`scripts/iceye_paris/test_rgpi_metric.py`。

重建：在仓库根目录执行 `python scripts/iceye_paris/evaluate_rgpi.py`。验证：`python -m unittest discover -s scripts/iceye_paris -p test_rgpi_metric.py -v`。

### RGPI 下降复核（2026-11-14）

已核验原记录的全部 13 项文件校验和，并从科学数组重新计算七种方法的全图 RGPI，结果与原记录一致。另用直接 3×3 卷积求和独立计算下降量，与两次 RGPI 相减的最大差异为 1.48×10⁻¹²；原有六项测试全部通过。

下降符合公式性质：固定观测、视数、输入权重和有效位置后，设 Q、q 分别为观测与输出的局部均值比，α=9L，则 `RGPI(Y,Y) − RGPI(Y,X̂) = mean[2αW log cosh(0.5 log(q/Q))] ≥ 0`。因此 Noisy 的恒等比较是该条件似然的上限，不是去斑性能基准；“↑”表示同一输入及参数下的局部梯度保持方向，不表示去噪后必须超过 Noisy。全局正增益不改变局部均值比。RGPI 是对数密度的加权均值，负值本身不表示计算错误。

GRD 的恒等参考为 0.0968456509；MERLIN 对应投影 SLC 的恒等参考为 0.0631781142。二者输入和视数不同，不直接排名。下表 Noisy 的 RGPI 不参与方法排名，原始参考数值仍保留在测量 JSON/CSV 中。

本次另在 H、S 内各取固定 128×128 原始强度块，运行作者 MATLAB 程序：H 区 Noisy 为 0.3485575194、SAR-BM3D 为 0.2636266314，同样下降。其他方法也低于各自恒等参考；SAR2SAR 在两块区域的作者程序输出均为 −Inf。作者程序与显式公式的绝对数值差异仍未解决，因此现有结果明确称为“论文公式实现值”，不称为作者程序复现结果，也不混用两套数值。

- [全图复算与独立下降量核验](seven_methods/rgpi/audit_20261114/recheck.json)
- [作者程序的 H/S 小块实测](seven_methods/rgpi/audit_20261114/author_probe.json) / [同样小块的公式实现结果](seven_methods/rgpi/audit_20261114/formula_probe.json)
- 复核脚本：`scripts/iceye_paris/audit_rgpi.py`、`scripts/iceye_paris/audit_rgpi_author.m`。小块实验用于诊断，不替代全图测量。

## 单景四指标测量（2026-11-14）

以下使用已保存的 3072 × 3072 浮点强度结果。ENL 在固定 H 区计算（裁剪内行 1696、列 2624，384 × 384，样本方差 ddof=1）。EPI、M-index 和 RGPI 使用全裁剪；RGPI 排除外侧 3 像素边界。未使用展示亮度匹配，也未对比率分母设置生效的截断。

| 方法 | ENL（H） | M-index（求和式） | EPI（全图） | RGPI（公式版，全图）↑ |
|---|---:|---:|---:|---:|
| Noisy | 4.37 | — | 1.0000 | —（恒等参考 0.0968） |
| SAR-BM3D | 9.33 | N/A | 0.8076 | 0.0809 |
| SAR2SAR | 1.64 | 0.4657 | 0.5929 | -2.8126 |
| SDUDNet* | 4.38 | N/A | 0.4030 | -0.1063 |
| Trans-SAR | 107.21 | N/A | 0.2554 | -0.8099 |
| CL-SAR | 45.02 | 2812.5111 | 0.8218 | -0.1655 |
| MERLIN** | 11.72 | N/A | 0.5948 | -0.0122 |
| MuLoG-DRUNet | 36.81 | 15.1810 | 0.5347 | -0.0450 |

M-index 使用 [Gómez et al. (2017)](https://www.mdpi.com/2072-4292/9/4/389) 式 (1)、(3) 的一阶残差求和形式，窗口 25 × 25、滑动步长 1、相对容差 0.03、8 级全局等宽量化、100 次随机置乱，种子 42，GLCM 水平偏移 (0,1)。这是公开公式和明确窗口约定下的计算，未宣称与作者程序逐值一致。当前项目 `classic_sar_metrics.py` 对一阶项取均值，其对应值另存为 `M_legacy_mean_variant`，不作为本表主值。SAR2SAR、CL-SAR、MuLoG-DRUNet 分别有 12、180378、279 个合格窗口；其余四种滤波输出没有合格窗口，记 N/A。Noisy 的恒等比率不给出 M-index。

CL-SAR 的求和式 M-index 受合格窗口数量影响。SAR2SAR、CL-SAR 等的极大比率还使 8 级量化高度集中，M-index 不用于单独排序；SAR2SAR 的低 M 值不能解释为其暗斑输出质量较好。SDUDNet* 沿用显示域输入。MERLIN** 使用对应投影 SLC 观测，其 RGPI 的有效视数为 4.00202945；其余行使用 GRD，RGPI 名义视数为 5，MERLIN 与这些行的输入协议不同。

ENL/EPI 已重新计算。RGPI 复用前核验了两种输入、七种输出及代码等全部 13 项文件的 SHA-256。M 的局部方差使用 Welford 计算，避免极大比率引起积分图相减精度损失；GLCM 局部均值采用代数等价的覆盖权重求和。两者分别与直接窗口统计、原局部 GLCM 实现核验一致。

- [完整精度 CSV](seven_methods/metrics_20261114/metrics.csv)
- [参数、分量、校验和及数值核验记录](seven_methods/metrics_20261114/report.json)
- 重建命令：`python scripts/iceye_paris/measure_four_metrics.py --workers 2`。

## Lee-MMSE 与均值滤波基线

- [全裁剪对比](analysis/whole_crop_comparison.png) 覆盖完整的 3072 × 3072 展示视野。该视野在 20000 × 20000 像素 GRD 母图中的位置见[整景定位图](previews/full_grd_selected_view.png)。
- [三个区域的局部对比](analysis/roi_comparison.png) 以相同位置和尺度显示原图、Lee-MMSE、均值滤波及两种方法的比率图。H 为农田内部，S 为屋顶边缘，T 为密集住宅散射纹理。

两种滤波均使用 5 × 5 窗口。Lee-MMSE 的窗口沿用项目的 NWPU 验证结果，输入视数采用 GRD 元数据给出的距离向 1 视、方位向 5 视的乘积 5。逐像素在线性强度域计算比率 $R=Y/\hat{X}$，其中 $Y$ 是观测强度，$\hat{X}$ 是滤波强度。强度图共用 −18～0 dB 显示范围，比率图共用 −5～+5 dB，0 dB 对应 $R=1$。整图缩略显示前在 dB 域缩小，局部图取自原像素网格。统计直接使用线性强度和比率。 [比率图分析方法](https://www.mdpi.com/2072-4292/9/4/389)

H 区输入 ENL 为 **4.37**，Lee-MMSE 和均值滤波输出分别为 **19.68** 和 **22.94**，线性比率均值分别为 **0.983** 和 **0.988**。S 区的屋顶边线和 T 区的成排亮散射在两种比率图中均可辨认，均值滤波的轮廓更明显。图中仍可见与场景对齐的结构，表明被去除的成分中可能包含场景细节。 [分区统计 CSV](analysis/ratio_statistics.csv)

巴黎场景的论文模型对比待补，需使用与稿件配置匹配的 Ours-base 和 Ours+AMS 检查点。上述基线图可在仓库根目录运行 `python output/fig3_iceye_paris_20261109/compare_despeckling.py` 重建。

## 官方来源和许可

场景编号：`ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF`。

- [ICEYE Open Data 官方说明](https://sar.iceye.com/6.0.6/opendata/opendata/)
- [该景官方 STAC 元数据](https://iceye-open-data-catalog.s3.us-west-2.amazonaws.com/stac-items/2025/10/ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF.json)
- [完整 GRD 下载（512,206,765 字节）](https://iceye-open-data-catalog.s3.us-west-2.amazonaws.com/data/spot-fine/ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF/ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF_GRD.tif)
- [辐射定标说明](https://sar.iceye.com/6.0.6/foundations/radiometric/#calibration-correction)

影像来源：**ICEYE Open Data，CC BY 4.0**。本目录对官方影像进行了裁剪、强度转换及显示标注；使用或再分发时保留 ICEYE 署名和 [CC BY 4.0 许可链接](https://creativecommons.org/licenses/by/4.0/)。

## 恢复完整数据和重建图像

完整 GRD 和临时候选 `.npy` 数组不纳入 Git。官方 JSON 元数据和 [download_verification.json](raw/download_verification.json) 已保留。

在仓库根目录运行（原脚本使用 macOS Helvetica 字体；图像处理需要 NumPy、Pillow 和 rasterio）：

```sh
python3 output/fig3_iceye_paris_20261109/download_grd.py
python3 output/fig3_iceye_paris_20261109/prepare_views.py
python3 output/fig3_iceye_paris_20261109/export_selected_crop.py
```

这三个脚本恢复整景数据、重建整景和 A/B 候选预览，再导出最终科学裁剪及 H/S/T 图像。`candidate_C_compact_preview.png` 和官方缩略图作为已有选景记录直接保留。重建会更新相应输出和来源记录。

完整 GRD 的本地下载 SHA-256：

```text
d2543836880133997c788de4765f7ea48772fa218c7af5345207d86ef91fcacc
```
