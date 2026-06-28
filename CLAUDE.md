# CAD Retriever — 工作进展与待办

> 此文件是会话间的进展交接。最新进展置顶。

## 当前状态（截至 2026-06-27）

- **分支**：`spec/cad-retriever-system-design`（已从 main 切出）
- **关键产物**：`docs/superpowers/specs/2026-06-27-cad-retriever-system-design.md`（commit `3aea88d`，497 行，11 章）—— 全流程系统设计 spec
- **流程位置**：brainstorming 已完成 spec 自审 → 卡在**用户评审门**，尚未进入 writing-plans

## 今天做了什么

1. **回忆并重建项目上下文**：读完 `context/history`（原 OpenCLIP 方案 + 失败复盘）、当前 `docs/`、download-probe 设计。
2. **盘清 Gitee `model-retrieval` 仓库**（治克隆到 /tmp 通读源码）：确认它不是"数据集"，而是一套完整可跑的**双分支 sketch→CAD 实例检索代码**。关键事实：`ABC_V2` = ABC chunk1 去重后 **~8,422 模型**，12 视图（顶6底6），PhotoSketch 产草图，可选 B-rep GNN，域对抗。
3. **项目转向定调**：以 Gitee 这套 CNN 方法为新主线，原 OpenCLIP 降为可选对比臂；"数据合成"步缩减为"缺什么补什么"。
4. **三方辩论定主干策略**（CNN拥护/ViT拥护/中立 三个 subagent）：~8.4K 量级是支点，结论 = **不预设主干，消融驱动**。CNN双分支+域对抗=默认基线，B-rep几何(BOTH)=最值得验证上行项，CLIP-ViT+LoRA=风险臂（须过坍缩探针门）。
5. **部署形态定案**（GPT-5.5 + CC subagent 双人小组，~0.8 收敛）：Python→ONNX→Rust(axum)+暴力点积检索+Astro，FastAPI 为回退逃生舱。
6. **写完 + 自审 + 提交 spec**。

## 明天要干的事（按顺序）

1. **等用户评审 spec**（若已反馈，先处理修改意见，再重跑自审）。待确认的 3 点：
   - 文件名后缀（现为 `-system-design.md`，流程默认 `-design.md`）
   - Top-1/Top-10 阈值是否要补方向性下限（现为"实测基线+决策规则"留白）
   - §8.3 演示物上线段是否降级为备注
2. **用户批准后 → 调 `writing-plans` 技能**把 spec 拆成可执行实现 plan。
   - 直接用 spec **§11 单元边界表**做拆分依据（download/probe/render/sketch/graph/train/build-artifact/serve/frontend 九个单元）。
   - 关键路径：M0环境对齐 → M1数据落地 → M2 B-rep图补全 → M3消融决策 → M4建库 → M5服务 → M6前端。
3. **M0 优先验证三个已知风险点**（写进 plan 的第一批任务）：PyG↔torch2.8 兼容、faiss-gpu、`ort`↔CUDA12.8(5090) 打包。

## 重要约束 / 备忘

- **不要预设魔法数阈值**（用户明确要求）——阈值由数据/消融定。
- **codex CLI 不可用**：API key 属 "Codex-Pro" 分组，`/v1/responses` 被 403；但 GPT-5.5 可经 `/v1/chat/completions` 调用（helper 模式见 memory `gpt55-api-access`）。多智能体讨论 = CC subagent + GPT-5.5 curl。
- **数据落盘**写 GPU 机大盘（历史 `~/data`），禁止写仓库目录/`/tmp`。
- 详细背景见 memory：`gitee-model-retrieval`、`project-pivot-2026-06`、`deploy-stack-decision`、`gpt55-api-access`。

## 下一步在哪继续

回到 brainstorming 流程的"用户评审门"。用户说"可以"即进入 `writing-plans`；否则按反馈改 spec。
