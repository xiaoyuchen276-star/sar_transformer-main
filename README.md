# Transformer based SAR image despeckling

This repository contains source code, configurations, documentation, and example
figures. Six comparison-model checkpoints are included as verified binary parts
under [`trained_models/comparison_baselines/`](trained_models/comparison_baselines/README.md).
Datasets, other model checkpoints, and most generated experiment outputs remain
excluded from Git. See the download, restore, and inference instructions below.

For the original SAR-BM3D v1.0 on local Windows/MATLAB, see
[SAR-BM3D 本地复现说明](docs/SAR_BM3D_LOCAL.md).

For local SAR-CAM training/inference and SAR2SAR pretrained inference, see
[SAR-CAM 与 SAR2SAR 本地运行](docs/SAR_CAM_SAR2SAR_LOCAL.md).

For local SDUDNet inference with the authors' pretrained weights, see
[SDUDNet 本地运行](docs/SDUDNET_LOCAL.md).

For local CL-SAR and MuLoG-DRUNet inference with the authors' pretrained weights,
see [CL-SAR 本地运行](docs/CL_SAR_LOCAL.md) and
[MuLoG-DRUNet 本地运行](docs/MULOG_DRUNET_LOCAL.md).
Both adapters require an explicit intensity/amplitude input domain; MuLoG-DRUNet
also requires an explicit number of looks. Their local smoke tests do not change
the frozen ICSPS/GRSL evaluation protocol or establish a new performance ranking.
CL-SAR and MuLoG-DRUNet pretrained inference have been run locally. The exact
checkpoints used by the exported comparison panels are now included below.

## 对比模型权重：下载、还原与使用

### 1. 下载权重

从 Gitee 或 GitHub **任选一个**仓库克隆，在仓库根目录执行后续命令：

```sh
# Gitee
git clone --depth 1 https://gitee.com/chy66666/sar_transformer-main.git
# 或 GitHub（不要在同一目录重复执行两次 clone）
# git clone --depth 1 https://github.com/Chen166-cloud/sar_transformer-main.git
cd sar_transformer-main
```

已有本地仓库可执行 `git pull --ff-only origin main`；若 GitHub 的远程名称为
`github`，则使用 `git pull --ff-only github main`。更新前先保存本地修改。

两处仓库保存相同的六套模型，共八个完整权重文件、14 个分片，原始总大小
**286,253,239 字节（约 273 MiB）**。当前 Gitee 仓库不支持 LFS，因此两端统一使用
普通 Git 保存每片最多 32 MiB 的 `.partNNN` 文件，**无需安装 Git LFS**。
也可从仓库页面下载 ZIP 并解压；应保留整个 `trained_models/comparison_baselines/`
目录，包括清单、脚本和全部分片。下面的源代码克隆步骤仍需要 Git。

### 2. 还原并校验完整文件

仅还原与校验需要 Python 3 标准库，无需 PyTorch、TensorFlow 或 GPU：

```sh
python trained_models/comparison_baselines/restore_weights.py
python trained_models/comparison_baselines/verify_weights.py
```

成功时输出 `Verified 8 complete checkpoint files.` 和 `Verified 8 checkpoint files.`。
还原脚本逐片检查大小与 SHA-256，合并后再次核对完整文件。相同的已有文件会跳过，
不同内容的已有文件不会被覆盖。不要把 `.partNNN` 直接传给模型加载函数。

需要保存到其他目录时，可运行
`python trained_models/comparison_baselines/restore_weights.py --destination D:/SAR_weights`。
该命令同样完成校验；`verify_weights.py` 固定检查默认目录，不检查自定义目录。
同时保留分片和还原文件约需 546 MiB 磁盘空间，不含源码、环境和数据。

下表中的权重路径相对 `trained_models/comparison_baselines/`：

