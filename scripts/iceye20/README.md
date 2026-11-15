# ICEYE20：数据准备与待运行测试

本次已完成20景完整SLC下载、H/S/T区域切分和输入预览复核。测试脚本只做静态检查，**没有运行模型推理、四项指标评价或数值回归实验**。

## 数据位置

| 内容 | 位置 |
|---|---|
| 完整原始SLC，20景、78,086,334,854字节 | `E:\SAR_datasets\iceye20\raw\<采集ID>\SLC.tif` |
| 数据集入口及元数据 | `D:\research\sar_transformer-main\datasets\iceye20` |
| 原始文件URL、尺寸、平台和下载体量 | `datasets/iceye20/manifest.json` |
| 文件大小、ETag和本地SHA-256记录 | `datasets/iceye20/download_records/<采集ID>.json` |
| 固定区域坐标和数组校验值 | `datasets/iceye20/regions_manifest.json` |
| 数据固定记录 | `datasets/iceye20/dataset_seal.json` |
| 60个256×256区域 | `datasets/iceye20/table_v/{homogeneous,structural,texture}` |
| 三类区域各20张预览的拼图 | `datasets/iceye20/previews/table_v_<类别>.jpg` |
| 各景全图及区域位置 | `datasets/iceye20/regions/<采集ID>/full_scene_regions.png` |
| 每景10个64×64 ENL区域 | `datasets/iceye20/regions/<采集ID>/table_iv_enl_intensity.npy` |

每个TABLE V区域包含线性强度`*_intensity.npy`、复数`*_complex.npy`、显示预览`*_preview.png`和来源坐标JSON。每景每类各选1个，共60个区域；三类区域在各景内互不重叠。每个区域另固定5个32×32 ENL子区域，共300个。类别依据原始SAR的外观结构划分，不是地物真值标签。

原始影像保留全部像素，没有缩放为统一尺寸。TABLE IV仍以20景为统计单位，推理块不计作独立影像。TABLE II保持不变。

## 数值读取

`slc.py`先读取GeoTIFF波段的scale/offset，再反解`iceye:amplitude_mapping`：

```text
mapped_amplitude = raw_band_1 * band_1_scale + band_1_offset
amplitude = mapped_amplitude ** (1 / exponent) / mapping_scale
phase = raw_band_2 * band_2_scale + band_2_offset
S = amplitude * exp(1j * phase)
Y = amplitude ** 2
```

科学数组采用原生SLC幅度平方单位，未混入GRD、8位显示图或拟合增益。复数数据和强度数据共享原始网格。GeoTIFF内置低分辨率overview仅用于显示和位置图，不作为指标输入。

