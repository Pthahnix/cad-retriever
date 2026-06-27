# CAD 草图检索系统 — 全流程系统设计（项目计划书）

> 日期: 2026-06-27
> 状态: 设计完成，待评审
> 范围: 从现有资产（Gitee `model-retrieval` 代码 + ABC chunk1 数据）开始，覆盖 数据 → 训练 → 评估 → 部署 → 交付 全流程。
> 粒度: plan 级技术实现蓝图（给出可执行的技术决策、接口契约、目录结构、命令意图），但不贴具体代码实现。
> 主干策略: **消融驱动**，模型主干由实验而非预设决定。

---

## 0. 文档约定

- 本文是**单一事实来源**。所有阶段、产物、阈值、决策规则以此为准。
- 出现"待回填"的阈值，均标注了"回填依据"（看哪张分布图/哪个指标定），不是 TODO，而是**显式的、数据驱动的定值流程**。
- 涉及具体代码处，只描述"做什么、输入输出、依赖谁、失败如何处理"，不给实现代码。
- 路径约定：训练/数据落盘在 GPU 机的大数据盘（沿用历史 `~/data` 约定，详见第 11 节环境约束）；代码仓库目录不写大数据。

---

## 1. 背景与目标

### 1.1 任务定义

草图 → CAD 零件**实例检索**（instance retrieval）。用户提交一张 2D 草图（手绘或 PhotoSketch 风格），系统返回库中 Top-K 个最匹配的具体 CAD 模型。**每个 CAD 模型自成一类**——目标是召回那一个正确模型，而非它的类别。

主指标：Top-1 / Top-10 / Top-20 / Top-50 / Top-100 检索准确率。

### 1.2 与原方案的关系（为何转向）

原计划（见 `context/history/`）是 OpenCLIP ViT-B/16 + LoRA + 投影头，在 1M ABC 模型上做对比学习，草图用边缘检测+扰动**合成**。该路线有一次失败执行（recall@1≈0），根因是训练 bug（Phase-1 视角一致性损失无负样本导致 embedding 坍缩、`torch.no_grad` 挡住 LoRA 梯度、PIL 渲染质量不可用）叠加合成草图与真实草图分布差异。

转向动机：Gitee `model-retrieval` 仓库提供了一套**已能跑通**的双分支 sketch→CAD 检索代码，且其数据管线用 **PhotoSketch（预训练 GAN）**产出风格真实的草图。因此原方案里"最贵最险的草图合成"那一步大幅缩减为"**基于现有数据集，缺什么补什么**"。

本项目以 Gitee 这套方法为新主线，原 OpenCLIP 路线降级为**可选对比臂**（仅在消融中作为草图侧编码器候选）。

### 1.3 目标与非目标

**做**：
- 把现有 ~8.4K 模型的数据集补齐缺口，跑通"数据→训练→评估→部署"全流程并交付。
- 用消融实验**经验性地**确定模型主干（CNN / GNN / BOTH，草图侧 SE-ResNet50 / CLIP-ViT+LoRA）。
- 交付一个可用的在线检索服务（Rust/axum）+ 复用现有 Astro 前端 demo。
- 数据管线写成**可扩展、可复现**：现有 8.4K 阶段沿用原管线，同时建一个开源兼容层供扩规模时复现。

**不做**（本期）：
- 文本检索（但若主干含 CLIP 则保留其文本对齐能力作为未来扩展点，不投入优化）。
- CAD 生成/编辑、参数化重建。
- 装配体级检索（仅零件级；装配体在数据筛选阶段分流，见第 4 节）。
- 分布式/多机部署、Kubernetes、多租户。

### 1.4 成功标准（交付级）

- 全流程可一键复现：从现有数据 → 训练出选定主干模型 → 建索引 → 起服务 → 前端可查。
- 在 ~8.4K 库上，选定主干的留出草图集 Top-1 与 Top-10 达到经评审认可的水平（目标见第 6 节，最终阈值由消融基线 + 决策规则确定，而非预设魔法数）。
- 在线服务 `POST /search` 端到端可用，单卡 5090 上 p95 延迟在交互级（< 数百 ms，主要成本在一次 CNN 前向 + 一次向量检索）。
- 交付物齐全（见第 9 节交付清单）。

---

## 2. 现状盘点（资产与缺口）

### 2.1 已有代码资产（Gitee `model-retrieval`）

仓库是一套完整可跑的双分支 sketch→CAD 实例检索研究代码，已通读确认结构：

