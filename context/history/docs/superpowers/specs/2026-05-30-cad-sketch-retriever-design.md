# CAD Sketch Retriever 系统设计

> 日期: 2026-05-30
> 状态: 设计完成，待实施

---

## 1. 系统架构

### 离线阶段（Index Building）

```
STEP files (1M, ABC Dataset 完整下载)
  → Omniverse Kit CAD Converter → OpenUSD
  → Blender headless 渲染 6 标准视角 (224×224)
  → OpenCLIP ViT-B/16 (frozen) 逐视角提取 embedding
  → 6 embeddings mean pooling
  → Projection Head A (Linear 768→512 + LayerNorm)
  → 512-dim CAD vector
  → FAISS GpuIndexIVFFlat (nlist=1024, nprobe=64)
```

### 在线阶段（Sketch Query）

```
用户草图 (任意尺寸)
  → Resize + Normalize to 224×224
  → OpenCLIP ViT-B/16 (frozen + LoRA rank=16)
  → Projection Head B (Linear 768→512 + LayerNorm)
  → 512-dim query vector
  → FAISS GPU 检索 Top-100
  → 余弦相似度精排 → Top-K 返回
```

### 关键设计点

- 共享 backbone：CAD 侧和草图侧用同一个 OpenCLIP ViT-B/16，但草图侧加 LoRA 适配
- 统一 512 维空间：OpenCLIP 原始输出 768 维，projection head 降到 512（节省索引显存）
- CLIP 空间保留：projection head 不破坏 CLIP 的文本-图像对齐，未来文本检索直接可用
- 延迟预估：草图侧 ~3ms（ViT-B/16 TensorRT FP16）+ FAISS ~0.3ms = ~3.3ms，远低于 10ms

---

## 2. 训练策略

### 训练数据构造

```
ABC Dataset (完整 1M STEP files，必须全量下载后才开始处理)
  → 渲染 6 视角图 (224×224) — CAD 正样本
  → 对每个视角做 edge detection (HED + Canny fallback) — "伪草图"桥梁
  → 对边缘图做随机扰动 — 合成草图（训练用）
      扰动方式：线条抖动、随机断裂、粗细变化、局部缺失、轻微旋转
```

### Phase 1：CAD Projection Head 对齐（~0.5 天）

- 冻结 OpenCLIP backbone
- 训练 Projection Head A：让 CAD 多视图 embedding 投影到 512 维空间
- Loss：同一 CAD 不同视角的 embedding 应该接近（视角一致性）
- Batch size：512，学习率 1e-3，cosine decay

### Phase 2：草图→CAD 对比学习（~1-2 天）

- 冻结 OpenCLIP backbone + Projection Head A
- 训练 Projection Head B + LoRA（rank=16，应用于 ViT 的 QKV）
- Loss：InfoNCE 对比损失，草图 embedding ↔ 对应 CAD embedding
- 训练对：(合成草图, CAD vector) — CAD vector 用 Phase 1 的冻结 encoder 预计算
- Hard negatives：同类零件不同规格（几何相似但不同）
- Batch size：256，学习率 5e-4，温度 τ=0.07（可学习）
- 训练时长：~1-2 天（单卡 5090）

### Hard Negative Mining

- 每 epoch 结束用当前模型检索 Top-50
- 取 rank 5-20 作为下轮 hard negative
- 例：M6 螺栓 vs M8 螺栓，六角法兰 vs 圆形法兰

### Fallback 到中等训练的触发条件

如果 Phase 2 后合成草图 Recall@10 < 80%：
- 解冻 OpenCLIP 最后 2 层，全量 fine-tune
- 加入三阶段域桥接：渲染图→边缘图→合成草图（渐进对齐）
- 训练时长增加到 3-5 天

---

## 3. 数据管线与评估

### 数据管线（严格顺序，每步必须对全部 1M 完成后才进入下一步）

1. 完整下载 ABC Dataset 全部 1M STEP 文件
2. 全部 1M 文件转换 STEP → OpenUSD
3. 全部 1M 模型渲染 6 视角图 + 生成边缘图 + 合成草图
4. 全部 1M 模型预计算 CAD embedding（Phase 1 训练后）
5. 用完整 1M 数据集训练（全量参与对比学习，不做抽样）

### 存储预估

| 数据 | 单个大小 | 1M 总量 |
|---|---|---|
| STEP 原始文件 | ~500KB avg | ~500GB |
| USD 转换后 | ~200KB avg | ~200GB |
| 6 视角渲染图 (224×224 PNG) | ~150KB × 6 | ~900GB |
| 边缘图 + 合成草图 | ~50KB × 6 | ~300GB |
| CAD embeddings (512-dim FP32) | 2KB | ~2GB |
| **总计** | | **~1.9TB** |

### 评估方案

