现有训练日志与学习曲线（2026-11-13）

已绘制：TransSARV2_DualFreqNG_Bottle 的监督训练（50 轮）和 AMS（8 轮）。作者于 2026-11-13 确认这两份记录可直接用于论文学习曲线，并确认学习率分别为 2e-4 和 2e-6。
原始记录：D:\research\sar_transformer-main\ExperimentalRecord.txt
监督训练：第 251-300 行，2026-05-04；AMS：第 310-317 行，2026-05-06。
两次运行逐轮记录完整，无缺轮、重复轮或非有限值；最小验证损失对应第 47 / 8 轮，与日志的 best_model 条目一致。

文件：
training_validation_loss：两个阶段各自的训练/验证损失（PNG、PDF、SVG）。
fig_learning_supervised / fig_learning_ams：论文中分别使用的两张单栏图（PNG、PDF、SVG）。
historical_supervised_metrics.csv / historical_ams_metrics.csv：逐轮损失、训练参数及来源行号。
figure_metadata.json：数据来源、SHA-256、运行标识及处理说明。

数据口径：
1. 所有图均使用日志原值，不平滑、不补点。监督训练损失包含 TV 项，验证损失为 MSE，二者不等同于同一定义的训练/验证 MSE。
2. AMS 的 val_loss / val_selfsup_loss 是真实 SAR 自监督损失。每个点对应日志中的一轮，星号标记最小验证损失。
3. 初始学习率为监督训练 2e-4、AMS 2e-6。正文实验在另一台机器上运行；图表采用作者确认的损失记录，其他设置以返修稿为准。

其他已检查记录：
- ExperimentalRecord.txt 还包含 5 个其他模型的监督记录（40-50 轮）；.tmp 是相同副本，notebook checkpoint 是较早副本。
- experiments_repro/p0_ablation/full_seed42/epoch_metrics.csv 有 45/100 轮，是 BSDS500 旧协议，未混入上述图。
- experiments_repro/nwpu_p0_ablation/full_seed42/epoch_metrics.csv 只有表头。
- experiments_smoke 中 12 份 epoch_metrics.csv 均只有 1 轮。
- 本地项目搜索未找到 step_metrics.csv、train_progress.jsonl 或 TensorBoard 事件文件。

观察：监督训练和验证损失总体下降，验证端仍有波动；AMS 训练与验证自监督损失均下降。

复现：python scripts/plot_training_learning_curves.py
绘图代码：D:\research\sar_transformer-main\scripts\plot_training_learning_curves.py