| 导出图片 | 方法 / 权重版本 | 还原后的文件 |
| --- | --- | --- |
| `a_noisy.png` | Noisy，原始输入 | 无权重 |
| `b_sar-bm3d.png` | SAR-BM3D，传统算法 | 无训练权重；程序安装见 [SAR-BM3D 说明](docs/SAR_BM3D_LOCAL.md) |
| `c_sar2sar.png` | SAR2SAR，官方 Single-Look TensorFlow 检查点 | `sar2sar/SAR2SAR-tensorflow-98550.data-00000-of-00001`、同前缀 `.index` 与 `.meta` |
| `d_sdudnet.png` | SDUDNet，real | `sdudnet/real.pth` |
| `e_trans-sar.png` | Trans-SAR，官方 TransSARV2 | `trans-sar/model.pth` |
| `f_cl-sar.png` | CL-SAR，MDN1-default | `cl-sar/net_g_latest.pth` |
| `g_merlin.png` | MERLIN，Spotlight | `merlin/spotlight.pth` |
| `h_mulog-drunet.png` | MuLoG-DRUNet，generic | `mulog-drunet/generic_model.pth` |

作者仓库、固定提交、每个文件及分片的 SHA-256、导出运行记录索引均见
[`manifest.json`](trained_models/comparison_baselines/manifest.json)。Trans-SAR 使用
官方基线，不能替换成本项目的频域变体或 AMS 权重；SAR2SAR 必须保留三个配套文件。

### 3. 准备运行环境和作者源码

还原权重不会安装模型架构、依赖或来源记录。以下为 **Windows PowerShell** 命令，
在仓库根目录运行；按所需方法选择安装。将解释器路径替换为本机路径：

```powershell
# SAR2SAR 使用单独的 Python 3.12 / TensorFlow compat.v1 环境
& .\scripts\sar2sar\setup_windows.ps1 -PythonExecutable 'C:\path\to\python312\python.exe'

# 其余三个入口复用已有 PyTorch 环境，建议采用已验证的 Python 3.12 / PyTorch 2.5.1
$BasePython = 'C:\path\to\pytorch_env\python.exe'
& .\scripts\sdudnet\setup_windows.ps1 -BasePython $BasePython
& .\scripts\cl_sar\setup_windows.ps1 -BasePython $BasePython
& .\scripts\mulog_drunet\setup_windows.ps1 -BasePython $BasePython
```

这些安装入口会联网获取固定版本源码、依赖和所需来源记录，部分还会下载上游权重；
本目录不是完整的离线运行环境。**先完成 setup，再按下一步放置已还原的权重**。
尤其 MuLoG-DRUNet 还要求 `py_functions.zip` 和有效的 `source_manifest.json`，
仅复制 `.pth` 不能替代来源校验。安装细节见
[SAR2SAR](docs/SAR_CAM_SAR2SAR_LOCAL.md)、[SDUDNet](docs/SDUDNET_LOCAL.md)、
[CL-SAR](docs/CL_SAR_LOCAL.md)、[MuLoG-DRUNet](docs/MULOG_DRUNET_LOCAL.md)。

Trans-SAR 和 MERLIN 的现有 ROI 脚本需要以下固定作者源码。仅在相应目录尚不存在时克隆；
已有目录应核对提交，不要覆盖本地修改：

```sh
git clone https://github.com/malshaV/sar_transformer.git external/TransSAR_official
git -C external/TransSAR_official checkout --detach b3ac845f96f2332aa4f1af94b455f71630978b17
git clone https://github.com/hi-paris/deepdespeckling.git external/deepdespeckling
git -C external/deepdespeckling checkout --detach b9bf54a013933a8dbfa63d5e02cd5b0a7acd7efc
```

使用已配置 PyTorch、NumPy、SciPy、Pillow、timm 的推理环境运行 Trans-SAR。
MERLIN 在相应推理环境中执行 `python -m pip install -e external/deepdespeckling`，
使导入的模型与这个源码目录中的权重对应。以下两个方法的 `python` 指该推理环境，
不使用下文历史上游示例的 Python 3.6 环境。

