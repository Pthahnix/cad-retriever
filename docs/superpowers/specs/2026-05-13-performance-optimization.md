# CAD-Retriever 性能优化全面分析

> 日期: 2026-05-13
> 硬约束: 端到端 <10ms，RTX 5090 单卡

---

## 1. 延迟瓶颈分解

### 当前架构各环节延迟估算（RTX 5090，未优化 baseline）

| 环节 | PyTorch FP32 | 占比 | 瓶颈原因 |
|------|-------------|------|---------|
| Text Encoder (Long-CLIP 12L) | ~15ms | 38% | 12 层 Transformer，序列长度 248 |
| Query Image Encoder (ViT-B/16) | ~12ms | 30% | 197 patch tokens，12 层 |
| Cross-Attention 融合 (3L) | ~4ms | 10% | 跨模态 token 交互 |
| FAISS 检索 (CPU IVFFlat) | ~5ms | 13% | CPU 计算 + 数据搬运 |
| 余弦重排 Top-100 | ~2ms | 5% | 未优化的 Python 循环 |
| 数据预处理 + 后处理 | ~2ms | 5% | tokenize + 图像 resize |
| **总计（未优化）** | **~40ms** | 100% | 超标 4× |

**结论**: 未优化状态下超标 4 倍，需要全栈优化才能达标。

---

## 2. 优化路线图（按收益排序）

### Level 1: 模型压缩（收益最大，~8× 加速）

#### Text Encoder 蒸馏

| 方案 | 参数量 | 相对速度 | 精度保留 | 推荐 |
|------|--------|---------|---------|------|
| Long-CLIP 12L (baseline) | 63M | 1× | 100% | 训练用 |
| DistilCLIP 6L | ~33M | 2× | ~97% | 备选 |
| TinyBERT-4L 蒸馏 | 14M | 7.5× | ~96% | **首选** |
| TinyBERT-2L 极限压缩 | 7M | 15× | ~92% | fallback |

**蒸馏策略**:
- 中间层对齐: student 4 层 → teacher 1/4/8/12 层的 hidden state MSE
- Embedding 对齐: 最终 512 维 embedding 的余弦相似度损失
- 验证门槛: Recall@10 下降 >2% 则回退到 6 层

**预期延迟**: TinyBERT-4L FP32 在 5090 上 ~2ms

#### Query Image Encoder 轻量化

| 方案 | 参数量 | 延迟 (FP32) | 精度 | 推荐 |
|------|--------|------------|------|------|
| ViT-B/16 (baseline) | 86M | ~12ms | 100% | 训练用 |
| ViT-S/16 | 22M | ~4ms | ~95% | 备选 |
| EfficientViT-M5 | 12M | ~2ms | ~92% | 极限场景 |
| ViT-B/16 + TensorRT | 86M | ~3ms | ~100% | **首选** |

**决策**: 优先用 TensorRT 编译 ViT-B/16（保精度），如果仍超标再换 ViT-S/16。

---

### Level 2: 推理引擎优化（~3× 加速）

#### TensorRT 编译

RTX 5090 (Blackwell) 支持的精度格式:
- FP32 → FP16: 2× 加速，精度无损
- FP16 → INT8: 额外 1.5-2× 加速，需要校准
- FP16 → FP8 (Blackwell 新增): 与 INT8 速度相当，精度更高

**各组件 TensorRT 编译后预期延迟**:

| 组件 | 精度 | 预期延迟 | 依据 |
|------|------|---------|------|
| TinyBERT-4L | INT8 | **<0.3ms** | NVIDIA 官方: BERT-Large INT8 = 1.2ms (A100)，4L 模型在更快的 5090 上 |
| ViT-B/16 | FP16 | **~2ms** | TRT-ViT 论文: ViT-B/16 在 T4 上 ~5ms FP16，5090 约 2.5× 快于 T4 |
| Cross-Attention 3L | FP16 | **<0.5ms** | 仅 3 层，参数量极小 |

**编译流程**:
```
PyTorch model → torch.onnx.export() → ONNX → trtexec → TensorRT Engine
                                              ↓
                                    INT8 校准 (需要 1000 条样本)
```

**5090 特有优化**:
- FP8 推理: Blackwell Tensor Core 原生支持，比 INT8 精度更高
- Sparsity 2:4: 结构化稀疏，额外 ~1.5× 加速（需要稀疏训练）
- TensorRT 9.x JIT 编译: 首次编译 <5s，后续直接加载 engine

