# CAD-Retriever 项目概览与技术决策

> 创建: 2026-05-13 | 状态: 设计完成
> 详细 spec: `docs/superpowers/specs/2026-05-13-cad-retriever-design.md`
> 性能分析: `docs/superpowers/specs/2026-05-13-performance-optimization.md`

---

## 一、项目定位

**CAD-Retriever** 是一个跨模态 CAD 零件检索系统。用户输入自然语言描述、手绘草图、工程视图，或它们的任意组合，系统从百万级 CAD 模型库中实时返回语义最匹配的零件。

**核心价值**: 将"找零件"从人工翻阅目录（分钟级）变为语义检索（毫秒级）。

**非目标**: 不做 CAD 生成/编辑、不做装配体检索、不做分布式部署。

---

## 二、系统架构

### 整体范式: CLIP 对比学习 + FAISS 向量检索

```
┌─────────────────── 离线（Index Building）───────────────────┐
│                                                              │
│  CAD 零件 ─┬─→ B-Rep Transformer ──┐                        │
│            │                        ├─ Late Fusion ─→ FAISS  │
│            └─→ 多视图 ViT ─────────┘   (α=0.7)     Index   │
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌─────────────────── 在线（Query & Retrieval）─────────────────┐
│                                                              │
│  用户输入 ─┬─ 文本 ─→ Text Encoder ────┐                     │
│           │                            ├─ Cross-Attention    │
│           └─ 图示 ─→ Image Encoder ───┘   Fusion            │
│                                            │                 │
│                                       Query Vector           │
│                                            │                 │
│                              FAISS Top-100 → Rerank → Top-K  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 架构核心决策

| 决策点 | 选择 | 为什么 |
|--------|------|--------|
| CAD 侧融合 | Late fusion (加权平均) | 离线计算，不受延迟约束，简单可靠 |
| Query 侧融合 | Cross-attention | 文本可以约束图示语义（"这个形状，但要三个孔"） |
| 单模态处理 | 跳过融合层，直接 projection | 保证最低延迟路径 |
| Embedding 维度 | 512 维统一空间 | 平衡表达力与检索效率 |
| 检索粒度 | 零件级 | 工程实际需求，装配体太粗、特征级太细 |

---

## 三、Encoder 设计

### 3.1 B-Rep Transformer（CAD 主路径）

- 6 层 Transformer Encoder，hidden 512，8 heads
- 输入: B-Rep 元素序列化 token（face-edge 交替，采用前人成熟方案）
- 拓扑感知: 邻接矩阵生成相对位置偏置（GraphFormer 思路）
- 序列上限 256 tokens，[CLS] → projection → 512 维

**为什么选 Transformer 而非 GNN**:
1. 与 CLIP 文本塔架构对称，训练对齐更自然
2. 固定长度序列易于 batch 化，GPU 利用率高
3. 全局注意力捕获长距离拓扑依赖
4. 推理时复用 TensorRT Transformer 优化栈

### 3.2 多视图 ViT（CAD 辅助路径）

- CLIP ViT-B/16，冻结主体，训练顶 2 层 + projection
- 6 视角渲染（前/后/左/右/上/下），mean pooling → 512 维
- 作用: 补充 B-Rep 在视觉外观语义上的不足

### 3.3 Text Encoder

- Long-CLIP 文本塔（248 token，解决原始 CLIP 77 token 限制）
- 冻结主体 + LoRA rank=16 适配 CAD 专业词汇
- 推理版本: 蒸馏到 TinyBERT-4L（14M 参数，7.5× 加速）

**为什么用 Long-CLIP 而非原始 CLIP**:
CAD 描述天然较长（材料、公差、工艺、功能），77 token 严重截断信息。Long-CLIP 扩展到 248 token，检索 recall 提升约 20%。

### 3.4 Query Image Encoder

- CLIP ViT-B/16，全量 fine-tune
- 统一处理三种图示: 手绘草图、工程视图、渲染截图
- 一个 encoder 通吃，靠训练数据多样性覆盖差异

**为什么不分三个 encoder**:
工程复杂度 3×，但收益有限。CLIP ViT 预训练已见过各种风格图像，fine-tune 足以适配。

### 3.5 Cross-Attention 融合层

- 2 层 cross-attention（text tokens 为 Q，image tokens 为 KV）+ 1 层 self-attention
- 输出: 融合 [CLS] → 512 维 query vector
- 单模态时完全跳过，零开销

---

## 四、训练策略

### 四阶段训练流程

```
Phase 1 (3-5天)     Phase 2 (1-2天)     Phase 3 (1天)      Phase 4 (0.5天)
基础对齐训练    →    图示 Encoder    →    融合层训练    →    知识蒸馏
CAD↔Text 对齐       Image→CAD 对齐      Cross-Attn        12L→4L
```

### 关键训练决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Loss | InfoNCE 双向对比 | CLIP 范式标准，成熟可靠 |
| Batch size | 2048 (gradient cache) | 对比学习强依赖大 batch 负样本 |
| 温度 τ | 可学习，初始 0.07 | 自适应调整比固定值效果好 |
| Hard Negative | 每 epoch 挖掘 rank 10-30 | 几何相似但语义不同的样本最有价值 |
| 文本标注 | LLM 自动生成 5 条/模型 | 1M 规模人工标注不现实 |
| 草图数据 | Edge detection + 随机扰动合成 | 真实草图稀缺，合成数据兜底 |

### LLM 标注的五个粒度

1. 一句话概括 — "带法兰的圆柱管接头"
2. 几何特征 — "圆柱体主体，顶部 6 孔均布法兰盘"
3. 功能用途 — "管道系统连接件，承受中等压力"
4. 工艺描述 — "车削加工，法兰面铣削"
5. 组合段落 — 混合以上要素的自然语言

---

## 五、性能目标与优化路线

### 硬约束

| 指标 | 目标 |
|------|------|
| 端到端延迟 | <10ms (P99) |
| 数据库规模 | 1M CAD 零件 |
| 部署硬件 | RTX 5090 单卡 (32GB) |
| 显存占用 | <4GB（余量留给扩展） |

### 延迟从 40ms 压到 3ms 的路径

未优化 baseline 约 40ms，超标 4×。通过四层优化压缩到 ~3ms：

```
40ms (PyTorch FP32)
  │
  ├─ Level 1: 模型蒸馏 ──────────→ ~8ms  (Text 12L→4L = 7.5×)
  │
  ├─ Level 2: TensorRT 编译 ─────→ ~4ms  (层融合 + FP16/INT8)
  │
  ├─ Level 3: FAISS GPU ─────────→ ~3.5ms (CPU→GPU = 10×)
  │
  └─ Level 4: 并行 + 缓存 ──────→ ~3ms  (Text∥Image 并行)