| 模块 | 文件 | 职责 |
|---|---|---|
| 训练入口 | `train.py` / `trainer.py` | 配置展开、建模、数据、loss、优化器、训练循环、存档 |
| 测试/检索 | `test.py` / `inference.py` | 提特征、建 FAISS 索引、检索、算 Top-K 指标 |
| 模型 | `model/Baseline/networks/baseline.py` | 双分支 `Baseline`，`baseline_step1..5` 渐进消融 |
| 草图/视图编码器 | 同上 `CNN` 类 | 共享 CNN 骨架（SE-ResNet50 等），多视图 max-pool |
| B-rep 图编码器 | `complex_gnn.py` + `encoders/` | UV-Net 风格面/边 UV-grid + 多聚合图编码器 |
| 可选模块 | `cross_attention.py` / `channel_grouping.py` / `feature_fusion.py` / `domain_discriminator.py` | 跨模态注意力 / 关键区域 / 多视图融合 / 域对抗（梯度反转） |
| 损失 | `utils/loss.py` | `HardTripletMarginLoss`(V2默认) / `InfoNCE` / `PairLoss` / `CorrLoss` |
| 数据集 | `data/retrieval/ABC/V2/dataset.py` | `ABC_V2`，12 视图（顶6+底6），按顶/底取对应视图组 |
| 配置 | `utils/config.py` | `ABC_V2`: `num_classes=8422`, `n_views=6`(顶/底各6), `collate_fn=abc_collate_fn_v2` |
| 部署参考 | `C++/` | libtorch + OpenCV + hnswlib 的 C++ 检索 demo |

**关键事实**（来自 `config.py`）：`ABC_V2` 即 ABC 第一个 STEP chunk（~10K）经两轮去重后的 ~8,422 模型。每模型 12 视图（顶半球 6 + 底半球 6），检索时顶/底各产一条特征，故去重比 `deduplicate_ratio=2`。

### 2.2 已有数据资产

- `data/retrieval/ABC/V2/input/` 提交了少量样例查询草图子目录（每目录 0.png/1.png/...），用于 demo/冒烟。
- 真正的训练数据（`views/`、`sketches/`、`train/`、`test/`、`graph*.pt`）**不在仓库**——README 指向校内网盘（pan.zju.edu.cn）下载，需另行获取或本地重建。
- `seresnet50.a1_in1k.bin` 预训练权重需放 `model/Baseline/path_state_dict/`（README 指明）。

### 2.3 原项目可复用资产（`context/history/`）

- `src/cad_retriever/data/`：OCC/OCP 的 STEP→mesh、渲染、边缘检测代码（开源可复现层的基础）。
- `download.py`：ABC 下载（7z header 校验 + 5x 重试 + resume + 代理），可复用于扩规模。
- download-probe 设计（`docs/superpowers/specs/2026-06-11-download-probe-design.md`）：LanceDB manifest + 拓扑探查质量筛选，扩规模时直接接入。
- `web/`：Astro 静态站点 + three.js 模型查看器（前端 demo 复用对象）。

### 2.4 缺口清单（"缺什么补什么"的"什么"）

按优先级：

1. **数据落地**：把网盘上的 `views/sketches/train/test` 取到 GPU 机，或用开源兼容层从 STEP 重建（第 4 节）。
2. **B-rep 图数据**：GNN/BOTH 分支需要 `graph*.pt`（每模型一张 UV-grid 图）。这是 8.4K 阶段**最主要的补全项**——需写 STEP→图 提取器（OCC 拓扑遍历 + UV 采样），失败模型回退 CNN-only。
3. **环境对齐**：仓库依赖 `timm`、`torch_geometric`、`faiss`、`tensorboardX`、`thop`、`warmup_scheduler` 等；需在 5090/CUDA12.8 上装齐并验证（尤其 PyG 与 torch 2.8 的兼容）。
4. **质量/失败清单**：渲染失败、图提取失败、去重剔除的模型需显式记录（沿用 download-probe 的 manifest 思路），避免隐式筛选。
5. **导出与服务**：sketch 编码器 → ONNX；Rust/axum 服务；产物交接契约（第 7 节）——仓库只有 C++ 参考，需按新栈重写。
6. **评估留出集**：按草图划分的 query 集（第 6 节），仓库的 `data_process.py` 是 10:2 切分，需对齐评估协议。

> 缺口 2（B-rep 图）与缺口 1（数据落地）是 8.4K 阶段的关键路径；缺口 5（服务）是交付关键路径。

---

## 3. 系统架构（离线建库 / 在线查询 不对称）

整个系统最核心的设计是**不对称**：查询时只跑草图编码器，CAD 侧（多视图 CNN、B-rep GNN）只在离线建库时跑。这个不对称是后续所有简化（ONNX 导出、Rust 服务、暴力检索）成立的根本原因。

### 3.1 离线建库阶段（Python + PyTorch）

```
STEP 文件 (ABC chunk1, ~8.4K 去重后)
  → [质量探查 probe: 拓扑遍历, 不 mesh] → manifest 标记 render_eligible
  → mesh / 渲染 12 视图 (顶6 + 底6, 224×224)
  → PhotoSketch 风格迁移 → 每视图一张草图
  → [可选] STEP 拓扑 → B-rep UV-grid 图 (face/edge 属性 + UV 网格)
  → 训练 (第 5 节, 消融驱动选主干)
  → CAD 编码器对全库提特征 → 每模型 512-d 向量 (V2 顶/底各一条)
  → 产物打包:
      · embeddings.npy   (L2 归一化后的向量矩阵)
      · sketch_encoder.onnx (查询侧编码器, 第 7 节导出)
      · ids.json / metadata.json / manifest.json
      · thumbnails/      (每模型缩略图)
```

CAD 编码器、B-rep GNN 的输出是"建库时算好的 512-d 向量"，写进 `embeddings.npy` 就完成使命，**永不进入在线服务**。

