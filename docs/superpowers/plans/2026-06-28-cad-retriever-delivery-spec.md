# CAD Retriever 交付 Spec 编写实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份 >5000 行、独立自洽、可被 writing-plans 直接拆解的 CAD 草图检索系统**交付 spec**（单一事实来源），含完整开发流程与专设的 Timeline 章节。

**Architecture:** 本计划的"代码产物"是一份 Markdown 文档 `docs/superpowers/specs/2026-06-28-cad-retriever-delivery-spec.md`。按 13 个 Part 增量编写：先建文件骨架（含 Part 标题占位 + 行数自检脚本），再每个 Part 作为一个任务**追加**正文，每任务结束跑一道"结构门 + 约束门"校验并提交。Part 9（9 个执行单元 × 全维度）是行数主引擎。

**Tech Stack:** Markdown；校验用 PowerShell / Bash 文本工具（行数统计、禁用词扫描、Part 标题完整性检查）；git 提交。

## Global Constraints

下列约束**逐字**适用于每个任务，是整份 spec 的全局红线：

- **独立文档**：spec 必须写成第一份、唯一一份关于本系统的文档。**禁止**出现回指既往工作的措辞——禁用词（中文）："转向"、"原方案"、"原计划"、"老方案"、"旧方案"、"老的设计"、"上次"、"上一次"、"此前失败"、"复盘"、"降级为"、"降为"、"改动"、"我们改了"、"与设计 spec 差异"、"相比之前"、"原来的"。理由一律**前向陈述**（"本方案采用 X 因为 Y"），不写成"因为之前 X 失败所以改成 Y"。
- **不含"与上游设计的关系"章节**，**不含"与设计 spec 差异表"附录**。
- **不预设魔法数阈值**："魔法数" = 无来源、硬编码的常量/阈值。所有阈值要么标注"回填依据"（看哪张分布图/哪个指标定），要么写成"数据驱动留白 + 相对止损线"。唯一允许的数值是有明确出处的（如 V2 `num_classes=8422`、`deduplicate_ratio=2`、bootstrap CI 半宽 ≈1 点 → ΔTop-1≥2 点决策规则）。
- **硬件 = 3× RTX 5090**（32GB each, Blackwell, CUDA 12.8）。算力预算、训练编排、Timeline 三处按 3 卡写；服务仍只用 1 卡。
- **不贴实现代码**：spec 是 plan 级蓝图，描述"做什么/输入输出/依赖谁/失败如何处理/接口契约/目录结构/命令意图"，不含具体函数实现代码。允许：目录树、JSON/接口 schema、表格、checkbox 任务、命令意图（非可复制脚本）。
- **语言 = 中文**（技术名词/路径/标识符保留英文原文）。
- **文件目标 >5000 行**，靠真内容达成（Part 9 为主引擎），非灌水。
- **路径约定**：训练/数据落盘在 GPU 机大数据盘（沿用 `~/data`）；代码仓库目录不写大数据。
- 单一事实来源：所有阶段、产物、阈值、决策规则以此 spec 为准。

---

## 编写约定（适用于所有任务）

- **目标文件**：`docs/superpowers/specs/2026-06-28-cad-retriever-delivery-spec.md`（下称"目标 spec"）。
- **增量方式**：每个 Part 任务用 append 追加正文到目标 spec 末尾，不重写已写部分。
- **每任务收尾三件事**：① 跑结构门（Part 标题存在且唯一）② 跑约束门（禁用词扫描 = 0 命中、魔法数自查）③ git 提交该 Part。
- **行数目标分配**（指导值，非硬约束；总和 >5000）：

  | Part | 章节 | 目标行数 |
  |---|---|---|
  | 骨架 | 文件头 + 目录 + 13 Part 占位 | ~120 |
  | 0 | 文档导言 | ~150 |
  | 1 | 背景与目标 | ~250 |
  | 2 | 现状盘点 | ~300 |
  | 3 | 系统架构 | ~350 |
  | 4 | 数据管线 | ~450 |
  | 5 | 模型与训练 | ~550 |
  | 6 | 评估协议 | ~350 |
  | 7 | 部署与服务 | ~500 |
  | 8 | 开发流程与时间线（Timeline 专章） | ~700 |
  | 9 | 单元执行规格（9 单元 × 全维度） | ~1500 |
  | 10 | 风险登记册 | ~300 |
  | 11 | 技术栈与环境 | ~250 |
  | 12 | 交付清单与验收 | ~250 |
  | 13 | 附录 | ~400 |
  | | **合计** | **~6420** |

- **禁用词扫描命令意图**（Bash，每任务收尾跑；命中应为 0）：
  ```
  grep -nE '转向|原方案|原计划|老方案|旧方案|老的设计|上次|上一次|此前失败|复盘|降级为|降为|我们改了|与设计 spec 差异|相比之前|原来的' <目标spec>
  ```
- **行数自检命令意图**：`wc -l <目标spec>`（Bash）或 `(Get-Content <目标spec>).Count`（PowerShell）。

---

### Task 0: 建文件骨架与校验基线

**Files:**
- Create: `docs/superpowers/specs/2026-06-28-cad-retriever-delivery-spec.md`

**Interfaces:**
- Consumes: 无（首个任务）。
- Produces: 目标 spec 文件 + 文档头（标题/日期/范围/粒度行）+ 完整目录（13 Part 链接）+ 13 个 Part 二级标题占位（每个仅标题 + 一行 `（本节待填）`）。后续每个 Part 任务依赖这些标题已存在，只替换占位段、append 正文。

- [ ] **Step 1: 写文件头与目录**

目标 spec 顶部写入（中文）：
- H1 标题：`# CAD 草图检索系统 — 交付规格说明书（Delivery Spec）`
- 引用块：`日期 2026-06-28` / `状态：待评审` / `范围：现有资产 → 数据 → 训练 → 评估 → 部署 → 交付 全流程` / `粒度：plan 级技术蓝图，不贴实现代码` / `主干策略：消融驱动` / `硬件：3× RTX 5090`
- `## 目录`：13 条带锚点链接，对应 Part 0–13。

- [ ] **Step 2: 写 13 个 Part 占位标题**

依次写入 `## 0. 文档导言` … `## 13. 附录`，每个标题下放一行 `> （本节由对应任务填充）`。占位顺序与目录一致。

- [ ] **Step 3: 结构门校验**

Run（Bash）：`grep -nE '^## [0-9]+\. ' docs/superpowers/specs/2026-06-28-cad-retriever-delivery-spec.md | wc -l`
Expected: `14`（Part 0–13 共 14 个二级标题）。

- [ ] **Step 4: 禁用词门校验**

Run（Bash）：`grep -nE '转向|原方案|原计划|老方案|旧方案|老的设计|上次|上一次|此前失败|复盘|降级为|降为|我们改了|与设计 spec 差异|相比之前|原来的' docs/superpowers/specs/2026-06-28-cad-retriever-delivery-spec.md || echo CLEAN`
Expected: `CLEAN`（0 命中）。

- [ ] **Step 5: 提交**

```
git add docs/superpowers/specs/2026-06-28-cad-retriever-delivery-spec.md
git commit -m "docs(spec): scaffold delivery spec skeleton + 13 part placeholders"
```

---

### Task 1: Part 0 — 文档导言

