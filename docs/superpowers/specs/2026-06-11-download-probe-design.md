# ABC 数据集下载与基本指标测绘 (Download + Probe) 系统设计

> 日期: 2026-06-11
> 状态: 设计完成，待实施
> 范围: pipeline 最前两步 —— 下载 (download) 与基本指标测绘 (probe)。
> 不含: 渲染 / sketch / caption / embedding（但其 manifest 列现在即建好占位）。

---

## 1. 目标与背景

把 1M ABC STEP 数据集**拉全**，并为每个 model 做**廉价的基本指标测绘**，
产出一张可查询的 **LanceDB manifest 主表**，作为后续所有阶段的事实来源。

**核心动机**（来自上次执行的真实教训）：
上次渲染卡在 276K/990K，剩余 STEP "太复杂渲染不动"，被迫把训练阈值从 900K 硬降到 340K
—— 即 "能否在 30s 内 mesh 完" 偷偷变成了隐式筛选规则，不可解释、不可复现。

本阶段用**便宜的拓扑探查**（不 mesh）预测哪些 model 会在 mesh 阶段爆炸，提前分流，
把质量筛选从 "渲染 timeout 的副产物" 提升为 "显式、廉价、可解释、可复现的一步"。

对应筛选文档（`context/2026-06-10-21-36-cost-estimate.md` Quality Filtering 节）的**方面 1 + 方面 2**。

---

## 2. 系统架构

### 数据流

```
ABC step_v00.txt (chunk 列表)
    ↓ download (curl + 代理 7890, 7z header 校验, 5x 重试, resume)
chunks/*.7z  ──py7zr 解压──>  step/**/*.step   (blob 层, 留在文件系统)
    ↓ ingest (扫描 + 登记, 不读文件内容)
LanceDB manifest 表 (每行一个 model, model_id = abc/<id>, src_path 指向磁盘文件)
    ↓ probe (拓扑探查, 不 mesh; 多 worker 探查 + 单 writer 串行 commit)
manifest 表写回 probe_* 列 + quality_flags + render_eligible
```

### 存储分层（关键设计）

| 层 | 内容 | 存哪 |
|---|---|---|
| blob 层 | 1M 个 `.step` 文件本体 (~500GB) | 解压后**留在文件系统** `step/**/*.step` |
| 元数据层 | 每个 model 一行: model_id / src_path / file_size_mb / probe 结果 / 各阶段 status | **LanceDB manifest 表**（瘦表，几 GB） |

STEP 字节**不进 LanceDB**。原因：① STEP 要被 OCC 反复 `ReadFile(path)` 解析（probe 读、渲染读），
必须是文件系统上的真实文件；② 500GB 二进制灌进表会让本该"瘦"的 manifest 变巨无霸，
违背"查询飞快"的初衷。manifest 用 `src_path` 引用磁盘上的文件。

### 三个独立单元（各自可单测、可单独重跑）

1. **download** — 继承现有 `context/history/src/cad_retriever/data/download.py`，几乎不动。
   职责：把 1M STEP 拉全并解压到 `step/`。
2. **ingest** — 新增。职责：扫描解压出的 STEP，在 manifest 表里为每个 model 建行
   （`model_id`/`source`/`src_path`/`format`/`file_size_mb`），各 `*_status` 初始化为 `pending`。
   这是**多源可扩展的边界** —— 以后新数据源就是新写一个 ingest adapter。
3. **probe** — 新增。职责：读 manifest 里 `probe_status=pending` 的行，做拓扑探查，
   写回拓扑列 + flags。**不 mesh、不渲染**，纯 CPU、可大规模并行。

**关键分工**：ingest 只管"登记存在"，probe 只管"测量质量"。拆开是因为重跑节奏不同 ——
download 慢且一次性，probe 会反复调阈值重跑。两者通过 manifest 表解耦。

---

## 3. 多源可扩展约定

- `model_id` 格式：`{source}/{id}`，如 `abc/00000123`，全局唯一，避免跨源撞名。
- 本阶段只接入 `source = "abc"` 一个源。
- ingest 留出 adapter 函数边界：未来加 DeepCAD / Fusion360 只需新写一个 adapter
  把该源的文件登记进同一张 manifest，**不改 schema**。

---

## 4. Manifest Schema (LanceDB 主表)

一张表，现在即建全所有列（后续阶段占位）。download/probe 阶段只填前几组。

```python
{
  # —— 身份/来源 (ingest 填) ——
  "model_id":      str,    # "abc/00000123" — 全局唯一, {source}/{id}
  "source":        str,    # "abc"
  "src_path":      str,    # 磁盘上 .step 的绝对路径 (blob 层指针)
  "format":        str,    # "step"
  "file_size_mb":  float,

  # —— 拓扑探查 (probe 填, 不 mesh) ——
  "probe_n_faces":   int,          # null until probed
  "probe_n_solids":  int,
  "probe_n_edges":   int,
  "probe_bbox_dims": list[float],  # [x, y, z]
  "probe_bbox_ratio":float,        # 最长/最短维
  "probe_status":    str,          # "pending"|"done"|"read_fail"|"probe_error"
  "probe_error":     str,          # null | 错误摘要

  # —— 判定 (probe 填) ——
  "quality_flags":   list[str],    # [] | ["too_complex","too_simple",...]
  "render_eligible": bool,         # 无致命 flag

  # —— 后续阶段占位 (本阶段全 null/pending) ——
  "render_status":   str,          # "pending"
  "sketch_status":   str,          # "pending"
  "caption_status":  str,          # "pending"
  "embedding":       list[float],  # 向量列, 后期 CLIP 填
}
```