### 3.2 在线查询阶段（Rust / axum）

```
用户草图图片 (multipart 上传)
  → 预处理 (Rust image crate: 解码 → 灰度 → resize → 归一化 → NCHW f32)
  → ONNX sketch 编码器 (ort crate, CPU 或 CUDA EP) → 512-d, L2 归一化
  → 暴力点积 (embeddings.npy · query) → top-100
  → 按 model_id 去重 (V2 顶/底两条取最优) → top-K
  → 返回 {model_id, score, rank, thumbnail_url}
  → Astro 前端渲染结果网格
```

热路径 = 一次小 CNN 前向 + 一次矩阵乘 + top-K。无重型依赖。

### 3.3 三个独立单元（各自可单独开发、测试、替换）

1. **build（离线）** — Python。职责：数据→训练→提特征→打包产物。可独立重跑（换主干只重跑提特征+打包）。
2. **serve（在线）** — Rust。职责：加载产物 → 起 HTTP → 处理 `/search`。只认产物契约，不关心产物怎么来的。
3. **frontend** — Astro。职责：上传草图、展示结果。只认 `/search` 的 JSON 契约。

三者通过**两个契约**解耦：build↔serve 用第 7.4 节的产物目录契约；serve↔frontend 用 `/search` 的请求/响应 JSON。任一单元可独立替换实现（例如 serve 从 Rust 回退到 FastAPI）而不动另外两个。

### 3.4 数据流中的关键不变量

- **维度一致**：ONNX 编码器输出维度 == `embeddings.npy` 列数 == `manifest.json` 的 `dim`。serve 启动时校验，不匹配则拒绝启动。
- **归一化位置**：向量在**建库时**就 L2 归一化写盘，故 serve 端只做点积（不在运行时归一化库向量）。query 向量在 serve 端归一化一次。
- **度量一致**：建库、训练、检索三处的距离度量必须一致（cosine/IP 或 L2，由 `manifest.metric` 声明，第 6 节）。

---

## 4. 数据管线（保留原管线 + 开源兼容层）

### 4.1 原则

8.4K 阶段**沿用 Gitee 已验证的管线**（含商业/不可复现环节），最贴近现有数据、零返工。同时为每个不可复现环节建一个**开源等价路径**，供扩规模时复现。两条路径产出同构数据（同样的 `views/`、`sketches/`、`graph*.pt` 布局），下游训练无感。

### 4.2 管线步骤与双路径

| 步骤 | 原管线（8.4K 沿用） | 开源兼容层（扩规模） | 产物 |
|---|---|---|---|
| 下载 | 校内网盘已有 | `download.py`（ABC 官方，7z 校验+resume+代理） | `step/**/*.step` |
| 去重1 | `FindDuplicatesByFileSize.ps1`（按文件大小） | 同脚本（PowerShell 可跨平台跑或移植） | `deduplicate1.txt` |
| 去重2 | `FindDuplicatesByJSD.py`（按 JSD 散度） | 沿用 | `deduplicate2.txt` |
| 质量探查 | （新增）download-probe 的拓扑探查 | 同 | manifest `render_eligible` |
| STEP→mesh | Crossmanager（商业）→OBJ；`utils/tools.py` OBJ→OFF | OCC/OCP STEP→STL/mesh（`context/history` 已有） | `off/` 或 mesh |
| 渲染视图 | Sketch3DToolkit（12 视图，顶6底6，224²） | moderngl/pyrender（`utils/render.py` 已有 moderngl 雏形） | `views/<model>/<model>_{0..11}.png` |
| 草图生成 | PhotoSketch（预训练 GAN，纯推理） | 同 PhotoSketch（开源、可复现） | `sketches/<model>/*.png` |
| B-rep 图 | （新增，关键缺口）STEP 拓扑→UV-grid 图 | OCC 拓扑遍历 + UV 采样 | `graph*.pt` |
| 切分 | `data_process.py`（10:2，顶/底各留1张test） | 沿用（但评估协议见第6节对齐） | `train/` `test/` |

### 4.3 视图与草图布局约定（来自 `ABC_V2`）

- 每模型 12 视图：索引 0-5 = 顶半球，6-11 = 底半球。文件名 `<model>_<idx>.png`。
- 草图与视图一一对应（PhotoSketch 对每张视图做风格迁移），同样 0-11 编号、按子目录组织。
- 训练时（`dataset.py` 逻辑）：随机取一张草图，依其编号判定 from_top，取对应的 6 张同半球视图作为正样本视图组；CNN 多视图 max-pool 成一条特征。检索时顶/底各产一条特征，故 `deduplicate_ratio=2`。

### 4.4 B-rep 图提取（最主要的补全项）

GNN / BOTH 分支依赖每模型一张图。`ComplexGNN` 期望的图结构（来自 `baseline.py` 与 `complex_gnn.py`）：