**Files:**
- Modify: 目标 spec（替换 `## 0.` 占位段，append 正文）

**Interfaces:**
- Consumes: Task 0 的标题占位。
- Produces: Part 0 正文，定义全文阅读契约（读者、约定、魔法数禁令、如何执行本 spec），后续所有 Part 默认遵守。

- [ ] **Step 1: 写 0.1 文档目的与读者**

内容要点：本文是 CAD 草图检索系统的**交付规格说明书**，面向将据此拆解实现 plan 并执行的工程读者。读者**无需任何外部背景**——本系统的方法、数据、技术栈在本文内完整定义。一句话定位："本文是单一事实来源，所有阶段/产物/阈值/决策规则以此为准。"

- [ ] **Step 2: 写 0.2 文档约定**

列出：① 不贴实现代码，只描述做什么/输入输出/依赖/失败处理/接口契约；② 路径约定（数据落盘 `~/data` 大盘，仓库目录不写大数据）；③ 出现"待回填"阈值均标注回填依据，是显式定值流程非 TODO；④ 命令以"命令意图"给出（说明做什么，非可直接复制的脚本）。

- [ ] **Step 3: 写 0.3 魔法数禁令与阈值约定**

定义"魔法数 = 无来源、硬编码的常量/阈值"。规定全文阈值三选一：(a) 标注回填依据；(b) 数据驱动留白 + 相对止损线；(c) 有明确出处的固定值（如 `num_classes=8422`）。明确：检索准确率目标**不写死数字**，由消融基线 + 决策规则确定。

- [ ] **Step 4: 写 0.4 如何执行本 spec**

说明执行链：本 spec → writing-plans 按 Part 9 单元边界拆任务 → 逐任务 TDD 执行。指明 Part 9 是拆 plan 的直接依据，Part 8 是排程依据。

- [ ] **Step 5: 结构门 + 禁用词门**

Run（Bash）：`grep -nE '^## [0-9]+\. ' <目标spec> | wc -l` → Expected `14`（标题数不变）。
Run 禁用词扫描 → Expected `CLEAN`。

- [ ] **Step 6: 提交**

```
git add <目标spec>
git commit -m "docs(spec): Part 0 文档导言"
```

---

### Task 2: Part 1 — 背景与目标

**Files:**
- Modify: 目标 spec（替换 `## 1.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 0 约定。
- Produces: 任务定义、目标/非目标、成功标准、术语符号表——后续 Part 5/6 的指标定义与 Part 9 的验收均引用此处术语。

- [ ] **Step 1: 写 1.1 任务定义**

草图 → CAD 零件**实例检索**：用户提交一张 2D 草图（手绘或 PhotoSketch 风格），系统返回 Top-K 最匹配的具体 CAD 模型。**每个 CAD 模型自成一类**，目标是召回那一个正确模型而非其类别。主指标 Top-1/10/20/50/100。**前向陈述**，不提任何既往方案。

- [ ] **Step 2: 写 1.2 为何采用双分支 + 消融驱动（前向理由）**

正面论证为何选这套方法：① 实例检索拼精确几何，双分支（草图 CNN + 多视图 CNN，可选 B-rep GNN）天然贴合；② PhotoSketch 产风格真实草图，避免合成草图分布差；③ ~8.4K 实例量级下主干优劣无定论，故**消融驱动**经验决定。**严禁**写成"因为旧方案失败"。

- [ ] **Step 3: 写 1.3 目标与非目标**

做：补齐 ~8.4K 数据集缺口、跑通"数据→训练→评估→部署"全流程并交付；消融确定主干；交付在线服务 + Astro 前端；数据管线可扩展可复现。
不做（本期）：文本检索、CAD 生成/编辑/参数化重建、装配体级检索、分布式/K8s/多租户。

- [ ] **Step 4: 写 1.4 交付级成功标准**

全流程一键复现；选定主干留出草图集 Top-1/Top-10 达评审认可水平（阈值见 Part 6，由基线+规则定）；`POST /search` 端到端可用、单卡 5090 p95 交互级；交付物齐全（Part 12）。

- [ ] **Step 5: 写 1.5 术语与符号表**

表格定义：实例检索、gallery、query、视图（顶6/底6）、草图、B-rep 图、消融轴、坍缩探针、产物契约、止损线、关键路径等术语。后续全文引用。

- [ ] **Step 6: 结构门 + 禁用词门**

Run 结构门 → `14`；Run 禁用词扫描 → `CLEAN`（本 Part 风险最高，重点核查 1.2）。

- [ ] **Step 7: 提交**

```
git add <目标spec>
git commit -m "docs(spec): Part 1 背景与目标"
```

---

### Task 3: Part 2 — 现状盘点（资产与缺口）

**Files:**
- Modify: 目标 spec（替换 `## 2.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 0/1。
- Produces: 代码资产逐模块表、数据资产、可复用资产、缺口清单、资产×缺口矩阵——Part 4/5/7/9 据此知道"从什么起步、要补什么"。

- [ ] **Step 1: 写 2.1 代码资产（逐模块表）**

表格列出 Gitee `model-retrieval` 各模块职责：训练入口 `train.py`/`trainer.py`、测试检索 `test.py`/`inference.py`、模型 `model/Baseline/networks/baseline.py`（双分支 `Baseline`，`baseline_step1..5` 渐进消融）、共享 CNN 骨架（SE-ResNet50，多视图 max-pool）、B-rep 图编码器 `complex_gnn.py`+`encoders/`（UV-Net 风格）、可选模块（cross_attention / channel_grouping / feature_fusion / domain_discriminator 梯度反转）、损失 `utils/loss.py`、数据集 `data/retrieval/ABC/V2/dataset.py`、配置 `utils/config.py`、C++ 部署参考。**前向陈述为"现有资产"，不写"老代码"。**

- [ ] **Step 2: 写 2.2 关键事实（来自 config.py）**

`ABC_V2` = ABC 第一个 STEP chunk 经两轮去重后 ~8,422 模型；每模型 12 视图（顶6+底6，224²）；检索时顶/底各产一条特征，`deduplicate_ratio=2`；`num_classes=8422`，`n_views=6`，`collate_fn=abc_collate_fn_v2`。这些是**有出处的固定值**，非魔法数。

- [ ] **Step 3: 写 2.3 数据资产**

`data/.../V2/input/` 有少量样例查询草图（demo/冒烟用）；训练数据（`views/sketches/train/test/graph*.pt`）需从网盘获取或本地重建；`seresnet50.a1_in1k.bin` 预训练权重放 `model/Baseline/path_state_dict/`；PhotoSketch 权重在 `tool/PhotoSketch.zip`。

- [ ] **Step 4: 写 2.4 可复用资产**

OCC/OCP 的 STEP→mesh/渲染/边缘检测代码（开源兼容层基础）；ABC 下载器（7z 校验+5x 重试+resume+代理）；download-probe 设计（LanceDB manifest + 拓扑探查质量筛选）；`web/` Astro 站点 + three.js 查看器（前端复用对象）。

- [ ] **Step 5: 写 2.5 缺口清单（按优先级）**

1 数据落地（取/重建 views/sketches/train/test）；2 B-rep 图数据（`graph*.pt`，8.4K 阶段最主要补全项，需写 STEP→图提取器，失败回退 CNN-only）；3 环境对齐（timm/PyG/faiss 等在 5090/CUDA12.8）；4 质量/失败清单（manifest 显式记录）；5 导出与服务（ONNX + Rust/axum，仓库只有 C++ 参考）；6 评估留出集（按草图划分）。

