# 03 - Transformer 与深度学习面试题

> 覆盖 Transformer、注意力机制、深度学习在推荐中的应用。

---

## Q1: Self-Attention 的计算复杂度是多少？如何优化？⭐⭐

**标准答案：**
$O(n^2 \cdot d)$，其中 $n$ 是序列长度，$d$ 是维度。

优化方向：
- **Grouped Query Attention (GQA)**：x-algorithm 使用，KV 头数少于 Q 头数
- **Flash Attention**：IO-aware 的注意力计算
- **稀疏注意力**：只计算部分位置对

---

## Q2: 解释 Grouped Query Attention (GQA) 的原理 ⭐⭐⭐

**标准答案：**

| 方案 | Q 头 | KV 头 | KV 缓存 |
|------|------|-------|---------|
| MHA | 32 | 32 | 100% |
| GQA | 32 | 8 | **25%** |
| MQA | 32 | 1 | 3.1% |

x-algorithm 使用 GQA，每 4 个 Q 头共享一对 KV。内存节省 75%，性能损失 <1%。

---

## Q3: RoPE 位置编码为什么比可学习位置编码好？⭐⭐

**标准答案：**
- 天然编码**相对位置**
- 可外推到训练时未见的序列长度
- 不需要额外参数
- x-algorithm 中行为序列长度变化大，RoPE 的外推能力很重要

---

## Q4: 什么是 Candidate Isolation？为什么重要？⭐⭐⭐

**标准答案：**
在注意力掩码中，候选帖子之间互不可见——每个候选只能看到用户上下文。

**重要性：** 评分独立于批次 → 可缓存 → 减少 30%+ 计算量。

---

## Q5: bfloat16 vs float16 vs float32 的区别？⭐⭐

| 类型 | 指数位 | 尾数位 | 范围 | 精度 |
|------|--------|--------|------|------|
| float32 | 8 | 23 | 大 | 高 |
| float16 | 5 | 10 | 小 | 中 |
| bfloat16 | 8 | 7 | 大 | 低 |

x-algorithm 选 bfloat16：保持 float32 的范围（防止溢出），推理速度提升 2-4x。

---

## Q6: RMSNorm vs LayerNorm？⭐

RMSNorm 去掉了均值偏移，只做缩放。计算更快，效果几乎相同。

---

## Q7: 门控 FFN (SiLU) 相比标准 ReLU FFN 的优势？⭐⭐

SiLU 门控 FFN = gate * value，gate 分支控制信息通行量。比 ReLU 更平滑，负值不完全截断。

---

## Q8: 什么是 Multi-Hash Embedding？⭐⭐

多个哈希函数将同一实体映射到多个嵌入桶，合并后投影到目标维度。冲突概率呈指数下降。

---

## Q9: Transformer 在推荐系统和 NLP 中的应用有何区别？⭐⭐⭐

| 维度 | NLP | 推荐 (x-algorithm) |
|------|-----|-------------------|
| 输入 | Token 序列 | 行为序列 + 候选 |
| 输出 | 下一个 Token | 19 种行为概率 |
| 掩码 | 因果 | 因果 + Candidate Isolation |
| 嵌入 | Token embedding | Multi-hash embedding |

---

## Q10: 损失函数选择——为什么用 BCE 而不是 CE？⭐⭐

19 种行为独立预测（可以同时点赞+回复），用 Binary Cross Entropy (sigmoid + BCE) 而非 Cross Entropy (softmax)。

---

## Q11-Q20: （简略标题）

**Q11:** 解释残差连接对深层 Transformer 训练的影响 ⭐
**Q12:** 什么是 KV Cache？在推荐推理中如何使用？⭐⭐
**Q13:** Transformer 的参数量怎么计算？⭐⭐
**Q14:** JAX vs PyTorch 在推荐系统训练中的对比 ⭐
**Q15:** 模型蒸馏如何应用于推荐系统？⭐⭐
**Q16:** 什么是 Feature Hashing？和 Multi-Hash Embedding 的关系 ⭐⭐
**Q17:** 对比式学习 (Contrastive Learning) 在双塔模型中的应用 ⭐⭐⭐
**Q18:** 如何在 Transformer 中处理变长序列？⭐
**Q19:** 预训练-微调范式在推荐系统中的应用 ⭐⭐
**Q20:** 解释 Grok-1 的核心架构特点 ⭐⭐