```

### 优化后各场景延迟

| 场景 | 延迟 | 余量 |
|------|------|------|
| 纯文本 Query | ~0.8ms | 9.2ms |
| 纯图示 Query | ~2.5ms | 7.5ms |
| 双模态 Query（最严格） | ~3.0ms | 7.0ms |

### 关键优化技术

| 技术 | 作用于 | 收益 | 优先级 |
|------|--------|------|--------|
| TensorRT FP16 编译 | 全部模型 | 3-5× 加速 | P0 |
| FAISS GPU (cuVS) | 检索引擎 | 10× vs CPU | P0 |
| TinyBERT-4L 蒸馏 | Text Encoder | 7.5× 加速 | P1 |
| CUDA Stream 并行 | Text∥Image | 双模态 2× | P1 |
| INT8/FP8 量化 | Text Encoder | 额外 1.5× | P2 |
| Query LRU 缓存 | 热点查询 | 命中时 ~0ms | P2 |
| CAGRA 图索引 | FAISS | 3× 检索加速 | P3 |
| Triton + Dynamic Batching | 服务层 | QPS 5-10× | P3 |

### 5090 Blackwell 特有能力

- **FP8 Tensor Core**: 比 INT8 精度更高，速度相当——优先于 INT8 使用
- **Sparsity 2:4**: 结构化稀疏额外 1.5× 加速（需稀疏训练）
- **32GB VRAM**: 模型+索引仅占 ~3.3GB，余量充足

---

## 六、显存预算

| 组件 | 占用 |
|------|------|
| Text Encoder (INT8) | ~30MB |
| Image Encoder (FP16) | ~170MB |
| Cross-Attention (FP16) | ~50MB |
| B-Rep Transformer (离线，不常驻) | — |
| FAISS Index (1M × 512 × FP32) | ~2GB |
| 推理 workspace | ~1GB |
| **总计** | **~3.3GB / 32GB** |

---

## 七、数据规划

| 数据集 | 规模 | 用途 |
|--------|------|------|
| ABC Dataset | 1M+ 机械零件 | 通用 CAD embedding 预训练 |
| Fusion 360 Gallery | ~8k 设计序列 | 高质量样本（自带设计意图） |
| 私有数据 | 部署时接入 | 实际使用，embedding 链路直接迁移 |

**数据准备流水线**:
```
STEP 文件 → B-Rep 解析 → Token 序列化
         → 6 视角渲染 (224×224)
         → 三视图导出
         → Edge detection → 合成草图
         → LLM 生成 5 条文本描述
