# CAD-Retriever 系统设计

> 日期: 2026-05-13
> 状态: 设计完成，待实施

---

## 1. 系统架构总览

### 离线阶段（Index Building）

1. CAD 模型库中每个零件经过 B-Rep Transformer + 多视图 ViT 双路编码
2. 两路 embedding 通过可学习标量权重 α 做加权平均合并：`CAD_vec = α * brep_emb + (1-α) * mv_emb`，α 初始化 0.7（偏向 B-Rep）
3. 所有 CAD vector 存入 FAISS IndexIVFFlat，序列化到磁盘

### 在线阶段（Query & Retrieval）

1. 用户输入 text / sketch / 两者组合
2. 有文本 → Text Encoder 出 text embedding
3. 有图示 → Query Image Encoder (ViT) 出 image embedding
4. 双模态输入 → Cross-Attention 融合层产出 query vector；单模态 → 直接 projection
5. Query vector 送入 FAISS GPU 检索 Top-100
6. 余弦相似度精排 → 返回 Top-K 结果

### 关键设计决策

- 所有 embedding 统一到 512 维共享空间
- CAD 侧融合用 late fusion（离线计算，不受延迟约束）
- Query 侧融合用 cross-attention（文本约束图示的语义交互能力）
- 单模态 query 不经过 cross-attention，直接 projection，保证最低延迟
- 检索粒度：零件级（单个 part，非装配体）
- Query 类型：纯文本、纯图示、文本+图示任意组合

---

## 2. 各 Encoder 详细设计

### 2.1 B-Rep Transformer Encoder

- **输入**: B-Rep 元素序列化后的 token 序列（采用前人效果较好的序列化方案，如 BrepGPT 的 face-edge 交替序列化）
- **架构**: 6 层 Transformer Encoder，hidden dim 512，8 heads
- **Positional Encoding**: 拓扑感知 PE——用 B-Rep 邻接矩阵生成相对位置偏置（类似 GraphFormer）
- **输出**: [CLS] token → projection head → 512 维 CAD embedding
- **序列长度上限**: 256 tokens（覆盖绝大多数机械零件，超长截断）

### 2.2 多视图 ViT（CAD 辅助路径）

- **输入**: CAD 模型 6 个标准视角渲染图（前/后/左/右/上/下），224×224
- **架构**: CLIP ViT-B/16，冻结主体，只训练最后 2 层 + projection head
- **多视图聚合**: 6 张图各自出 embedding 后 mean pooling → 512 维
- **作用**: 补充 B-Rep encoder 在视觉外观语义上的不足

### 2.3 Text Encoder

- **架构**: Long-CLIP 文本塔（12 层 Causal Transformer，248 token 上限）
- **训练策略**: 冻结主体 + LoRA (rank=16) 适配 CAD 专业词汇
- **输出**: [EoT] position → projection head → 512 维
- **推理版本**: 蒸馏到 TinyBERT-4L → TensorRT INT8

### 2.4 Query Image Encoder

- **架构**: CLIP ViT-B/16（与多视图 ViT 共享预训练权重，独立 fine-tune）
- **输入**: 单张图像 224×224（用户上传的草图/工程图/渲染截图）
- **训练**: 全量 fine-tune（草图与自然图像差异大）
- **输出**: [CLS] → projection head → 512 维

### 2.5 Cross-Attention 融合层

- **结构**: 2 层 cross-attention（text tokens 为 Q，image tokens 为 KV）+ 1 层 self-attention
- **输出**: 融合后的 [CLS] → 512 维 query vector
- **单模态 fallback**: 只有文本时跳过此层；只有图示时跳过此层

---

## 3. 训练策略

### Phase 1: 基础对齐训练

- **目标**: CAD embedding 与 Text embedding 在同一空间对齐
- **Loss**: InfoNCE 对比损失，双向（CAD→Text + Text→CAD）
- **数据**: ABC Dataset 1M 模型 + LLM 生成文本描述（5 条/模型）
- **Batch size**: 2048（gradient cache，实际 GPU batch 256，累积 8 步）
- **温度 τ**: 可学习参数，初始化 0.07
- **冻结策略**: Text Encoder 冻结+LoRA；B-Rep Transformer 全量训练；多视图 ViT 冻结底层训练顶 2 层
- **训练时长**: ~3-5 天（单卡 5090）

### Phase 2: Query Image Encoder 对齐

- **目标**: 草图/工程图/渲染图映射到同一空间
- **数据来源**:
  - 渲染图：从 CAD 模型直接渲染（天然配对）
  - 工程图：从 CAD 自动导出三视图（天然配对）
  - 草图：edge detection + 随机扰动模拟手绘风格（合成数据）
- **Loss**: Image→CAD 对比损失（复用 Phase 1 的 CAD embedding 作为 anchor）
- **训练时长**: ~1-2 天

### Phase 3: Cross-Attention 融合训练

- **目标**: 训练融合层，让 text+image 组合 query 优于单模态
- **数据**: 三元组（text, sketch, CAD）
- **Loss**: 融合 query→CAD InfoNCE + 单模态 query→CAD InfoNCE（联合训练，防止退化为单模态依赖）
- **训练时长**: ~1 天

### Phase 4: 知识蒸馏