现在就建好后续阶段列（含向量列），使本阶段产出的表后面渲染/caption/embedding 直接填，无需迁移 schema。

---

## 5. Probe 判定逻辑

对每行做以下判定（对应筛选文档方面 1 + 2）。

**方面 1（元数据，不开文件）**
- `file_size_mb > 50` → flag `oversized`（几何爆炸，mesh 大概率超时）
- 文件过小 / 空 / 截断 → flag `corrupt`

**方面 2（拓扑遍历，`STEPControl_Reader.ReadFile` + `TopExp_Explorer`，不调 `BRepMesh`）**
- `ReadFile != 1` → `probe_status = read_fail`，flag `step_read_fail`
- `n_solids == 0` → flag `no_solid`（纯曲面/线框，渲染无意义）
- `n_faces > 5000` → flag `too_complex`（mesh 必超时）
- `n_faces < 3` → flag `too_simple`（退化/平板/空壳，无信息量）
- bbox 某维 ≈ 0 → flag `degenerate`（退化成面/线）
- `bbox_ratio > 1000` → flag `degenerate`（细长件，渲染全黑/全白）

**`render_eligible`** = 无任何**致命 flag**。
- 致命集: `corrupt` / `step_read_fail` / `no_solid` / `degenerate` / `too_complex` / `too_simple`
- 非致命: `oversized`（仅作信号，不否决）

**关键约定 —— 阈值是配置，不是硬编码**：
上述阈值（50MB / 5000 / 3 / 1000）是**临时起点**，必须写成配置参数。
probe 第一遍跑完后，先看 `n_faces` / `file_size` / `n_solids` 的**真实直方图**，
再回填阈值 —— 避免重蹈 340K 魔法数的覆辙。本阶段交付物之一就是这份分布直方图。

> 待拍板的方向性决策（影响 `n_solids` / `n_faces` 阈值）：检索任务面向"零件级"还是"装配体级"。
> 仅单零件 → `n_solids > 1` 可直接筛掉/拆解；保留装配体 → 高 n_faces 需单独慢速渲染队列。
> 此决策可在拿到直方图后再定，不阻塞 probe 首跑。

---

## 6. 错误处理、并发、测试

### 错误处理（继承现有踩坑经验）
- **download**: 沿用 `download.py` 的 7z header 校验 + 5 次重试 + resume；失败 chunk 记录但不阻塞其余。
- **probe**: **单文件故障隔离** —— 任何 model 解析抛错只把该行标 `probe_status=probe_error`
  + 记错误摘要，**绝不中断整批**。这是 manifest 模式相对上次"timeout 默默吞掉"的核心改进:
  失败可查询、可分类、可单独重跑。

### 并发（LanceDB 写入）
- Lance 是版本化写入，多 worker 同时 append 同一表会产生版本冲突。
- 方案: **多 worker 并行探查 + 单 writer 串行 commit** —— worker 把结果丢队列，
  一个进程批量写 Lance。probe 瓶颈在 OCC 解析不在写，单 writer 完全够。
- **断点续跑**: probe 重跑只取 `probe_status = pending` 的行；
  download 靠 header 校验跳过已完成 chunk。

### 测试
- **download**: 小样本（几个 chunk）验证 header 校验 + resume + 解压。
- **ingest**: 临时目录放几个 `.step`，验证建行数、`model_id` 格式（`abc/<id>`）、
  `src_path` 正确、各 status 初始化为 pending。
- **probe**: **构造已知几何的 STEP**（一个简单立方体、一个空壳、一个超大面数件），
  断言各自命中预期 flag 和拓扑计数。这是保证阈值逻辑正确的关键。

---

## 7. 交付物

1. 填好 ingest/probe 列的 **LanceDB manifest 表**（后续阶段列建好占位）。
2. **ABC 几何复杂度直方图**（`n_faces` / `n_solids` / `file_size` 分布）—— 用于回填阈值。
3. **probe 汇总报告**: 各 flag 命中数、`render_eligible` 总数
   —— 让我们判断离 500K pretrain 目标还有多远。

---

## 8. 环境约束（AutoDL pod）

- GPU/盘: 数据写 `/home/cc/data`（2TB），**禁止**写 `/home/cc/cad-retriever/data/` 或 `/tmp/`。
- 外网: 全部走代理 `http://127.0.0.1:7890`（mihomo）。
- Python: `/root/miniconda3/bin/python3` (3.12.3)。
- 依赖: OCP (OpenCASCADE, 经 cadquery 装), py7zr, 新增 lancedb。
- probe 为纯 CPU 任务，可与其他 GPU 任务并行。