```

---

## 八、评估体系

| 指标 | 目标值 | 含义 |
|------|--------|------|
| Recall@1 | >60% | Top-1 命中正确结果 |
| Recall@10 | >90% | Top-10 包含正确结果 |
| MRR | >0.7 | 平均倒数排名 |
| P99 延迟 | <10ms | 99 分位端到端 |
| QPS (batch=1) | >100 | 单条吞吐 |
| QPS (batch=32) | >1000 | 批量吞吐 |

**消融实验矩阵**:
- B-Rep only vs 多视图 only vs 双路融合 → 验证双路增益
- 纯文本 vs 纯图示 vs cross-attention 融合 → 验证融合增益
- 12 层 vs 4 层蒸馏 → 验证蒸馏精度损失

---

## 九、风险与 Fallback

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| B-Rep Transformer 训练不稳定 | 主路径失效 | 多视图路径兜底，系统仍可用 |
| Cross-attention 延迟超标 | 双模态超 10ms | 退化为 late fusion（加权平均） |
| ViT-B/16 延迟超标 | 图示检索超标 | 换 ViT-S/16 (22M) 或降分辨率 |
| TinyBERT 精度损失过大 | Recall 下降 >3% | 回退到 6 层蒸馏 |
| LLM 标注质量差 | 对齐效果差 | 多粒度生成 + 人工抽检 |
| 5090 TensorRT FP8 不成熟 | 编译失败 | 回退 FP16 + INT8 组合 |
| 草图合成数据分布偏差 | 草图检索差 | 收集少量真实草图 fine-tune |

---

## 十、技术选型总览

| 层级 | 选型 | 理由 |
|------|------|------|
| CAD 编码 | B-Rep Transformer + 多视图 ViT | 原生拓扑 + 视觉语义互补 |
| 文本编码 | Long-CLIP → TinyBERT-4L 蒸馏 | 长文本支持 + 极致推理速度 |
| 图示编码 | CLIP ViT-B/16 统一 encoder | 简洁，一个模型覆盖三种图示 |
| 跨模态融合 | Cross-Attention (2CA+1SA) | 文本约束图示的语义交互 |
| 对比学习 | InfoNCE + Hard Negative Mining | CLIP 范式标准 + 精度提升关键手段 |
| 向量检索 | FAISS 1.10 GPU (IVFFlat/CAGRA) | 算法效率天花板，1M 规模 <0.3ms |
| 推理引擎 | TensorRT 9.x (FP8/INT8) | 5090 原生支持，层融合最优 |
| 服务框架 | Triton Inference Server | TensorRT 原生集成 + dynamic batching |
| 文本预处理 | HuggingFace tokenizers (Rust) | 比 Python 快 10× |
| 图像预处理 | torchvision CUDA ops | 全 GPU 流水线，零 CPU 瓶颈 |