- [ ] **Step 6: 写 2.6 资产×缺口矩阵**

表格交叉：每个缺口 → 可复用哪些资产 → 还需新建什么 → 关键路径标记。明确缺口 1/2 是 8.4K 阶段关键路径，缺口 5 是交付关键路径。

- [ ] **Step 7: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 2 现状盘点"
```

---

### Task 4: Part 3 — 系统架构（离线建库 / 在线查询 不对称）

**Files:**
- Modify: 目标 spec（替换 `## 3.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 2 资产/缺口。
- Produces: 不对称原则、离线/在线数据流图、三单元两契约、关键不变量、ADR 汇总——Part 7（部署）与 Part 9（单元）的结构依据。

- [ ] **Step 1: 写 3.1 核心设计：不对称**

阐明：查询时只跑草图编码器；CAD 侧（多视图 CNN、B-rep GNN）只在离线建库时跑。这个不对称是 ONNX 导出、Rust 服务、暴力检索三项简化成立的根本原因。

- [ ] **Step 2: 写 3.2 离线建库数据流（ASCII 图）**

STEP（~8.4K 去重后）→ 质量探查 probe（拓扑遍历不 mesh）→ mesh/渲染 12 视图 → PhotoSketch 草图 →[可选] STEP→B-rep UV-grid 图 → 训练（消融选主干）→ CAD 编码器全库提特征（512-d，V2 顶/底各一条）→ 打包产物（embeddings.npy / sketch_encoder.onnx / ids / metadata / manifest / thumbnails）。强调 GNN 输出"建库时算好的向量"永不进在线服务。

- [ ] **Step 3: 写 3.3 在线查询数据流（ASCII 图）**

草图上传（multipart）→ Rust 预处理（解码→灰度→resize→归一化→NCHW f32）→ ONNX 草图编码器（512-d，L2 归一化）→ 暴力点积 top-100 → 按 model_id 去重（顶/底取最优）→ top-K → 返回 {model_id, score, rank, thumbnail_url}。热路径 = 一次小 CNN 前向 + 一次矩阵乘 + top-K。

- [ ] **Step 4: 写 3.4 三单元两契约**

三单元：build（Python，离线，数据→训练→提特征→打包）/ serve（Rust，在线，加载产物→`/search`）/ frontend（Astro，上传与展示）。两契约：build↔serve 用产物目录契约（Part 7.4）；serve↔frontend 用 `/search` JSON。任一单元可独立替换（如 serve 从 Rust 回退 FastAPI）而不动其余。

- [ ] **Step 5: 写 3.5 关键不变量**

维度一致（ONNX 输出维 == embeddings 列数 == manifest.dim，serve 启动校验）；归一化位置（建库时 L2 归一化写盘，serve 只对 query 归一化一次）；度量一致（建库/训练/检索三处距离度量必须一致，`manifest.metric` 声明）。

- [ ] **Step 6: 写 3.6 架构决策记录（ADR 汇总）**

表格形式列关键决策：不对称架构 / 暴力检索优先 / Rust 服务 + FastAPI 逃生舱 / 消融驱动选主干 / GNN 离线-only。每条：决策 / 前向理由 / 影响单元。**理由前向陈述。**

- [ ] **Step 7: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 3 系统架构"
```

---

### Task 5: Part 4 — 数据管线（原管线 + 开源兼容层）

**Files:**
- Modify: 目标 spec（替换 `## 4.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 2 资产、Part 3 离线数据流。
- Produces: 双路径管线表、视图/草图布局约定、B-rep 图结构规格、质量筛选与失败清单机制、数据管线交付物——Part 9 的 download/probe/render/sketch/graph 五单元直接据此展开任务。

- [ ] **Step 1: 写 4.1 原则**

8.4K 阶段沿用已验证管线（含商业/不可复现环节），最贴近现有数据、零返工；同时为每个不可复现环节建**开源等价路径**供扩规模复现。两路径产出同构数据（同样的 `views/`/`sketches/`/`graph*.pt` 布局），下游训练无感。

- [ ] **Step 2: 写 4.2 管线步骤与双路径（表）**

表格列每步：下载 / 去重1（按文件大小）/ 去重2（按 JSD）/ 质量探查 / STEP→mesh / 渲染视图 / 草图生成 / B-rep 图 / 切分。每步两列：原管线（8.4K 沿用，Crossmanager/Sketch3DToolkit/PhotoSketch）vs 开源兼容层（OCC/OCP、moderngl/pyrender、PhotoSketch），第三列产物路径。

- [ ] **Step 3: 写 4.3 视图与草图布局约定**

每模型 12 视图：索引 0-5 顶半球、6-11 底半球，文件名 `<model>_<idx>.png`；草图与视图一一对应同样 0-11 编号；训练时随机取一张草图依编号判 from_top，取同半球 6 视图作正样本组，CNN 多视图 max-pool 成一条特征；检索时顶/底各产一条 → `deduplicate_ratio=2`。

- [ ] **Step 4: 写 4.4 B-rep 图提取规格（最主要补全项）**

`ComplexGNN` 期望的图结构：节点=面（`node_attr_dim=14` 属性 + `node_grid_dim=7` UV 网格 7 通道）；边=面邻接（`edge_attr_dim=15` + `edge_grid_dim=12` 边曲线 UV 网格）。提取方式：OCC `STEPControl_Reader` 读 → `TopExp_Explorer` 遍历面/边 → 采 UV 网格 + 拓扑属性 → `torch_geometric` Data → 聚合 `graph*.pt`（list of `{name, graph}`）。命名对齐：`inference.py` 做 `replace('step','trimesh')`，提取器须产出可对齐 `name`。失败处理：图提取失败的模型记入失败清单，在 BOTH 分支回退 CNN-only（图特征置零，concat 结构天然支持），绝不丢弃。这些维度是有出处的固定值。

- [ ] **Step 5: 写 4.5 质量筛选与失败清单（显式可复现）**

核心原则：质量筛选必须显式、廉价、可解释、可复现，不能是渲染 timeout 的隐式副产物。一张 manifest 表记录每模型 `model_id / src_path / probe_* 拓扑指标 / quality_flags / render_eligible / 各阶段 status`。probe 只做拓扑遍历不 mesh（面数过多 too_complex、无实体 no_solid、退化 degenerate）。渲染/图提取/去重剔除全写回 manifest，可查询可复核可单独重跑。**阈值是配置不是硬编码**：首跑后看 `n_faces`/`file_size` 真实直方图回填。

- [ ] **Step 6: 写 4.6 数据管线交付物**

清单：① views/sketches/train/test/graph*.pt（8.4K 全量）；② manifest 表（质量 flag + 各阶段 status + 失败清单）；③ 几何复杂度分布直方图（供阈值回填与扩规模评估）；④ 开源兼容层脚本 + 一致性说明（开源路径产出与原管线同构）。

- [ ] **Step 7: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 4 数据管线"
```

---

### Task 6: Part 5 — 模型与训练（消融驱动选主干，3 卡编排）

**Files:**
- Modify: 目标 spec（替换 `## 5.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 2 模型资产、Part 4 数据布局。
- Produces: 消融轴、A/B/C/D 阶段化（3 卡并行）、训练配置基线、决策规则 + 止损线、3×5090 算力预算、坍缩检测——Part 6 评估协议与 Part 8 Timeline 的 M3 直接引用。