### 4. 将权重放到现有脚本读取的位置

默认还原目录与推理脚本读取目录不同。完成相应方法的源码和环境安装后，按下表复制文件；
在目标目录已存在同名文件时，先与清单中的 SHA-256 比较，相同则无需复制。

| 本目录下的文件 | 相对仓库根目录的目标位置 |
| --- | --- |
| `sar2sar/SAR2SAR-tensorflow-98550.*`（三个完整文件） | `external/SAR2SAR/SAR2SAR-test/checkpoint/` |
| `sdudnet/real.pth` | `external/SDUDNet/models/real.pth` |
| `trans-sar/model.pth` | `pretrained_models/model.pth`，也可通过下方 `--checkpoint` 直接指定还原文件 |
| `cl-sar/net_g_latest.pth` | `external/CL-SAR/experiments/MDN1-default/models/net_g_latest.pth` |
| `merlin/spotlight.pth` | `external/deepdespeckling/deepdespeckling/merlin/saved_models/spotlight.pth` |
| `mulog-drunet/generic_model.pth` | `external/MuLoG-DRUNet/models/generic_model.pth` |

清单中每个文件的 `restore_path` 就是上述目标路径；`--destination` 只改变还原根目录，
不会自动将文件分发到这些位置。可用 PowerShell 的 `Get-FileHash -Algorithm SHA256`
检查复制后的文件。

### 5. 运行推理

下面的输入路径是示例，需要替换为实际数据。单通道线性强度、幅度和显示用 PNG
不是同一数据域；请使用与输入相符的参数。SAR2SAR 要求图像至少为 256×256。
CL-SAR 的输出会在归一化幅度域裁剪到 [0,1]：下方 `-Scale 1` 适用于已经具有相应
归一化尺度的数据；原始强度应使用预先确定的强度除数作为 `-Scale`，并记录该值。
重复运行时使用新的输出目录，CL-SAR 会拒绝写入已有非空目录。

```powershell
# SAR2SAR：单通道幅度 .npy；若输入为线性强度，改用 -InputDomain intensity
& .\scripts\sar2sar\run_windows.ps1 -InputPath '.\data\amplitude.npy' -InputDomain amplitude -OutputDir '.\output\demo_sar2sar'

# SDUDNet：real 权重；这里示例为灰度显示图，导出对比图使用固定 dB 显示映射
& .\scripts\sdudnet\run_windows.ps1 -InputPath '.\data\noisy_display.png' -Model real -OutputDir '.\output\demo_sdudnet'

# CL-SAR：示例输入为 [0,1] 线性强度；原始数据需按上述说明设置 Scale
& .\scripts\cl_sar\run_windows.ps1 -InputPath '.\data\intensity.npy' -InputDomain intensity -Scale 1 -OutputPath '.\output\demo_clsar'

# MuLoG-DRUNet：此处 Looks 1 仅对应单视数据，其他数据需填写实际视数
& .\scripts\mulog_drunet\run_windows.ps1 -InputPath '.\data\intensity.npy' -InputDomain intensity -Looks 1 -Iterations 10 -OutputDir '.\output\demo_mulog'
```

Trans-SAR 的现有适配器读取二维、非负、有限的 `float32` 线性强度 `.npy`，
尺寸至少为 256×256，并要求与该 ROI 对应的准备记录 `run.json`（含 `roi`、`source`
等来源字段）。使用真实的 ROI 准备记录；缺少该记录时不能直接运行这个复现入口。

```sh
python scripts/transsar/run_umbra_official.py --input data/noisy_intensity.npy --parent-run-json data/run.json --checkpoint trained_models/comparison_baselines/trans-sar/model.pth --device cuda --output-dir output/demo_transsar
```