- **节点 = 面**：`node_attr_dim=14`（面类型/参数等属性），`node_grid_dim=7`（面 UV 网格采样，UV-Net 风格 7 通道：3 坐标 + 3 法向 + 1 可见性掩码类）。
- **边 = 面邻接**：`edge_attr_dim=15`，`edge_grid_dim=12`（边曲线 UV 网格）。
- 提取方式：OCC `STEPControl_Reader` 读 → `TopExp_Explorer` 遍历面/边 → 每面/边采 UV 网格 + 拓扑属性 → 存为 `torch_geometric` Data → 聚合成 `graph*.pt`（list of `{name, graph}`）。
- **命名对齐**：`inference.py` 里图名做 `replace('step','trimesh')`，提取器须产出与 `views/`、`sketches/` 子目录名可对齐的 `name` 字段。
- **失败处理**：图提取失败的模型——记入失败清单，**该模型在 BOTH 分支回退为 CNN-only**（其图特征分支置零，仓库 `BOTH` 的 concat 结构天然支持），保证它仍可被检索，绝不从库中丢弃。

### 4.5 质量筛选与失败清单（显式、可复现）

沿用 download-probe 设计的核心教训：**质量筛选必须显式、廉价、可解释、可复现，不能是渲染 timeout 的隐式副产物**。

- 用一张 manifest 表（LanceDB 或等价）记录每模型：`model_id / src_path / probe_* 拓扑指标 / quality_flags / render_eligible / 各阶段 status`。
- 探查（probe）只做拓扑遍历不 mesh：面数过多→`too_complex`、无实体→`no_solid`、退化→`degenerate` 等（致命 flag 集见 download-probe spec 第 5 节）。
- 渲染失败、图提取失败、去重剔除的模型——全部写回 manifest 对应 status，**可查询、可复核、可单独重跑**。
- 阈值是配置不是硬编码：首跑后看 `n_faces`/`file_size` 真实直方图回填，避免重蹈"340K 魔法数"。

### 4.6 数据管线交付物

1. `views/`、`sketches/`、`train/`、`test/`、`graph*.pt`（8.4K 全量）。
2. manifest 表（含质量 flag、各阶段 status、失败清单）。
3. 几何复杂度分布直方图（供阈值回填与扩规模评估）。
4. 开源兼容层脚本（STEP→mesh→渲染→图）+ 一致性说明：开源路径产出与原管线同构。

---

## 5. 模型与训练（消融驱动选主干）

### 5.1 为何不预先押注主干

~8.4K 实例 / ~10 万图像这个量级是整个方法选型的支点。一场结构化辩论（CNN 拥护 / ViT 拥护 / 中立分析三方）的收敛结论：

- **CNN 双分支 + 域对抗**是 SHREC13/14 草图赛道在相近规模上的获奖配方（DCML/DCHML、Chen&Fang ECCV'18），数据高效、已能跑、有部署参考——**默认基线**。
- **B-rep 几何（GNN，BOTH）**结构上最可能赢实例检索：实例检索拼的是精确几何细节，而 B-rep 图在 CAD 模型侧**零草图域差**——**最值得验证的上行项**。
- **CLIP-ViT+LoRA**在这个小规模细粒度 3D 实例集上**没有证据**能稳赢 CNN，且原项目有坍缩前科——**风险臂，须先过坍缩探针门**。

故主干**由实验定**，spec 固化的是"如何决定"，不是"决定了什么"。

### 5.2 消融轴

| 轴 | 取值 | 仓库支持点 |
|---|---|---|
| 草图主干 | SE-ResNet50 / CLIP-ViT+LoRA | `backbone` 参数（新增 CLIP 选项需小幅扩展 `CNN` 类） |
| CAD 分支 | CNN-only / GNN-only / BOTH | `branch ∈ {CNN,GNN,BOTH}`（已支持） |
| 域损失 | 开 / 关 | `loss` 后缀 `WithDomainLoss` + `domain_discriminator`（已支持） |
| 对比损失 | HardTripletMargin / InfoNCE | `utils/loss.py`（已支持） |

完整网格 = 2×3×2×2 = 24 run，**不全跑**。采用部分析因 + 单轴扫描。

### 5.3 阶段化执行（先 de-risk，再展开）

**阶段 A — 坍缩探针（< 1 小时，先于任何训练）**
- 冻结 CLIP-ViT，零训练，embed ~2K 留出草图 + 其真模型的视图，跑 FAISS 看**零样本 Top-100** + 草图 embedding 的**有效秩 / 随机草图对平均余弦**。
- 判据：若 embedding 塌成低秩锥（随机对余弦 ≈0.9+），CLIP 臂降级——优先 SE-ResNet50，CLIP 仅作低优先对比。若零样本 Top-100 非平凡且秩健康，CLIP 臂放行。
- 目的：用 <1h 提前暴露原项目那种 embedding 坍缩，避免在风险臂上烧算力。

**阶段 B — 关键二选一（2 个 run，全用现有代码、最低风险栈）**
- R1: SE-ResNet50 + CNN-only + 域损失关 + triplet（基线锚点）。
- R3: SE-ResNet50 + BOTH(CNN⊕B-rep GNN) + 域损失关 + triplet（几何上行测试）。
- 问题：**精确几何到底帮不帮实例检索**？这是信息量最高、成本最低的问题，2 个 run 即可答。

**阶段 C — 按决策规则展开矩阵**
- 依阶段 B 结果与阶段 A 放行情况，补齐至多 ~9 run 的部分析因矩阵（下表），每轴至少被触碰 2 次。