- [ ] **Step 1: 写 5.1 为何不预设主干（前向论证）**

~8.4K 实例 / ~10 万图像是方法选型支点。正面陈述三个候选的定位：CNN 双分支 + 域对抗 = 相近规模草图检索的成熟配方、数据高效、有部署参考 → **默认基线**；B-rep 几何（GNN/BOTH）在 CAD 侧零草图域差、结构上最可能赢实例检索 → **最值得验证的上行项**；CLIP-ViT+LoRA 在小规模细粒度集无定论 → **风险臂，须先过坍缩探针门**。结论：主干由实验定，spec 固化"如何决定"。

- [ ] **Step 2: 写 5.2 消融轴（表）**

四轴：草图主干（SE-ResNet50 / CLIP-ViT+LoRA）、CAD 分支（CNN-only / GNN-only / BOTH）、域损失（开/关）、对比损失（HardTripletMargin / InfoNCE）。每轴标注仓库支持点。完整网格 2×3×2×2=24 run，不全跑；用部分析因 + 单轴扫描。

- [ ] **Step 3: 写 5.3 阶段化执行 A/B/C/D**

A 坍缩探针（<1h，先于任何训练）：冻结 CLIP 零训练 embed ~2K 留出草图 + 视图，跑零样本 Top-100 + 有效秩 / 随机对平均余弦；判据放行/降级 CLIP 臂。B 关键二选一（R1 SE-R50/CNN-only/triplet 基线锚点 + R3 SE-R50/BOTH/triplet 几何上行）。C 按决策规则展开 ≤9 run 部分析因矩阵（给完整 R1–R9 表）。D 定稿：选主干 + 换种子复现。

- [ ] **Step 4: 写 5.4 训练配置基线**

骨架 partial pretrain（`seresnet50.a1_in1k.bin`）；输入 224² 灰度转 3 通道；草图增强（旋转/抖动/翻转）视图用 test transform；优化器 timm AdamW+cosine 起点 lr≈1e-3（V2，有出处）batch 视显存；损失 HardTripletMarginLoss（V2 默认）+ InfoNCE 消融；B-rep 图 `graph_hidden_dim=512`（5090，仓库注释有出处）；存档 checkpoint + 断点续训 + 分离导出（`extract_mode='separate'`）。

- [ ] **Step 5: 写 5.5 评估协议与决策规则**

划分按草图（gallery=全部 ~8.4K，每模型留 1 张草图作 query）；固定协议（同索引/query/种子跨所有 run）；主指标 Top-1，Top-10 平手区分 + 坍缩探测；**决策规则**：差异算真 ⟺ ΔTop-1 ≥ 2 绝对点 且换第二种子仍成立（~8.4K query bootstrap 95% CI 半宽≈1 点，2 点可辩护——有统计出处非魔法数）；低于此取更简单/更便宜架构（CNN-only 优于 BOTH、SE-R50 优于 CLIP）；报告 bootstrap 95% CI。

- [ ] **Step 6: 写 5.6 算力预算（3× RTX 5090）**

探针 <1h；单 run（triplet/InfoNCE）≈2-4h，BOTH 加 GNN ≈+30%；STEP→图预处理一次性离线 ~数小时。**3 卡并行编排**：阶段 B 两 run 分占两卡 ≈ 半日；阶段 C ≤9 run 分波（每波 3 卡）纯算力 ~0.5-0.7 天；D top-2 换种子双卡并行 ≈ 半日。单卡基线对照（9 run 串行 ≈1.5-2 天）以示并行收益。

- [ ] **Step 7: 写 5.7 坍缩与退化检测（贯穿训练）**

监控 batch 内检索准确率（loss 已返回 accuracy）；周期性 embed 留出集看有效秩 / 随机对平均余弦；Loss NaN 即抛异常停训。

- [ ] **Step 8: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 5 模型与训练"
```

---

### Task 7: Part 6 — 评估协议与目标指标

**Files:**
- Modify: 目标 spec（替换 `## 6.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 5 决策规则。
- Produces: 评估对象、划分协议、目标指标（数据驱动留白 + 止损线）、统计方法——Part 9 train/build-artifact 单元的验收引用。

- [ ] **Step 1: 写 6.1 评估对象**

离线检索评估（主）：留出草图集跑全库检索算 Top-K，是选主干/定阈值依据。真实草图小评估（辅）：手绘 30-50 张真实草图标注对应模型，验证 PhotoSketch 合成草图与真实手绘的效果差距——"训练分布 vs 部署分布"差异的早期信号。

- [ ] **Step 2: 写 6.2 划分与协议（固化为评估规范）**

gallery=全部 ~8.4K；query=每模型留出 1 张草图（顶/底各留思路，~8.4K query）；索引 FAISS flat（离线评估），度量由主干定（triplet→L2，InfoNCE/cosine→IP），`manifest.metric` 声明、建库/训练/检索三处一致；去重 top-(ratio×k) 后按 model_id 取最优，V2 ratio=2；指标 Top-1/10/20/50/100 + bootstrap 95% CI。

- [ ] **Step 3: 写 6.3 目标指标（数据驱动留白 + 相对止损线）**

表格给方向性目标（不写死数字）：Top-1=经评审认可水平（基线锚点见阶段 B 实测）；Top-10 显著高于 Top-1（平手区分 + 坍缩探测）；真实手绘 Top-10 报告与合成草图差距（部署可用性参考）；p95 交互级。明确**相对止损线**：若候选配置 Top-1 低于阶段 B 实测基线锚点达决策规则阈值（ΔTop-1≥2 点）即触发回退（Part 10）。最终交付阈值 = 阶段 B 实测基线 + 决策规则选出的最优配置实测值，写入交付报告。**重申不预设魔法数。**

- [ ] **Step 4: 写 6.4 统计方法**

bootstrap CI 计算方式（over query 集重采样）；ΔTop-1≥2 点判据的统计依据（CI 半宽≈1 点）；换种子复现要求；坍缩量化指标（有效秩、随机对平均余弦的报告方式）。

- [ ] **Step 5: 写 6.5 坍缩与退化检测（评估侧固化）**

训练中监控 batch 内检索准确率；周期性 embed 留出集看有效秩 / 随机对平均余弦；Loss NaN 停训。与 Part 5.7 呼应但此处固化为评估规范（何时测、测什么、判据）。

- [ ] **Step 6: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 6 评估协议"
```

---

### Task 8: Part 7 — 部署与服务（Python→ONNX→Rust→Astro，FastAPI 回退）

**Files:**
- Modify: 目标 spec（替换 `## 7.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 3 不对称架构、Part 5 选定主干。
- Produces: ONNX 导出规格、向量检索方案、产物契约全 schema、`/search` API 全契约、安全要求、回退判定——Part 9 build-artifact/serve/frontend 三单元直接据此展开。

- [ ] **Step 1: 写 7.1 推理路径（PyTorch → ONNX）**

