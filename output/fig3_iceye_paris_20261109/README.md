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