| # | 草图主干 | CAD 分支 | 域损失 | loss | 目的 |
|---|---|---|---|---|---|
| R1 | SE-ResNet50 | CNN-only | 关 | triplet | 基线锚点 |
| R2 | SE-ResNet50 | GNN-only | 关 | triplet | CAD 分支轴 |
| R3 | SE-ResNet50 | BOTH | 关 | triplet | 几何上行（关键） |
| R4 | CLIP-ViT+LoRA | CNN-only | 关 | triplet | 草图主干轴（须探针放行） |
| R5 | CLIP-ViT+LoRA | BOTH | 关 | triplet | 双优候选 |
| R6 | SE-ResNet50 | BOTH | 开 | triplet | 域损失轴 |
| R7 | SE-ResNet50 | BOTH | 关 | InfoNCE | loss 轴 |
| R8 | CLIP-ViT+LoRA | BOTH | 开 | InfoNCE | 叠加最优 |
| R9 | CLIP-ViT+LoRA | GNN-only | 关 | triplet | ViT 在纯几何 CAD 侧是否仍有用 |

**阶段 D — 定稿**
- 按决策规则（5.5）选出主干，对最优配置换种子复现，作为交付模型。

### 5.4 训练配置基线（沿用仓库，可消融覆盖）

- 骨架预训练：`seresnet50.a1_in1k.bin`（partial pretrain）。
- 输入 224×224，灰度转 3 通道（仓库 transform 已含 `Grayscale(3)`）。
- 草图增强：旋转 15°、颜色抖动、水平翻转（`abc_transform_v2`）；视图用 test transform（不强增强）。
- 优化器/调度：仓库默认 timm `create_optimizer`/`create_scheduler`（AdamW + cosine）或自定义；起点 lr≈1e-3（V2），batch 视显存（5090 32GB 可比仓库默认 32 更大）。
- 损失：HardTripletMarginLoss（V2 默认，含 batch 内最难负样本 + 准确率监控）；InfoNCE 作消融。
- B-rep 图：`ComplexGNN` 在 5090 用 `graph_hidden_dim=512`（仓库注释：4090 用 32，5090 用 512）。
- 存档：仓库 `trainer.py` 已有 checkpoint + 断点续训 + 分离导出（`extract_mode='separate'` 可单独导出 `sketch_model`/`view_model`）。

### 5.5 评估协议与决策规则

- **划分**：实例检索每个模型都必须在 gallery 里，故**按草图划分**而非按模型。gallery = 全部 ~8.4K 模型（其视图+几何入库）；每模型留 1 张草图作 query（~8.4K query），其余训练。（对齐仓库 `data_process.py` 顶/底各留 1 张 test 的思路。）
- **固定协议**：同一 FAISS 索引、同一 query 集、同一随机种子跨所有 run。报告 Top-1/10/20/50/100。
- **主指标 Top-1**（实例检索就是要那一个），Top-10 作平手区分 + 坍缩探测。
- **决策规则**：差异算"真"当且仅当 **ΔTop-1 ≥ 2 绝对点 且换第二个种子仍成立**（~8.4K query 的 bootstrap 95% CI 半宽约 1 点，2 点是可辩护阈值）。低于此**取更简单/更便宜的架构**（偏好 CNN-only 优于 BOTH、SE-ResNet50 优于 CLIP）。报告 bootstrap 95% CI。

### 5.6 算力预算（单卡 5090）

- 探针：< 1h。单 run（triplet/InfoNCE，骨架基本冻结或轻调）≈ 2-4h；BOTH 加 GNN 前向 ≈ +30%。
- STEP→图 预处理：一次性离线 ~数小时（非每 run）。
- 阶段 B（2 run）≈ 半天；完整 ~9 run ≈ 1.5-2 天；top-2 换种子复现 ≈ +半天。

---

## 6. 评估协议与目标指标

### 6.1 评估对象

- **离线检索评估**（主）：在留出草图集上跑全库检索，算 Top-K。这是选主干、定阈值的依据。
- **真实草图小评估**（辅）：手绘 30-50 张真实草图、标注对应模型，验证 PhotoSketch 合成草图与真实手绘的效果差距——这是"训练分布 vs 部署分布"差异的早期信号。

### 6.2 划分与协议（与第 5.5 节一致，此处固化为评估规范）

- gallery = 全部 ~8.4K 模型；query = 每模型留出的 1 张草图（按顶/底各留思路，~8.4K query）。
- 索引：先 FAISS flat（与仓库一致，离线评估用），度量由主干决定——triplet 主干用 L2，InfoNCE/cosine 主干用 IP。`manifest.metric` 声明，建库/训练/检索三处一致。
- 去重：检索 top-(ratio×k) 后按 model_id 去重取最优，V2 `ratio=2`。
- 指标：Top-1/10/20/50/100 + bootstrap 95% CI（over query 集）。

### 6.3 目标指标

阈值**不预设魔法数**，由消融基线 + 决策规则确定。给出方向性目标供评审锚定：