MERLIN 的现有脚本限定为 **1024×1024、complex64 的原始复数 ROI**，需要同一 ROI
的 `float32` 线性强度参考数组（实部平方加虚部平方）。普通灰度 PNG 无法提供所需复数输入。
先运行 stride=64 的均匀汇总，再运行导出图采用的加权汇总：

```sh
python scripts/merlin/run_umbra_buenos_aires.py --input data/sicd_complex_roi.npy --reference-intensity data/noisy_intensity.npy --stride-size 64 --output-dir output/demo_merlin_uniform
python scripts/merlin/run_weighted_overlap.py --input data/sicd_complex_roi.npy --reference-noisy data/noisy_intensity.npy --reference-uniform-stride64 output/demo_merlin_uniform/denoised.npy --output-dir output/demo_merlin_weighted
```

各入口在指定输出目录保存数值结果及运行记录，具体文件见对应脚本。上述命令用于加载
这些权重；要复现已导出的图片，还需使用对应原始数据、裁剪位置、归一化、分块和显示
设置。历史原始数据及多数运行输出未随仓库分发，不能仅凭 PNG 文件名重建原实验输入。

缺少分片时重新下载或更新仓库；校验失败时核对 `manifest.json` 中的大小与哈希。
遇到缺少 `external/` 源码、来源记录或 Python 包的错误，应先完成对应安装步骤。
不要将本节的八个检查点与 `trained_models/` 中其他历史训练模型混用。

## Dataset location

All datasets are stored under [`datasets/`](datasets/README.md). Use
`datasets/<dataset-name>` for data paths; the original top-level compatibility
junctions have been removed. Docker uses `/workspace/datasets/` through the
project mount. See the dataset guide for each dataset's purpose.

> **Reproducibility update:** the historical commands below describe the upstream
> project only. `REPRODUCIBLE_EXPERIMENTS.md` documents the general historical
> cleanup, but **ICSPS 2026 formal runs must use only** the frozen ICSPS documents
> linked below and `scripts/icsps2026/`. In particular, do not train directly from
> `datasets/bsds500_synthetic_dataset/train` because that legacy directory contains
> official BSDS500 test images.


## Using the code:

The code is stable while using Python 3.6.13, CUDA >=10.1

- Clone this repository:
```bash
git clone git@gitee.com:chy66666/sar_transformer-main.git
cd sar_transformer-main
```

To install all the dependencies using conda:

```bash
conda env create -f environment.yml
conda activate sar
```

For the native Apple Silicon (`linux/arm64`) Docker environment, see
[APPLE_SILICON_DOCKER.md](APPLE_SILICON_DOCKER.md).

For the frozen ICSPS 2026 SAR-despeckling protocol and the Ubuntu 22.04 / dual
RTX 4090 server workflow, use
[docs/ICSPS2026_SAR去斑网络设计与实验方案.md](docs/ICSPS2026_SAR去斑网络设计与实验方案.md)
and
[docs/ICSPS2026_远程服务器运行手册.md](docs/ICSPS2026_远程服务器运行手册.md).
Those entry points target Python 3.12, PyTorch 2.5.1 + CUDA 12.4, and do not use
the historical Python 3.6 environment below.

If you prefer pip, install following versions:

```bash
timm==0.3.2
mmcv-full==1.2.7
torch==1.7.1
torchvision==0.8.2
opencv-python==4.5.1.48
```


## Creating synthetic data:
This network was trained synthetic SAR images generated using [BSD500](https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/bsds/). To create the synthetic data use create_synthetic_data.py file.

## To  train the network:

```   
python train.py --batch_size 1 --epoch 400 --modelname "TransSARV2" --learning_rate 0.0002 --train_dataset "path_to_training_data" --val_dataset "path_to _validation_data" --direc "path_to_save_results" --crop 256
```

## To test the network:

```   
python test.py --loadmodel "./pretrained_models/model.pth" --save_path "./test_images/" --model "TransSARV2"
```
