# 导出对比图对应的模型权重

本目录保存下列导出图使用的原始检查点，整理日期为 2026-11-09。六套模型共八个文件，合计 286,253,239 字节；SAR2SAR 的 TensorFlow 检查点包含三个配套文件。每个文件均与实际推理记录中的 SHA-256 一致，未转换、裁剪或重新训练。

| 图片 | 方法 | 本目录中的权重 |
| --- | --- | --- |
| `a_noisy.png` | Noisy | 输入噪声图，无权重 |
| `b_sar-bm3d.png` | SAR-BM3D | 传统算法，无训练权重 |
| `c_sar2sar.png` | SAR2SAR | `sar2sar/SAR2SAR-tensorflow-98550.{data-00000-of-00001,index,meta}` |
| `d_sdudnet.png` | SDUDNet | `sdudnet/real.pth` |
| `e_trans-sar.png` | Trans-SAR | `trans-sar/model.pth`，官方 TransSARV2 |
| `f_cl-sar.png` | CL-SAR | `cl-sar/net_g_latest.pth`，MDN1-default |
| `g_merlin.png` | MERLIN | `merlin/spotlight.pth` |
| `h_mulog-drunet.png` | MuLoG-DRUNet | `mulog-drunet/generic_model.pth` |

## 下载与校验

由于当前 Gitee 仓库不支持 Git LFS，权重以每片最多 32 MiB 的 `.partNNN` 二进制文件保存于普通 Git。分片是原文件按字节切分，合并后与原始检查点完全一致。克隆仓库后在仓库根目录执行（仅需 Python 标准库）：

```sh
python trained_models/comparison_baselines/restore_weights.py
python trained_models/comparison_baselines/verify_weights.py
```

`restore_weights.py` 先检查所有分片，再合并到本目录的对应子目录，并检查完整文件的大小和 SHA-256。已存在且相同的文件会跳过；不同内容的文件不会被覆盖。`--destination DIR` 可将完整权重恢复到其他空目录。

`manifest.json` 记录完整文件和每个分片的大小、SHA-256、原始推理路径、作者仓库与固定提交，以及对应导出运行记录的路径和哈希。`restore_path` 相对仓库根目录，表示现有推理脚本使用的原始路径；需要运行原脚本时，将对应文件复制回该位置。SAR2SAR 的三个文件必须保留共同前缀。

## 来源与复现说明

权重映射来自 `output/umbra_buenos_aires_multimethod_1024/figure3/manifest.json` 指向的运行记录。这里的 Trans-SAR 是作者发布的基线检查点，不能与本项目的频域变体或 AMS 权重混用；SDUDNet 使用 real 版本，CL-SAR 使用 MDN1-default，MERLIN 使用 Spotlight。

权重本身不足以复现图片的显示结果。需同时使用对应的输入、归一化、分块与显示设置；SDUDNet 使用记录中的 dB 显示域输入，MERLIN 使用记录中的复数输入与重叠汇总方式。既有适配脚本位于 `scripts/`。

上游来源与版本见清单；随附本地上游快照提供的 SAR2SAR、Trans-SAR、MERLIN 许可证。SDUDNet、CL-SAR、MuLoG-DRUNet 的权重保留其原作者归属，本目录不为第三方权重另授许可。SAR-BM3D 没有训练权重，本目录不包含其作者二进制程序。