| 指标 | 方向性目标（合成草图留出集） | 备注 |
|---|---|---|
| Top-1 | 经评审认可的水平（基线锚点见阶段 B 实测） | 实例检索主指标 |
| Top-10 | 显著高于 Top-1，作平手区分与坍缩探测 | 坍缩时 Top-10 也会塌 |
| 真实手绘 Top-10 | 报告与合成草图的差距，作部署可用性参考 | 若差距大 → 先扩数据再换主干 |
| p95 延迟 | 交互级（< 数百 ms） | 主要成本一次 CNN 前向 + 一次检索 |

最终交付阈值 = 阶段 B 实测基线 + 决策规则选出的最优配置实测值，写入交付报告。

### 6.4 坍缩与退化检测（贯穿训练）

- 训练中监控 batch 内检索准确率（仓库 `HardTripletMarginLoss`/`InfoNCE` 已返回 accuracy）。
- 周期性 embed 留出集，看有效秩 / 随机对平均余弦，及早发现坍缩（原项目教训）。
- Loss NaN 即抛异常停训（仓库已有）。

---

## 7. 部署与服务（Python→ONNX→Rust→Astro，FastAPI 回退）

由 GPT-5.5 + Claude 双人小组评审定案（两方均 ~0.8 置信，强收敛）。核心仍是第 3 节的不对称：热路径只有一个小模型。

### 7.1 推理路径（PyTorch → ONNX）

- **SE-ResNet50 草图编码器**：干净导出。纯 conv/BN/ReLU/SE(全局池+2FC+sigmoid+乘)/池化/linear，opset 17+，仅 batch 维动态轴，H/W 固定 224。
- **CLIP-ViT+LoRA**（若选为主干）：**先 `merge_and_unload()` 把 LoRA 并入基座**再导出（绝不把 adapter 当独立分支导）；固定方形输入、关闭异型 attention kernel；导出后做 **PyTorch↔ONNX 数值对齐测试**（mean cosine > 0.999 且 top-K 一致）才放行。
- **B-rep GNN 确认离线-only**：PyG message-passing 依赖 `scatter_reduce`，是已知的 ONNX 雷区（`include_self=False` 不支持、`max` reduce 静默错值）。GNN 只在建库产出向量，**永不进 ONNX/Rust**。这是整个部署能简化的根本。
- **烘进图的内容**：首版啥也不烘；归一化(mean/std)可后期作为 2-op 前缀折叠，非首要。

### 7.2 向量检索

- **首版暴力点积**：`embeddings[N×512] · query[512]` + top-K。建库时已 L2 归一化，serve 端只做点积。
- 规模阈值：512 维下，CPU 上暴力到 ~1-2M 向量仍可接受，GPU 上几乎永远够。**超过 ~1-2M 且 CPU 受限**再上 ANN。
- ANN 选型：**usearch**（Rust 原生、cosine/IP、部署简单）。不在 Rust 里碰 FAISS（绑定弱）；hnswlib 仅因有 C++ 参考可考虑，但不作 Rust 首选依赖。
- V2 顶/底两条向量的去重在 top-100 之上做，与是否 ANN 无关。

### 7.3 服务形态（Rust / axum）

- 启动时加载：ONNX 草图编码器（`ort` crate，CUDA EP 优先、CPU EP 回退）+ `embeddings.npy`（mmap）+ `ids.json` + `metadata.json`。
- 端点：
  - `GET /healthz`
  - `POST /search`：multipart 图片（+可选 `k`）→ `{query_id, results:[{model_id, score, rank, thumbnail_url, metadata}]}`。
  - 缩略图：静态目录服务或 `GET /models/:id/thumbnail`。
- **预处理放 Rust 端**（`image` crate：解码→灰度→resize→归一化→NCHW f32），不烘进图（首版易调试）。预处理参数（input_size/channels/mean/std/resize_mode）写进 `manifest.json` 冻结契约，serve 严格照此执行。
- 启动校验：ONNX 输出维度 == `embeddings` 列数 == `manifest.dim`；行数 == `ids` 长度；每条向量都能映射到模型；不匹配拒绝启动。

### 7.4 产物交接契约（build → serve）

Python build 产出单个版本化目录，Rust serve 只认这个契约：

```
artifact/
  manifest.json        # {schema_version, dim:512, metric:"ip"|"l2", count, encoder, normalized:true,
                       #  preprocess:{input_size,[h,w], channels, mean, std, resize_mode}}
  embeddings.npy        # float32 [N, 512], 行主序, 建库时 L2 归一化
  ids.json              # [N] row → model_id (并行数组, 下标即行号; V2 含 slot: top/bottom)
  metadata.json         # model_id → {name, step_path, thumbnail_path, view_count, source}
  sketch_encoder.onnx   # 查询侧编码器
  thumbnails/           # 每模型缩略图
```

契约规则：
- **embeddings 建库时归一化**（serve 端不再归一化库向量）。
- `manifest.json` 是**版本门**：`schema_version`/`dim`/`metric` 不匹配则 serve 拒绝启动。
- 数值热数组（`embeddings`）与映射（`ids`/`metadata`）分离，保持热数组缓存友好。
- 该契约完全解耦：Python 端换 CNN/GNN/BOTH 主干，只要产出同样的 `.npy` + `.onnx`，serve 无感。