编码依据：[ICEYE产品说明](https://sar.iceye.com/6.0.8/productspecification/dataproducts/)、[幅度映射元数据说明](https://sar.iceye.com/6.0.8/productFormats/metadata/#amplitude-mapping)。来源：[ICEYE Open Data](https://sar.iceye.com/6.0.6/opendata/opendata/)，CC-BY-4.0，署名ICEYE。

## 测试入口（尚未运行）

在项目根目录运行。两份正式权重按用户安排保留为参数，未使用本地历史e47/e8文件代替。

```powershell
& '.\.venv-iceye20\Scripts\python.exe' scripts/iceye20/run_experiment.py `
  --base-checkpoint '正式Ours-base权重的完整路径' `
  --ams-checkpoint '正式Ours+AMS权重的完整路径'
```

入口依次执行：核对固定数据与权重身份 → 解码一景 → 逐方法整景推理 → 完整有效区域指标 → 提取固定TABLE V区域 → 汇总两张均值表。编码器状态会在base/AMS之间逐项核对。九种方法为SAR-BM3D、SAR2SAR、SDUDNet、Trans-SAR、CL-SAR、MERLIN、MuLoG-DRUNet、Ours-base、Ours+AMS。

各基线使用项目中已有的专用虚拟环境，SAR-BM3D使用MATLAB。`.venv-ours-legacy`在这里仅提供Python/PyTorch运行环境；Ours实际加载的是用户指定并经元数据检查的当前`intensity_v1`模型。

默认结果位置为`output/iceye20`，工作目录为`E:\SAR_datasets\iceye20\work`。可用`--results`、`--work-root`修改。已完成的场景/方法在数据、代码、权重均一致时跳过。某方法失败时停止本次运行，已完成结果和未完成输出均保留；`--retry-incomplete`会先把未完成的输入解码或方法工作目录改名保留，再重新执行，需保证额外空间。指标已经完成但预测尚未归档时，恢复运行会先完成归档，不重复推理。

数据、代码或权重改变后，应同时指定新的结果目录和工作目录，避免复用另一配置的中间预测。

## 方法适配与整景计算

| 方法 | 固定输入/输出变换与执行方式 |
|---|---|
| SAR-BM3D | 幅度输入、强度输出，L=1，512核心＋64上下文 |
| SAR2SAR | 原始幅度及作者固定对数归一化；256窗口、步长64；在归一化对数域均匀合并 |
| SDUDNet | 线性强度除以整景峰值；输出乘回相同峰值；没有dB显示图转换 |
| Trans-SAR | 整景峰值归一化幅度及作者映射；输出恢复原强度单位 |
| CL-SAR | 整景非零幅度最小值和最大值；作者归一化与反变换 |
| MERLIN | 原生复数SLC，作者逐窗口频谱对称化，256窗口、步长64，均匀合并 |
| MuLoG-DRUNet | D=1，L=1，10次全局ADMM；全景PCA均值和全景分位数；仅DRUNet按512核心＋128上下文执行 |
| Ours-base / Ours+AMS | 当前`intensity_v1`，共同整景峰值归一化；256输入、192核心、32上下文 |

神经网络分块限制其空间上下文和傅里叶支持，不声称等价于一次性将完整影像送入网络。新整景流式适配器尚未做数值运行验证。MuLoG复用作者标量Newton近端算子，使用磁盘映射保留全局ADMM状态，不把独立块ADMM当成整景ADMM。

所有方法在输出保存前采用同一正值下限`1e-6 × 原始整景有效强度均值`。负值比例和受下限影响的比例写入推理记录。NaN/Inf使该方法/场景失败；不会按方法输出缩小输入固定掩膜。

## 指标与均值表

- ENL：每景先平均10个固定64×64区域；TABLE V每个区域先平均5个固定32×32子区域。
- M-index：25×25窗口、0.03容差、8级量化、100次全景有效像素随机置乱、种子42。没有合格窗口时记缺失。整景使用全局比率量化范围和全局统计，不平均分块M-index。
- EPI：沿用项目稿件对应实现的右下对角相邻像素绝对差之和比值。
- RGPI：沿用项目的Ma 2022公式实现，四方向、3×3块、7×7权重、方差ddof=1、L=1；固定输入支持，零权重项仍计入有效像素方向对总数。
- TABLE IV：20景等权均值。TABLE V：每类20个区域均值，Average为三类均值的等权平均。只输出均值，不输出标准差或置信区间。
- 缺失指标不填0；JSON保留原因和有效数量，表后列出少于预期的有效样本数。

科学数组使用线性强度。展示使用输入确定的统一对数显示范围，比率预览范围固定为0–3。ENL不作整体质量排名，EPI/RGPI与M-index及比率图共同解释。

完成运行后生成：

```text
output/iceye20/
  run_config.json
  checkpoint_pair.json
  scenes/<采集ID>/<方法>/
    inference.json
    table_iv.json
    table_v.json
    full_scene_preview.png
    full_ratio_preview.png
    homogeneous_intensity.npy / structural_intensity.npy / texture_intensity.npy  # 所有方法，用于局部视觉比较
  comparisons/<采集ID>/  # 全图、H/S/T与比率图的十方法对照
  summary.json
  TABLE_IV_TABLE_V.md
  completion.json
```

均值表也可由已有结果重新汇总，不需要再推理：

```powershell
& '.\.venv-iceye20\Scripts\python.exe' scripts/iceye20/summarize.py --results output/iceye20
```

没有生成Excel文件。

## 存储与当前检查范围

默认在整景指标、全图预览和局部科学数组保存成功后，删除本次工作目录中的临时整景预测，避免累计存储180幅浮点影像。原始SLC和固定切分数据不删除。保留全部完整浮点预测可添加：

```text
--keep-full --full-output-root <足够空间的目录>
```

全部预测约需632.5 GB；最大场景的流式工作空间估算约128.5 GB（含5 GB余量）。脚本会检查空间。这些是尺寸计算值，不是实测运行资源。

本轮已检查：20份下载记录与文件大小、原生尺寸/编码、60个裁剪与原图的一致性、强度/复数幅度平方的一致性、区域边界及数量、输入预览、Python语法编译和pyflakes静态分析。尚未检查：模型实际前向、MATLAB运行、流式算法数值等价性、真实耗时与最终指标。

## 重建数据

已有清单时可断点续传完整SLC：

```powershell
python scripts/iceye20/download_ranges.py --workers 64
& '.\.venv-iceye20\Scripts\python.exe' scripts/iceye20/prepare_regions.py --watch
```

已固定的数据集不要原地更换区域；需要新选区时使用新的数据目录和版本，避免混用前后结果。下载最初的20景清单及元数据可由`download.py`建立；现有`manifest.json`已经保存本批完整URL。