SE-ResNet50 草图编码器干净导出（纯 conv/BN/ReLU/SE/池化/linear，opset 17+，仅 batch 维动态轴，H/W 固定 224）。CLIP-ViT+LoRA（若选）先 `merge_and_unload()` 并入基座再导出（绝不把 adapter 当独立分支），固定方形输入、关闭异型 attention kernel，导出后做 PyTorch↔ONNX 数值对齐测试（mean cosine > 0.999 且 top-K 一致）才放行。B-rep GNN 确认离线-only：PyG `scatter_reduce` 是 ONNX 雷区，GNN 只在建库产向量永不进 ONNX/Rust。烘进图内容：首版啥也不烘，归一化可后期作 2-op 前缀折叠。

- [ ] **Step 2: 写 7.2 向量检索**

首版暴力点积（`embeddings[N×512]·query[512]` + top-K，建库已 L2 归一化 serve 只点积）。规模阈值：512 维 CPU 暴力到 ~1-2M 仍可接受、GPU 几乎永够；超 ~1-2M 且 CPU 受限再上 ANN。ANN 选型 usearch（Rust 原生、cosine/IP）；不在 Rust 碰 FAISS（绑定弱）。V2 顶/底去重在 top-100 之上做，与是否 ANN 无关。

- [ ] **Step 3: 写 7.3 服务形态（Rust / axum）**

启动加载：ONNX 编码器（`ort` crate，CUDA EP 优先 CPU EP 回退）+ `embeddings.npy`（mmap）+ ids + metadata。端点：`GET /healthz`；`POST /search`（multipart 图片 + 可选 k → JSON）；缩略图静态服务或 `GET /models/:id/thumbnail`。预处理放 Rust 端（`image` crate），参数（input_size/channels/mean/std/resize_mode）写进 manifest 冻结契约。启动校验：ONNX 输出维 == embeddings 列数 == manifest.dim，行数 == ids 长度，不匹配拒启动。

- [ ] **Step 4: 写 7.4 产物交接契约（build → serve，全 schema）**

给完整 `artifact/` 目录树 + 每文件 schema：`manifest.json`（schema_version/dim:512/metric/count/encoder/normalized/preprocess{input_size,channels,mean,std,resize_mode}）、`embeddings.npy`（float32 [N,512] 行主序 L2 归一化）、`ids.json`（[N] row→model_id，含 slot top/bottom）、`metadata.json`（model_id→{name,step_path,thumbnail_path,view_count,source}）、`sketch_encoder.onnx`、`thumbnails/`。契约规则：建库时归一化；manifest 是版本门（schema_version/dim/metric 不匹配拒启动）；热数组与映射分离；换主干只要产同样 .npy+.onnx 则 serve 无感。

- [ ] **Step 5: 写 7.5 `/search` API 全契约**

请求：multipart（image 字段 + 可选 k）。响应 JSON schema：`{query_id, results:[{model_id, score, rank, thumbnail_url, metadata}]}`。错误码（400 解码失败/413 超限/415 MIME 不支持/429 限流/503 未就绪）。serve↔frontend 的唯一契约。

- [ ] **Step 6: 写 7.6 前端（Astro）**

复用 `web/` Astro demo（three.js 查看器、结果网格、上传栏）。改动：上传草图 → fetch multipart 到 `/search` → 渲染 top-K 缩略图+分数 → 点击查看 3D。与 serve 经 `/search` JSON 解耦。

- [ ] **Step 7: 写 7.7 安全（网络暴露前必做）**

上传图片限 body 大小（5-10MB）、限解码后分辨率（防图片炸弹）、限 MIME、请求超时；暴露前加鉴权（至少共享 token）+ 限流（按 IP/用户）；缩略图/CAD 文件禁任意路径访问；不在公网开放无鉴权端点。

- [ ] **Step 8: 写 7.8 诚实回退判定**

Rust 是否值得（热路径单小模型，相对 FastAPI 延迟优势有限；实益是单二进制/无 GIL/低空闲内存）；回退触发：`ort`+CUDA EP 在 5090（Blackwell/CUDA12.x）链接打包不顺 → 退回 FastAPI + onnxruntime-gpu，`/search` API 完全一致、前端无感、零能力损失。

- [ ] **Step 9: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 7 部署与服务"
```

---

### Task 9: Part 8 — 开发流程与时间线（Timeline 专章）

**Files:**
- Modify: 目标 spec（替换 `## 8.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 4/5/7（各阶段技术内容）、Global Constraints 的 3 卡硬件。
- Produces: 里程碑总览、依赖 DAG、逐里程碑展开、关键路径 CPM、3 卡并行调度、阶段分带、缓冲节奏——本章是排程依据，与 Part 9 单元一一映射。形式 = **里程碑 + 相对工期（work-day, WD）**，不绑日历。

- [ ] **Step 1: 写 8.1 时间线约定**

工期单位 = 工作日（WD），相对计、不绑日历（起始日变动不失效）。硬件 3×RTX 5090。单人开发。每里程碑设退出门（完成判据），不过门不进下一里程碑。

- [ ] **Step 2: 写 8.2 里程碑总览表**

表格 M0–M6：里程碑 / 内容 / 工期(WD) / 前置 / 可并行项。M0 环境对齐 2-3WD；M1 数据落地 3-5WD；M2 B-rep 图补全 3-4WD；M3 消融决策 3-4WD（3 卡并行）；M4 建库与产物 2WD；M5 服务上线 4-6WD（回退 2-3）；M6 前端联调 2WD。

- [ ] **Step 3: 写 8.3 依赖 DAG（ASCII 图）**

画 `M0→M1→M2→M3→M4→M5→M6` 主链 + 重叠标注：M2 提取器在 M1 probe 完成后并行开发；M3 阶段 A 坍缩探针只需 views+sketches 可早于 M2 启动；阶段 B 的 R1(CNN-only)不需图、R3(BOTH)需 M2；M5 Rust 脚手架可对 mock artifact 先写；M6 可对 mock `/search` 先接。

- [ ] **Step 4: 写 8.4 逐里程碑展开（M0–M6 各一小节）**

每里程碑写：进入条件 / 任务清单（映射 Part 9 单元）/ 工期估计 / 完成判据（退出门）/ 可并行编排 / 触发的风险点（指向 Part 10）。
- M0：装栈 + 验证 3 个已知依赖风险（PyG↔torch2.8 / faiss-gpu / ort↔CUDA12.8）；判据 `train.py --debug`+`test.py` 跑通。
- M1：取/重建 views·sketches·train·test + manifest + 探查 + 直方图；判据 8.4K 齐、manifest 有 flag、直方图产出。
- M2：STEP→UV-grid 图提取器 + graph*.pt + 失败清单回退；判据 GNN 能加载图前向、失败模型记录且回退 CNN-only。
- M3：A→B→C→D；判据按决策规则选主干 + 换种子复现 + 消融报告。
- M4：选定主干提全库特征 + 打包 artifact；判据 artifact 齐且过 serve 启动校验。
- M5：ONNX 导出 + 对齐门 + Rust/axum `/search`（或 FastAPI 回退）；判据端到端 top-K 正确、p95 交互级。
- M6：Astro 接 `/search`；判据 demo 可演示完整查询流程。

- [ ] **Step 5: 写 8.5 关键路径 (CPM)**

关键路径 `M0→M1→M2→M3→M4→M5→M6`；朴素串行 ≈19-26WD；计入重叠（M2 压 M1、M5 脚手架压 M4、M6 接 mock 压 M5、M3 三卡并行）关键路径 ≈16-21WD；最大不确定度在 M5（Rust 顺否）与 M1（网盘直取 vs 开源层重建）。