### 7.5 前端（Astro）

- 复用现有 `web/` Astro demo（已有 three.js 模型查看器、检索结果网格、草图/图片上传栏）。
- 改动：上传草图 → `fetch` multipart 到 Rust `/search` → 渲染返回的 top-K 缩略图 + 分数；点击查看 3D。
- 与 serve 通过 `/search` JSON 契约解耦，serve 换实现前端无感。

### 7.6 诚实回退判定

- **Rust 是否值得**：热路径只有一个小模型，Rust 相对 FastAPI+onnxruntime-gpu 的延迟优势有限（GPU 干活，Python 开销约 1ms/请求）。Rust 的实益是单静态二进制、无 GIL/无 Python 环境漂移、低空闲内存——叠加用户的 Rust 取向与现有 C++ 参考，**可辩护但非延迟必需**。
- **回退触发**：若 `ort` + CUDA EP 在 5090（Blackwell/CUDA 12.x）上链接/打包不顺，**退回 FastAPI + onnxruntime-gpu**，保持 `/search` HTTP API 完全一致 → Astro 无感、零能力损失。这是务实逃生舱。

### 7.7 安全（网络暴露前必做）

- 上传图片：限 body 大小（如 5-10MB）、限解码后分辨率（防图片炸弹）、限 MIME、请求超时。
- 暴露前加鉴权（至少共享 token）+ 限流（按 IP/用户）。
- 缩略图/CAD 文件不允许任意路径访问。
- 不在公网开放无鉴权端点。

> 安全提示：本服务接受任意上传图片，必须在守护路径中解码并限流，暴露前置于鉴权之后。

---

## 8. 全流程里程碑与交付清单

### 8.1 里程碑（M0 → M6）

| 里程碑 | 内容 | 完成判据 | 关键路径 |
|---|---|---|---|
| **M0 环境对齐** | 5090/CUDA12.8 装齐 torch2.8 + PyG + faiss + timm 等；仓库能在 debug 模式跑通一个 mini-batch | `train.py --debug` 跑通、`test.py` 跑通 | 是（PyG↔torch2.8 兼容是已知风险点） |
| **M1 数据落地** | 取/重建 `views/sketches/train/test`（8.4K）；建 manifest + 质量探查 | 8.4K 视图+草图齐、manifest 有质量 flag、复杂度直方图产出 | 是 |
| **M2 B-rep 图补全** | 写 STEP→UV-grid 图提取器；产 `graph*.pt`；失败清单 | GNN 分支能加载图并前向；失败模型记录且回退 CNN-only | 是（GNN/BOTH 依赖） |
| **M3 消融决策** | 阶段 A 探针 → B(R1/R3) → C(矩阵) → D(定稿) | 按决策规则选出主干 + 换种子复现；消融报告产出 | 是（定主干） |
| **M4 建库与产物** | 用选定主干对全库提特征；打包 artifact 目录（第7.4契约） | `artifact/` 齐全且通过 serve 启动校验 | 是 |
| **M5 服务上线** | 导出 ONNX；Rust/axum 服务 `/search`；（或回退 FastAPI） | 端到端 `/search` 返回正确 top-K；p95 交互级 | 是（交付） |
| **M6 前端联调** | Astro 接 `/search`；上传草图→看结果→查 3D | demo 可演示完整查询流程 | 是 |

> 关键路径串联：M0→M1→M2→M3→M4→M5→M6。M2 可与 M3 阶段 A/B 并行启动（阶段 B 的 R3 需要图，故 M2 须在 R3 前完成）。

### 8.2 交付清单

1. **可复现全流程**：从现有数据到起服务的脚本/命令序列（含开源兼容层）。
2. **训练好的主干模型** + 消融报告（含决策规则的实测依据、最终阈值）。
3. **artifact 产物**（embeddings/onnx/manifest/metadata/thumbnails）。
4. **Rust/axum 服务**（或 FastAPI 回退），含 `/search` API 文档。
5. **Astro 前端 demo**（接真实服务）。
6. **数据 manifest + 质量直方图 + 失败清单**。
7. **本 spec + 实现 plan + 复现 README**。

### 8.3 与历史演示物的关系

仓库已有 `presentations/cad-retriever/`（5-slide Astro 演示）与 `web/`（demo 前端）。本项目交付的真实服务上线后，演示物可指向真实 `/search`，把"概念演示"升级为"实物演示"，无需重写。

---

## 9. 风险与回退路径