- **Teacher**: Phase 1-3 完整 Text Encoder（12 层）
- **Student**: TinyBERT-4L（4 层，14M 参数）
- **蒸馏方式**: 中间层对齐（student 4 层对应 teacher 1/4/8/12 层）+ embedding MSE
- **验证**: Recall@10 下降不超过 2%，否则改用 6 层

### Hard Negative Mining

- 几何相似但语义不同：同类零件不同规格（M6 vs M8 螺栓）
- 语义相似但几何不同：同功能不同实现（焊接法兰 vs 螺栓法兰）
- 挖掘方式：每 epoch 结束用当前模型检索 Top-50，取 rank 10-30 作为下轮 hard negative

---

## 4. 推理优化与部署

### 硬件: RTX 5090（32GB VRAM）

### 延迟预算（双模态 query，最严格场景）

| 阶段 | 目标延迟 | 优化手段 |
|------|---------|---------|
| Text Encoder | <2ms | TinyBERT-4L + TensorRT INT8 |
| Query Image Encoder | <3ms | ViT-B/16 + TensorRT FP16 |
| Cross-Attention 融合 | <1ms | TensorRT FP16，2+1 层 |
| FAISS 检索 | <2ms | GPU IndexIVFFlat，nprobe=64 |
| 余弦重排 Top-100 | <0.5ms | CUDA kernel |
| **总计** | **<8.5ms** | 余量 1.5ms |

### 单模态延迟

- 纯文本: ~4ms
- 纯图示: ~5ms

### 优化栈（按实施顺序）

1. FP16 推理：所有模型默认 FP16
2. TensorRT 编译：ONNX → TensorRT engine，层融合 + kernel 调优
3. INT8 量化：仅 Text Encoder（蒸馏后 TinyBERT，对量化最鲁棒）
4. FAISS GPU 索引：IndexIVFFlat 加载到 GPU 显存
5. Query 缓存：LRU Cache 10k 条，预期命中率 30-40%
6. Dynamic Batching：并发 query 聚合 batch 推理

### 显存预算

| 组件 | 显存占用 |
|------|---------|
| Text Encoder (INT8) | ~30MB |
| Image Encoder (FP16) | ~170MB |
| Cross-Attention (FP16) | ~50MB |
| FAISS Index (1M × 512 × FP32) | ~2GB |
| 推理 workspace | ~1GB |
| **总计** | **~3.3GB** |

### 消融 Fallback

- Cross-attention 延迟超标 → 退化为 late fusion（加权平均）
- Image Encoder 延迟超标 → 降分辨率 224→160 或换 ViT-S/16
- 总延迟仍超 10ms → Text Encoder 压缩到 2 层

---

## 5. 数据管线与评估

### 训练数据准备

```
ABC Dataset (1M STEP files)
  → 解析 B-Rep 拓扑 → 序列化为 token 序列
  → 渲染 6 视角图像 (224×224)
  → 导出三视图工程图
  → Edge detection + 扰动 → 合成草图
  → LLM 生成文本描述 (5条/模型)

Fusion 360 Gallery (8k)
  → 同上 + 利用自带设计意图元数据作为高质量文本
```

### LLM 标注策略

输入给 LLM：6 视角渲染图 + B-Rep 元数据（face 数量、edge 类型、包围盒尺寸）

生成 5 条不同粒度描述：
1. 一句话概括（"带法兰的圆柱管接头"）
2. 几何特征描述（"圆柱体主体，顶部 6 孔均布法兰盘，底部外螺纹"）
3. 功能/用途描述（"管道系统连接件，承受中等压力"）
4. 工艺描述（"车削加工，法兰面铣削，螺纹滚压成型"）
5. 组合描述（混合以上要素的自然语言段落）

### 评估方案

**测试集**:
- ABC 中随机抽取 5000 零件作为测试库
- 人工标注 500 条 query-CAD 配对（覆盖纯文本、纯草图、混合 query）
- 每条 query 标注 1 正确 + 3-5 相关结果

**指标**:

| 指标 | 目标值 | 含义 |
|------|--------|------|
| Recall@1 | >60% | Top-1 命中 |
| Recall@10 | >90% | Top-10 包含正确结果 |
| MRR | >0.7 | 平均倒数排名 |
| P99 延迟 | <10ms | 99 分位端到端延迟 |
| QPS (batch=1) | >100 | 单条吞吐 |
| QPS (batch=32) | >1000 | 批量吞吐 |

### 消融实验矩阵

- B-Rep only vs 多视图 only vs 双路融合
- 纯文本 vs 纯图示 vs cross-attention 融合
- 12 层 Text Encoder vs 4 层蒸馏版

---

## 6. 项目约束与边界

### 硬约束

- 端到端延迟 <10ms（RTX 5090）
- 数据库规模 1M CAD 零件
- 支持三种 query 模式：纯文本、纯图示、混合

### 非目标

- 不做 CAD 生成/编辑
- 不做装配体级检索（仅零件级）
- 不在 tokenization 上做创新（复用前人方案）
- 不做分布式部署（单机单卡）

### 技术风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| B-Rep Transformer 训练不稳定 | 主路径失效 | 多视图路径兜底 |
| Cross-attention 延迟超标 | 无法满足 <10ms | 退化为 late fusion |
| LLM 标注质量差 | 对齐效果差 | 多粒度生成 + 抽检 |
| 5090 TensorRT 生态不成熟 | 部署延迟 | 回退 FP16 |
| 草图合成数据与真实草图分布差异大 | 草图检索效果差 | 收集少量真实草图 fine-tune |