- [ ] **Step 6: 写 8.6 三卡并行调度方案（表）**

表格 M3 各阶段 × 卡0/卡1/卡2 × 墙钟：A 探针（卡0 跑 CLIP 零样本，余空闲，<1h）；B 关键二选一（卡0=R1、卡1=R3，~半日）；C 矩阵分波（波1 R2/R4/R5、波2 R6/R7/R8、波3 R9，每波 2-4h）；D 定稿（卡0/卡1 top-2 换种子，~半日）。注明单卡 9 run 串行 ≈1.5-2 天 vs 3 卡分波 ~0.5-0.7 天的并行收益。

- [ ] **Step 7: 写 8.7 阶段分带（高层视图）**

5 带：① 打地基（M0+M1 起步，出口=debug mini-batch 跑通 + 数据可见）；② 补几何（M1 收尾+M2，出口=GNN 加载图前向 + 失败回退）；③ 定主干（M3，出口=选主干 + 换种子复现 + 消融报告）；④ 上服务（M4+M5，出口=`/search` 端到端 + p95 交互级）；⑤ 交付（M6+复现演练+清单核对，出口=demo 完整流程 + 交付物齐）。

- [ ] **Step 8: 写 8.8 缓冲与回顾节奏**

每里程碑出口设退出门（指向 Part 9 验收）；M0 依赖三连任一不过触发 Part 10 回退（PyG 不兼容→先只跑 CNN 分支推迟 GNN；ort 打包不顺→M5 走 FastAPI）；关键路径每带留 ~15% 缓冲吸收 M1/M5 不确定度。

- [ ] **Step 9: 结构门 + 禁用词门 + 行数检查 + 提交**

Run 两道门 → `14` / `CLEAN`；Run 行数自检确认 Part 8 已显著增重。
```
git add <目标spec>
git commit -m "docs(spec): Part 8 开发流程与时间线（Timeline 专章）"
```

---

### Task 10: Part 9 — 单元执行规格（9 单元 × 全维度，行数主引擎）