**测试集划分**：
- 从 1M 中随机抽取 5000 零件作为测试集（不参与训练）
- 剩余 995,000 零件作为训练集 + 检索库

**合成评估（自动化）**：
- 5000 测试零件各生成 5 张不同扰动程度的合成草图 = 25,000 条 query
- 指标：Recall@1, Recall@5, Recall@10, MRR

**真实草图评估（人工）**：
- 手绘 30-50 张真实草图，标注对应的 CAD 零件
- 用于验证合成草图与真实草图的效果差距

**目标指标**：

| 指标 | 合成草图目标 | 真实草图目标 |
|---|---|---|
| Recall@1 | >60% | >40% |
| Recall@10 | >90% | >70% |
| MRR | >0.7 | >0.5 |
| P99 延迟 | <10ms | <10ms |

**Fallback 触发**：合成草图 Recall@10 < 80% → 升级到中等训练

---

## 4. 推理优化与部署

### 硬件：RTX 5090（32GB VRAM）

### 延迟预算（草图查询）

| 阶段 | 目标延迟 | 优化手段 |
|---|---|---|
| 图像预处理 (resize + normalize) | <0.1ms | GPU resize |
| OpenCLIP ViT-B/16 + LoRA | <3ms | TensorRT FP16 |
| Projection Head B | <0.1ms | 融入 TensorRT engine |
| FAISS GPU 检索 | <0.3ms | GpuIndexIVFFlat, nprobe=64 |
| 余弦重排 Top-100 | <0.1ms | CUDA kernel |
| **总计** | **<3.6ms** | 余量 6.4ms |

### 优化栈

1. FP16 推理：OpenCLIP 默认 FP16
2. TensorRT 编译：ViT-B/16 + Projection Head 合并为单个 engine
3. FAISS GPU 索引：IndexIVFFlat 常驻 GPU 显存
4. Query 缓存：LRU Cache 10k 条（image perceptual hash 作为 key）

### 显存预算

| 组件 | 显存占用 |
|---|---|
| OpenCLIP ViT-B/16 (FP16) | ~170MB |
| Projection Head | <1MB |
| FAISS Index (1M × 512 × FP32) | ~2GB |
| 推理 workspace | ~500MB |
| **总计** | **~2.7GB** |

---

## 5. 准确率保障

### 训练侧

- Hard negative mining 每 epoch 更新
- 多粒度合成草图（从"接近边缘图"到"高度抽象手绘"渐进训练）
- 数据增强：随机视角偏移、局部遮挡、比例变化

### 检索侧

- 两阶段检索：FAISS 粗排 Top-100 → 余弦精排 Top-K
- 精排延迟预算：~0.1ms（100 个 512 维向量）

### Fallback 升级路径

| 阶段 | 触发条件 | 动作 |
|---|---|---|
| Level 1 | Recall@10 < 90% (合成) | 加 LoRA rank 16→32，延长训练 |
| Level 2 | 仍不达标 | 解冻 ViT 最后 2 层 fine-tune |
| Level 3 | 仍不达标 | 加域桥接层，三阶段渐进对齐 |
| Level 4 | 仍不达标 | 加 DINOv2 双路 |

每一级 fallback 增量升级，不需要重建 FAISS 索引。

---

## 6. 技术栈与项目边界

### 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.11+ | 生态最全 |
| 框架 | PyTorch 2.x | OpenCLIP 原生支持 |
| 预训练模型 | OpenCLIP ViT-B/16 (laion2b_s34b_b88k) | 开源最强 CLIP |
| 推理优化 | TensorRT 9.x + torch.compile | 5090 原生支持 |
| 向量检索 | FAISS 1.10+ (faiss-gpu) | GPU 原生 |
| CAD 转换 | Omniverse Kit CAD Converter | 免费，NVIDIA 生态 |
| 渲染 | Blender 4.x headless | 免费，批量渲染成熟 |
| 边缘检测 | HED + Canny fallback | HED 质量高 |
| 服务框架 | FastAPI | 轻量 async |
| 数据格式 | OpenUSD（中间格式） | 接轨国际路线 |

### 项目边界

**做**：草图→CAD 零件检索，1M 零件库，<10ms 延迟，预留文本扩展

**不做**：文本检索（本期）、CAD 生成/编辑、装配体级检索、分布式部署、前端 UI

### 技术风险

| 风险 | 缓解 |
|---|---|
| OpenCLIP 对工程草图理解弱 | LoRA 适配 + 4 级 fallback |
| 1M STEP→USD 转换失败率高 | 记录失败文件，OCP 直转 mesh 兜底 |
| ABC Dataset 下载/存储瓶颈 | 提前规划 ~2TB 存储 |
| 合成草图与真实草图分布差异 | 多粒度扰动 + 真实草图验证 |
| Blender 批量渲染 1M 模型耗时 | 并行渲染，预估 3-5 天 |