| 风险 | 触发信号 | 回退/缓解 |
|---|---|---|
| PyG 与 torch 2.8 不兼容（M0） | `torch_geometric` import/编译失败 | 锁定经验证的 PyG+torch 组合；或先只跑 CNN 分支（不依赖 PyG），GNN 推迟 |
| B-rep 图提取失败率高（M2） | 大量 STEP 图提取报错 | 失败模型回退 CNN-only（图特征置零）；不阻塞全流程；记失败清单 |
| CLIP 草图编码器坍缩（M3-A） | 探针：embedding 低秩 / 随机对余弦≈0.9+ | CLIP 臂降级，主干走 SE-ResNet50；不在风险臂烧算力 |
| 几何无显著增益（M3-B） | R3 对 R1 ΔTop-1 < 2 点 | 取更简单的 CNN-only，省掉 STEP→图 管线与失败处理 |
| 合成草图≠真实手绘（M3/M6） | 真实手绘 Top-10 远低于合成 | 先扩 ABC chunk 增样本，而非换主干；或在 query 端用同款 PhotoSketch 预处理 |
| ONNX↔PyTorch 数值漂移（M5，尤其 ViT-LoRA） | 对齐测试 cosine < 0.999 / top-K 不一致 | build 管线内置对齐门；CNN 主干风险低 |
| `ort`+CUDA-EP 在 5090 打包不顺（M5） | Rust 侧 ORT CUDA 链接/运行失败 | **退回 FastAPI + onnxruntime-gpu**，`/search` API 不变，前端无感 |
| 检索延迟超预算（M5） | p95 超交互级 | 暴力→usearch ANN；或 GPU 检索 |
| 数据盘/显存不足 | OOM / 磁盘满 | 数据写大盘（第11节）；batch 调小；GNN hidden dim 降档 |

**回退总原则**：每一级回退都向"更简单、更已验证"的方向走，且通过契约（产物契约 / `/search` API）隔离，使回退不波及其他单元。

---

## 10. 技术栈与环境约束

### 10.1 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 训练 | Python 3.12 + PyTorch 2.8（+CUDA 12.8） | 仓库原生；5090 支持 |
| CAD 编码/图 | torch_geometric（ComplexGNN）；OCC/OCP（STEP 解析、图提取） | 仓库依赖；OCC 开源可复现 |
| 骨架 | timm SE-ResNet50（`seresnet50.a1_in1k`）；可选 OpenCLIP ViT-B/16 | 仓库默认 + 消融对比臂 |
| 检索（离线评估） | FAISS flat | 仓库一致 |
| 推理导出 | ONNX（opset 17+） | 跨语言、Rust 可载 |
| 在线推理 | ONNX Runtime（`ort` crate；回退 onnxruntime-gpu） | Rust 原生 / Python 回退 |
| 在线检索 | 暴力点积（首版）→ usearch（超规模） | 简单优先；Rust 原生 ANN |
| 服务 | Rust + axum（回退 FastAPI） | 单二进制 / 用户取向；FastAPI 为务实逃生舱 |
| 前端 | Astro + three.js（复用 `web/`） | 已有 demo |
| 数据管线 | Crossmanager/Sketch3DToolkit/PhotoSketch（沿用）+ OCC/moderngl/pyrender（开源层） | 现有沿用 + 扩规模可复现 |
| manifest | LanceDB（或等价瘦表） | download-probe 一致 |

### 10.2 环境约束

- GPU：单卡 RTX 5090（32GB，Blackwell，CUDA 12.8）。
- 数据落盘：写 GPU 机大数据盘（沿用历史 `~/data` 2TB 约定），**禁止**写代码仓库目录或 `/tmp`。
- 外网（如需下载/扩规模）：走代理（历史环境 `http://127.0.0.1:7890` mihomo）。
- 预训练权重：`seresnet50.a1_in1k.bin` 放 `model/Baseline/path_state_dict/`；PhotoSketch 权重在 `tool/PhotoSketch.zip` 内。
- 关键依赖验证点：PyG↔torch2.8、faiss-gpu、ort↔CUDA12.8（5090）——这三处是 M0/M5 的已知风险，须早验证。

### 10.3 跨平台说明

- 训练在 GPU 机（Linux 约定路径）；当前开发机为 Windows（仓库、spec、前端）。
- 去重脚本含 PowerShell（`FindDuplicatesByFileSize.ps1`），跨平台时需移植或在 Windows 侧跑。
- 路径分隔、shell 语法按目标机调整；spec 不绑定单一 OS。

---

## 11. 单元边界小结（便于后续拆 plan）

| 单元 | 职责 | 输入 | 输出 | 依赖 |
|---|---|---|---|---|
| download/ingest | 取 STEP、登记 manifest | ABC chunk / 网盘 | `step/`、manifest 行 | 代理、py7zr |
| probe | 拓扑探查、质量 flag | manifest pending 行 | probe 列、render_eligible | OCC |
| render | STEP/mesh→12 视图 | render_eligible STEP | `views/` | Sketch3DToolkit / moderngl |
| sketch | 视图→草图 | `views/` | `sketches/` | PhotoSketch |
| graph | STEP→UV-grid 图 | render_eligible STEP | `graph*.pt`、失败清单 | OCC + torch_geometric |
| train | 消融训练、选主干 | views/sketches/graph | 主干 checkpoint、消融报告 | 仓库 trainer |
| build-artifact | 提特征、打包 | 主干 + 全库 | `artifact/`（第7.4契约） | 仓库 inference + ONNX 导出 |
| serve | 在线检索 | `artifact/` + 上传草图 | `/search` JSON | ort/onnxruntime |
| frontend | 上传与展示 | `/search` | 浏览器 UI | Astro |

每个单元可单测、可单独重跑、通过契约与上下游解耦。这张表是第二步 writing-plans 拆任务的直接依据。