**Files:**
- Modify: 目标 spec（替换 `## 9.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 4（数据管线 5 单元的技术内容）、Part 7（部署 3 单元）、Part 5/6（train 单元）。
- Produces: 9 个执行单元各一节，**全维度展开**——这是 writing-plans 拆任务的直接依据，也是本 spec 的行数主体。9 单元：download/probe/render/sketch/graph/train/build-artifact/serve/frontend。

**统一子节模板**（每单元 9 个固定维度，逐一填实，禁止占位）：

1. **职责** — 一句话边界 + 不做什么。
2. **输入 / 输出** — 精确路径与数据形态。
3. **接口契约** — 消费上游什么、产出下游什么（字段名/类型/路径布局），与相邻单元的耦合点。
4. **任务分解（checkbox）** — 该单元拆成的可执行子任务，每条一个动作粒度（供 writing-plans 直接采用）。
5. **量化验收** — 客观可验证的完成判据（数值或可程序化检查），**不用"足够/充分"含糊词**。
6. **命令意图** — 跑什么、看什么输出（命令意图非可复制脚本）。
7. **测试矩阵** — 表格：用例 / 输入 / 期望 / 失败信号；含正常路径 + 边界 + 失败注入。
8. **失败处理** — 每类失败如何检测、记录（manifest status）、是否阻塞、如何重跑。
9. **回退** — 该单元的降级路径（指向 Part 10），及通过哪个契约隔离不波及他单元。

- [ ] **Step 1: 写 9.0 单元总览 + 统一模板说明**

写一段：Part 9 把系统拆成 9 个可独立开发/测试/重跑的单元，每单元按上述 9 维模板展开；给一张单元依赖小表（单元/职责/输入/输出/依赖），作为本章导航。声明本章是 writing-plans 拆任务的直接依据。

- [ ] **Step 2: 写 9.1 download/ingest 单元（全 9 维）**

职责：取 STEP、登记 manifest。输入 ABC chunk/网盘；输出 `step/**`、manifest 行。依赖代理、py7zr。任务分解含：下载器复用（7z header 校验 + 5x 重试 + resume + 代理）、manifest 初始化登记、断点续传。验收：8.4K STEP 落盘、manifest 每行有 src_path + 初始 status。测试矩阵：正常下载 / 损坏 7z / 网络中断 resume / 代理失效。失败处理：校验失败重试 5 次后记 manifest `download_failed`。回退：网盘直取失败 → 开源层从 ABC 官方下载。

- [ ] **Step 3: 写 9.2 probe 单元（全 9 维）**

职责：拓扑探查、质量 flag（不 mesh）。输入 manifest pending 行；输出 probe 列 + render_eligible。依赖 OCC。任务分解含：STEP 拓扑遍历、采集 n_faces/n_solids/退化指标、写 quality_flags、首跑后看直方图回填阈值。验收：每模型有 probe_* 指标 + render_eligible 布尔 + 致命 flag 集判定。测试矩阵：正常实体 / 无实体 no_solid / 面数过多 too_complex / 退化 degenerate / STEP 解析失败。失败处理：解析失败记 `probe_failed` 不阻塞他模型。回退：阈值过严误筛 → 看直方图放宽（配置非硬编码）。

- [ ] **Step 4: 写 9.3 render 单元（全 9 维）**

职责：STEP/mesh → 12 视图。输入 render_eligible STEP；输出 `views/<model>/<model>_{0..11}.png`。依赖 Sketch3DToolkit（原管线）/ moderngl·pyrender（开源层）。任务分解含：STEP→mesh、12 视图（顶6底6，224²）渲染、双路径产同构布局校验。验收：每 eligible 模型 12 张视图、命名合规、双路径产物布局一致。测试矩阵：正常渲染 / mesh 失败 / 视图缺失 / 双路径一致性。失败处理：渲染失败记 `render_failed`、该模型不入训练集。回退：商业工具不可用 → 开源 moderngl 路径。

- [ ] **Step 5: 写 9.4 sketch 单元（全 9 维）**

职责：视图 → 草图。输入 `views/`；输出 `sketches/<model>/*.png`（0-11 与视图一一对应）。依赖 PhotoSketch（预训练 GAN，纯推理）。任务分解含：PhotoSketch 权重就位、逐视图风格迁移、编号对齐校验。验收：每视图一张草图、编号与视图对应、风格抽检通过。测试矩阵：正常迁移 / 权重缺失 / 编号错位 / 空白草图。失败处理：迁移失败记 `sketch_failed`。回退：开源路径同用 PhotoSketch（本步本就开源可复现）。

- [ ] **Step 6: 写 9.5 graph 单元（全 9 维，关键补全项）**

职责：STEP → UV-grid B-rep 图。输入 render_eligible STEP；输出 `graph*.pt`（list of `{name, graph}`）+ 失败清单。依赖 OCC + torch_geometric。任务分解含：OCC `STEPControl_Reader` 读、`TopExp_Explorer` 遍历面/边、采 UV 网格（node 14+7 / edge 15+12 维）、`replace('step','trimesh')` 命名对齐、聚合 graph*.pt。验收：成功模型图能被 `ComplexGNN` 加载并前向、name 与 views/sketches 子目录可对齐、失败模型在失败清单且 BOTH 分支回退 CNN-only（图特征置零）。测试矩阵：正常提取 / 提取失败回退 / 命名对齐 / 维度匹配 ComplexGNN 期望 / 空图。失败处理：提取失败记 `graph_failed` + 标记该模型 CNN-only-fallback，不丢弃不阻塞。回退：图提取失败率高 → 全流程先跑 CNN-only（Part 10）。

- [ ] **Step 7: 写 9.6 train 单元（全 9 维）**

职责：消融训练、选主干。输入 views/sketches/graph；输出主干 checkpoint + 消融报告。依赖仓库 trainer。任务分解含：阶段 A 探针、阶段 B（R1/R3）、阶段 C 矩阵（3 卡分波）、阶段 D 定稿换种子、产消融报告。验收：按决策规则（ΔTop-1≥2 点且换种子成立）选出主干、报告含 bootstrap 95% CI、坍缩检测无异常。测试矩阵：探针放行/降级 CLIP / 单 run 收敛 / NaN 停训 / 断点续训 / 3 卡并行无冲突。失败处理：CLIP 坍缩降级 SE-R50；Loss NaN 抛异常停训。回退：几何无显著增益 → CNN-only（省 graph 单元）。

- [ ] **Step 8: 写 9.7 build-artifact 单元（全 9 维）**

职责：提全库特征、打包 artifact。输入选定主干 + 全库；输出 `artifact/`（Part 7.4 契约）。依赖仓库 inference + ONNX 导出。任务分解含：全库提特征（512-d，V2 顶/底各一条）、L2 归一化、ONNX 导出 + PyTorch↔ONNX 对齐门（cosine>0.999 且 top-K 一致）、写 manifest/ids/metadata、生成 thumbnails。验收：artifact 齐全、过 serve 启动校验（维度/行数/映射一致）、对齐门通过。测试矩阵：CNN 导出 / CLIP merge_and_unload 后导出 / 对齐门失败拦截 / manifest 版本门 / 维度不匹配检出。失败处理：对齐 cosine<0.999 阻断打包。回退：ViT 导出漂移 → 用 CNN 主干（对齐风险低）。

- [ ] **Step 9: 写 9.8 serve 单元（全 9 维）**

职责：在线检索。输入 `artifact/` + 上传草图；输出 `/search` JSON。依赖 ort/onnxruntime。任务分解含：启动加载（ONNX + embeddings mmap + ids + metadata）、启动校验、Rust 预处理（image crate）、暴力点积 top-100 + 去重 top-K、`/healthz`+`/search`+缩略图端点、安全（限 body/分辨率/MIME/超时 + 鉴权 + 限流）。验收：`/search` 端到端 top-K 正确、p95 交互级、启动校验拒绝不匹配 artifact、安全项全开。测试矩阵：正常查询 / 维度不匹配拒启动 / 图片炸弹防护 / 超限 413 / 非法 MIME 415 / 限流 429 / CUDA EP 回退 CPU。失败处理：artifact 不匹配拒启动；CUDA EP 失败回退 CPU EP。回退：`ort`+CUDA 打包不顺 → FastAPI + onnxruntime-gpu，`/search` API 不变。

- [ ] **Step 10: 写 9.9 frontend 单元（全 9 维）**

职责：上传与展示。输入 `/search`；输出浏览器 UI。依赖 Astro。任务分解含：复用 `web/` demo、上传栏 fetch multipart 到 `/search`、渲染 top-K 缩略图+分数、点击查看 three.js 3D。验收：demo 可演示完整查询流程、对 mock `/search` 与真实 serve 均可跑。测试矩阵：正常查询展示 / serve 不可用错误态 / 空结果 / 3D 查看 / 大图上传客户端校验。失败处理：serve 503 时前端友好降级。回退：与 serve 经 `/search` JSON 解耦，serve 换实现前端无感。

- [ ] **Step 11: 结构门 + 禁用词门 + 行数检查 + 提交**

Run 两道门 → `14` / `CLEAN`；Run 行数自检确认 Part 9 为最大章节（目标 ~1500 行，全文应已逼近或超过 5000）。
```
git add <目标spec>
git commit -m "docs(spec): Part 9 单元执行规格（9 单元全维度）"
```

---

### Task 11: Part 10 — 风险登记册

**Files:**
- Modify: 目标 spec（替换 `## 10.` 占位段，append 正文）

**Interfaces:**
- Consumes: 全部前述 Part 的风险点引用（Part 8 里程碑、Part 9 各单元回退）。
- Produces: 完整 risk register——Part 8/9 的"触发风险点/回退"指向此处。

- [ ] **Step 1: 写 10.1 风险登记册（主表）**

表格列：风险 / 触发信号 / 概率 / 影响 / 缓解 / 回退 / 责任单元（映射 Part 9）。至少覆盖：PyG↔torch2.8 不兼容（M0/train）、B-rep 图提取失败率高（M2/graph）、CLIP 坍缩（M3/train）、几何无显著增益（M3/train）、合成草图≠真实手绘（M3/M6）、ONNX↔PyTorch 漂移（M5/build-artifact）、`ort`+CUDA-EP 打包不顺（M5/serve）、检索延迟超预算（M5/serve）、数据盘/显存不足（多单元）。

- [ ] **Step 2: 写 10.2 回退总原则**

每一级回退向"更简单、更已验证"方向走；通过契约（产物契约 / `/search` API）隔离，使回退不波及其他单元。给一张"风险 → 回退后系统形态"对照（如 GNN 失败→CNN-only 全流程仍闭环；Rust 失败→FastAPI 同 API）。

- [ ] **Step 3: 写 10.3 风险监控点**

每个风险绑定一个可观测信号 + 在哪个里程碑/单元的退出门检查。强调 M0 依赖三连（PyG/faiss/ort）须最早验证。

- [ ] **Step 4: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 10 风险登记册"
```

---

### Task 12: Part 11 — 技术栈与环境约束

**Files:**
- Modify: 目标 spec（替换 `## 11.` 占位段，append 正文）

**Interfaces:**
- Consumes: 全文技术选型。
- Produces: 技术栈表、3×5090 环境约束、跨平台说明、依赖验证点——Part 8 M0 与 Part 9 各单元的环境前提。

- [ ] **Step 1: 写 11.1 技术栈表**

表格：层 / 选型 / 理由（前向）。训练 Python3.12+PyTorch2.8(CUDA12.8)；CAD 编码/图 torch_geometric+OCC/OCP；骨架 timm SE-ResNet50 + 可选 OpenCLIP ViT-B/16（消融对比臂）；离线评估 FAISS flat；导出 ONNX opset17+；在线推理 ort crate（回退 onnxruntime-gpu）；在线检索 暴力点积→usearch；服务 Rust+axum（回退 FastAPI）；前端 Astro+three.js；数据管线 商业工具沿用+OCC/moderngl 开源层；manifest LanceDB。

- [ ] **Step 2: 写 11.2 环境约束（3× RTX 5090）**

GPU 3×RTX 5090（32GB each，Blackwell，CUDA12.8）；数据落盘写大盘（`~/data` 约定）禁写仓库/`/tmp`；外网走代理（`http://127.0.0.1:7890`）；预训练权重位置（`seresnet50.a1_in1k.bin` → `model/Baseline/path_state_dict/`，PhotoSketch 在 `tool/PhotoSketch.zip`）。

- [ ] **Step 3: 写 11.3 依赖验证点（M0 必验）**

三个已知风险依赖：PyG↔torch2.8（import/编译）、faiss-gpu（CUDA12.8 可用）、ort↔CUDA12.8（5090 链接打包）。每条给验证方式 + 不过的回退（指向 Part 10）。

- [ ] **Step 4: 写 11.4 跨平台说明**

训练在 GPU 机（Linux 路径约定）；开发机 Windows（仓库/spec/前端）；去重脚本含 PowerShell 需移植或 Windows 侧跑；路径分隔/shell 语法按目标机调整，spec 不绑单一 OS。

- [ ] **Step 5: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 11 技术栈与环境"
```

---

### Task 13: Part 12 — 交付清单与验收

**Files:**
- Modify: 目标 spec（替换 `## 12.` 占位段，append 正文）

**Interfaces:**
- Consumes: Part 8 里程碑出口、Part 9 单元验收。
- Produces: 交付物逐项验收标准 + 最终复现演练——项目收尾的客观判据。

- [ ] **Step 1: 写 12.1 交付物清单（逐项验收）**

表格每项：交付物 / 验收标准（客观可验证）/ 责任单元。覆盖：可复现全流程脚本、训练好的主干模型+消融报告（含决策规则实测依据与最终阈值）、artifact 产物、Rust/axum 服务（或 FastAPI 回退）+API 文档、Astro 前端 demo、数据 manifest+质量直方图+失败清单、本 spec+实现 plan+复现 README。

- [ ] **Step 2: 写 12.2 最终复现演练**

一条端到端复现路径（命令意图序列）：从现有数据 → 训练选定主干 → 建索引 → 起服务 → 前端可查。作为交付前的总验收脚本意图。

- [ ] **Step 3: 写 12.3 演示物（备注）**

以**备注**形式说明：`presentations/` 与 `web/` 可指向真实 `/search`，把概念演示升级为实物演示，无需重写。**降级为备注，不作为硬交付项。**

- [ ] **Step 4: 写 12.4 验收门总表**

汇总 M0–M6 各退出门 + 交付物验收为一张总验收清单（checkbox），作为项目 done 的单一判据。

- [ ] **Step 5: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 12 交付清单与验收"
```

---

### Task 14: Part 13 — 附录

**Files:**
- Modify: 目标 spec（替换 `## 13.` 占位段，append 正文）

**Interfaces:**
- Consumes: 全文。
- Produces: 术语表、配置项清单、命令速查、ADR 索引、测试用例索引——查阅辅助。**不含"与设计 spec 差异表"。**

- [ ] **Step 1: 写 13.1 术语表（全文汇总）**

汇总全文术语定义（实例检索/gallery/query/视图/草图/B-rep 图/消融轴/坍缩探针/产物契约/止损线/关键路径/退出门等）。

- [ ] **Step 2: 写 13.2 配置项清单**

汇总有出处的固定值与待回填阈值两张表：固定值（num_classes=8422、n_views=6、deduplicate_ratio=2、node/edge 维度、graph_hidden_dim=512、opset17+、ΔTop-1≥2 点）；待回填（probe 阈值看 n_faces/file_size 直方图、检索准确率目标看阶段 B 基线、ANN 切换看向量规模）——每条标回填依据。

- [ ] **Step 3: 写 13.3 命令意图速查**

按单元汇总命令意图（download/probe/render/sketch/graph/train/build/serve/frontend 各跑什么看什么），含禁用词门与行数自检命令意图。

- [ ] **Step 4: 写 13.4 ADR 索引**

汇总全文架构决策（不对称 / 暴力检索 / Rust+FastAPI 逃生舱 / 消融驱动 / GNN 离线-only），每条决策+前向理由+影响单元，链接到正文位置。

- [ ] **Step 5: 写 13.5 测试用例索引**

汇总 Part 9 各单元测试矩阵为一张总索引（单元 / 用例数 / 关键失败注入），便于 writing-plans 转成测试任务。

- [ ] **Step 6: 结构门 + 禁用词门 + 提交**

Run 两道门 → `14` / `CLEAN`。
```
git add <目标spec>
git commit -m "docs(spec): Part 13 附录"
```

---

### Task 15: 全文终检（结构 + 约束 + 行数 + 自审）

**Files:**
- Read-only：目标 spec 全文。

**Interfaces:**
- Consumes: Part 0–13 全部已写。
- Produces: 通过全部门的终稿 + 一份终检结论（供用户评审）。

- [ ] **Step 1: 结构完整门**

Run（Bash）：`grep -nE '^## [0-9]+\. ' <目标spec> | wc -l` → Expected `14`；逐一核对 Part 0–13 标题存在且唯一、占位行（`（本节由对应任务填充）`）已全部被正文替换（`grep -c '本节由对应任务填充' <目标spec>` → `0`）。

- [ ] **Step 2: 禁用词约束门（全文）**

Run（Bash）：`grep -nE '转向|原方案|原计划|老方案|旧方案|老的设计|上次|上一次|此前失败|复盘|降级为|降为|我们改了|与设计 spec 差异|相比之前|原来的' <目标spec> || echo CLEAN` → Expected `CLEAN`。若命中，逐处改为前向陈述后重跑。

- [ ] **Step 3: 行数门**

Run（Bash）：`wc -l <目标spec>` 或（PowerShell）`(Get-Content <目标spec>).Count` → Expected `> 5000`。未达标则回到行数最薄的 Part 用真内容增重（优先 Part 9 各单元的测试矩阵/任务分解），不灌水。

- [ ] **Step 4: 魔法数自查**

通读所有数值，确认每个都属三类之一（标回填依据 / 数据驱动留白+止损线 / 有明确出处）。可疑数值改为留白或补出处。

- [ ] **Step 5: spec-self-review（强制）**

按 writing-specs 流程跑 spec 自审：覆盖度（每个 Part 的需求都有对应正文）、独立性（无回指措辞、无"与上游关系"章节、无差异表）、可执行性（Part 9 可被 writing-plans 直接拆任务）。产出自审结论。

- [ ] **Step 6: 终检提交**

```
git add <目标spec>
git commit -m "docs(spec): 全文终检通过（结构/约束/行数/自审）"
```

---

## Self-Review（本计划对 spec 的覆盖核对）

**覆盖**：13 个 Part 全部有对应 Task（Task 0 骨架 → Task 1–14 逐 Part → Task 15 终检）。Timeline 专章 = Task 9（Part 8），全维度展开 = Task 10（Part 9，9 单元 × 9 维模板）。

**用语约束**：每个 Task 收尾都跑禁用词门；已删除"与上游设计的关系"章节与"与设计 spec 差异表"附录；理由全前向陈述。

**3 卡硬件**：Task 6（算力预算 5.6）、Task 9（并行调度 8.6）、Task 12（环境约束 11.2）三处落地。

**魔法数**：Task 1（0.3 禁令）、Task 7（6.3 留白+止损线）、Task 15（Step 4 自查）三道防线；有出处固定值在 13.2 集中列示。

**行数**：Part 9 为主引擎（~1500），Task 15 Step 3 行数门兜底 >5000。

**无占位**：每个 Step 给出该 Part 要写的具体内容要点（非"待填"），校验给出确切命令意图与期望输出。