---

### Level 3: 检索引擎优化

#### FAISS GPU + cuVS (CAGRA)

FAISS 1.10.0 集成了 NVIDIA cuVS，新增 CAGRA 索引（专为 GPU 设计的图索引）:

| 索引类型 | 1M 延迟 (GPU) | 召回率 | 显存 | 推荐场景 |
|---------|--------------|--------|------|---------|
| GpuIndexFlatIP | ~0.5ms | 100% | 2GB | 验证阶段 |
| GpuIndexIVFFlat (nprobe=64) | ~0.3ms | ~95% | 2GB | **生产首选** |
| GpuIndexCagra | ~0.1ms | ~98% | 3GB | 极限延迟 |
| GpuIndexIVFPQ | ~0.1ms | ~85% | 200MB | 内存受限 |

**推荐**: GpuIndexIVFFlat 作为默认，CAGRA 作为升级选项。

**关键配置**:
```python
import faiss

res = faiss.StandardGpuResources()
res.setTempMemory(256 * 1024 * 1024)  # 256MB scratch space

# 构建索引
nlist = 1024  # 聚类中心数（sqrt(1M) ≈ 1000）
index_cpu = faiss.IndexIVFFlat(
    faiss.IndexFlatIP(512), 512, nlist, faiss.METRIC_INNER_PRODUCT
)
index_cpu.train(training_vectors)
index_cpu.add(all_vectors)

# 迁移到 GPU
index_gpu = faiss.index_cpu_to_gpu(res, 0, index_cpu)
index_gpu.nprobe = 64  # 搜索 64 个聚类
```

---

### Level 4: 系统工程优化

#### 4.1 Query Embedding 缓存

```
策略: LRU Cache，容量 10k 条
命中时: 跳过 encoder 推理，直接进 FAISS（延迟 <1ms）
预期命中率: 30-40%（工业检索场景实测数据）
实现: Python lru_cache 或 Redis（如需持久化）
```

**缓存 key 设计**:
- 纯文本: text hash
- 纯图示: image perceptual hash (pHash)
- 混合: text_hash + image_pHash 拼接

#### 4.2 Dynamic Batching

```
场景: 多用户并发查询
策略: 收集 N ms 内的请求，聚合成 batch 推理
参数: max_batch=32, max_wait=2ms
收益: GPU 利用率 20% → 80%+，QPS 提升 5-10×
```

#### 4.3 异步流水线

```
阶段 A (Text Encode) 和阶段 B (Image Encode) 可并行:

Timeline (双模态 query):
  t=0ms   ┌─ Text Encoder ──────┐ (0.3ms)
           └─ Image Encoder ─────┘ (2ms)
  t=2ms   ── Cross-Attention ──── (0.5ms)
  t=2.5ms ── FAISS Search ─────── (0.3ms)
  t=2.8ms ── Rerank ──────────── (0.2ms)
  t=3ms   → 返回结果

实际端到端: ~3ms（双模态），~1ms（纯文本）
```

**关键**: Text Encoder 和 Image Encoder 用不同 CUDA stream 并行执行。

#### 4.4 预处理优化

| 操作 | 当前 | 优化后 | 手段 |
|------|------|--------|------|
| Text tokenize | ~1ms (CPU) | ~0.1ms | Rust tokenizer (tokenizers 库) |
| Image resize | ~2ms (CPU) | ~0.1ms | GPU resize (torchvision CUDA) |
| Image normalize | ~0.5ms (CPU) | 0ms | 融入 TensorRT engine 首层 |

---

## 3. 优化后延迟预算（最终目标）

### 场景 A: 纯文本 Query（最快）

| 环节 | 延迟 |
|------|------|
| Tokenize (Rust) | 0.1ms |
| TinyBERT-4L (TensorRT INT8) | 0.3ms |
| FAISS GPU (IVFFlat) | 0.3ms |
| Rerank (CUDA) | 0.1ms |
| **总计** | **~0.8ms** |

### 场景 B: 纯图示 Query

| 环节 | 延迟 |
|------|------|
| Image preprocess (GPU) | 0.1ms |
| ViT-B/16 (TensorRT FP16) | 2.0ms |
| FAISS GPU (IVFFlat) | 0.3ms |
| Rerank (CUDA) | 0.1ms |
| **总计** | **~2.5ms** |

### 场景 C: 双模态 Query（最严格）

| 环节 | 延迟 |
|------|------|
| Preprocess (并行) | 0.1ms |
| Text Encoder ∥ Image Encoder (并行) | 2.0ms (取 max) |
| Cross-Attention (TensorRT FP16) | 0.5ms |
| FAISS GPU (IVFFlat) | 0.3ms |
| Rerank (CUDA) | 0.1ms |
| **总计** | **~3.0ms** |

**结论**: 全栈优化后，即使最严格的双模态场景也只需 ~3ms，远低于 10ms 硬约束。余量 7ms 可以容纳网络开销、序列化、以及未预见的延迟抖动。

---

## 4. 优化实施优先级

| 优先级 | 优化项 | 预期收益 | 实施难度 | 依赖 |
|--------|--------|---------|---------|------|
| P0 | TensorRT FP16 编译全部模型 | 3-5× | 低 | ONNX export |
| P0 | FAISS GPU 索引 | 10× vs CPU | 低 | faiss-gpu 安装 |
| P1 | Text Encoder 蒸馏 (4L) | 7.5× | 中 | 训练完成后 |
| P1 | Text/Image encoder 并行 (CUDA streams) | 2× (双模态) | 中 | 推理框架 |
| P2 | INT8 量化 (Text Encoder) | 额外 1.5× | 低 | 校准数据 |
| P2 | Query 缓存 | 命中时 ~0ms | 低 | 无 |
| P3 | FP8 推理 (5090 Blackwell) | 与 INT8 同速更高精度 | 中 | TensorRT 9.x |
| P3 | CAGRA 索引替换 IVFFlat | 3× 检索加速 | 低 | FAISS 1.10+ |
| P3 | Dynamic Batching | QPS 5-10× | 中 | 服务框架 |

---

## 5. 风险与 Fallback 矩阵

| 风险 | 触发条件 | Fallback |
|------|---------|---------|
| Cross-attention 延迟超标 | TensorRT 编译后仍 >2ms | 退化为 late fusion（加权平均） |
| ViT-B/16 延迟超标 | TensorRT FP16 后仍 >3ms | 换 ViT-S/16（22M 参数） |
| TinyBERT 精度损失过大 | Recall@10 下降 >3% | 回退到 6 层蒸馏 |
| 5090 TensorRT FP8 不成熟 | 编译失败或精度异常 | 使用 FP16 + INT8 组合 |
| FAISS GPU 显存不足 | 索引 + 模型超 32GB | 索引留 CPU，用 IVFFlat nprobe=32 |

---

## 6. Benchmark 验证计划

### 阶段性验证点

1. **Baseline 测量** (训练完成后立即):
   - 全模型 PyTorch FP32 端到端延迟
   - 各环节独立延迟 profiling (torch.cuda.Event)

2. **TensorRT 编译后**:
   - 各 engine 独立延迟
   - 精度对比 (embedding 余弦相似度 vs PyTorch 输出)

3. **蒸馏后**:
   - TinyBERT-4L vs 原始 12L 的 Recall@K 对比
   - 蒸馏模型 TensorRT 延迟

4. **全栈集成后**:
   - 端到端 P50/P95/P99 延迟
   - QPS (batch=1 和 batch=32)
   - 显存占用峰值

### 测量工具

```python
# CUDA event 精确计时
start = torch.cuda.Event(enable_timing=True)
end = torch.cuda.Event(enable_timing=True)

start.record()
# ... inference ...
end.record()
torch.cuda.synchronize()
latency_ms = start.elapsed_time(end)
```

---

## 7. 关键技术选型总结

| 组件 | 选型 | 理由 |
|------|------|------|
| 推理引擎 | TensorRT 9.x | 5090 原生支持，层融合最优 |
| 精度格式 | FP8 (首选) / INT8 (fallback) | Blackwell 原生 FP8，精度优于 INT8 |
| 向量检索 | FAISS 1.10 + cuVS | GPU 原生，CAGRA 索引最快 |
| 服务框架 | Triton Inference Server | 原生 TensorRT 集成，dynamic batching 内置 |
| Tokenizer | HuggingFace tokenizers (Rust) | 比 Python 快 10× |
| 图像预处理 | torchvision CUDA ops | 避免 CPU-GPU 数据搬运 |
