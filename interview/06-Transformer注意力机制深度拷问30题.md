# 06 - Transformer 注意力机制深度拷问 30 题

> 每题含标准答案、x-algorithm 实现对照、追问方向。

---

## Q1: Self-Attention 为什么要除以 $\sqrt{d_k}$？⭐

**答案：** 当 $d_k$ 较大时，$Q$ 和 $K$ 的点积方差约为 $d_k$，导致 softmax 趋于 one-hot，梯度接近零。除以 $\sqrt{d_k}$ 使方差归一化到 1。

**追问：** 如果不除会怎样？模型能学到正确的 attention pattern 吗？

---

## Q2: GQA 的 KV 头数设为多少最优？⭐⭐

**答案：** 经验上 Q:KV = 4:1 到 8:1 是最佳区间。x-algorithm 用 32:8 (4:1)。

$\text{KV 缓存} = 2 \times H_{kv} \times d_k \times L \times N_{layers} \times \text{sizeof}(\text{dtype})$

---

## Q3: RoPE 如何编码相对位置？给出数学证明。⭐⭐⭐

**答案：** 对位置 $m$ 和 $n$ 的向量：
$$\langle \text{RoPE}(q, m), \text{RoPE}(k, n) \rangle = f(q, k, m-n)$$

证明利用旋转矩阵的性质：$R_m^T R_n = R_{n-m}$

---

## Q4: Candidate Isolation 掩码的完整构造方法？⭐⭐⭐

**答案：**
1. User + History 位置：标准下三角因果掩码
2. 每个 Candidate 位置：只看 User+History 全部 + 自己
3. 用 -1e9 填充不可见位置（softmax 后趋于 0）

---

## Q5: MultiHead Attention 的参数量计算 ⭐⭐

$$\text{Params} = 4 \times d_{model} \times d_{model} = 4d^2 \text{ (Q,K,V,O 四个投影)}$$

GQA 下：$\text{Params} = d(H_q \cdot d_k + 2 \cdot H_{kv} \cdot d_k + d)$

---

## Q6-Q30: （标题列表）

**Q6:** Flash Attention 的 IO 优化原理 ⭐⭐⭐
**Q7:** KV Cache 在增量推理中的作用 ⭐⭐
**Q8:** 注意力分数的稀疏性分析 ⭐⭐
**Q9:** Pre-Norm vs Post-Norm 对梯度流的影响 ⭐⭐
**Q10:** 多头注意力中不同头学到了什么？⭐⭐
**Q11:** 注意力权重可以用来解释推荐结果吗？⭐⭐
**Q12:** Sliding Window Attention 的适用场景 ⭐⭐
**Q13:** ALiBi 和 RoPE 位置编码对比 ⭐⭐⭐
**Q14:** 注意力模式在用户行为序列中的体现 ⭐⭐
**Q15:** 如何可视化推荐 Transformer 的注意力矩阵？⭐⭐
**Q16:** Attention is Not All You Need? FFN 的作用 ⭐⭐
**Q17:** Linear Attention 能否替代 Softmax Attention？⭐⭐⭐
**Q18:** 长序列处理：Ring Attention / Sequence Parallelism ⭐⭐⭐
**Q19:** Cross-Attention 在检索增强推荐中的应用 ⭐⭐
**Q20:** 注意力掩码的不同设计对推荐质量的影响 ⭐⭐⭐
**Q21:** SiLU vs GELU vs ReLU 激活函数对比 ⭐⭐
**Q22:** FFN 的 widening_factor 如何影响模型容量？⭐⭐
**Q23:** MoE (Mixture of Experts) 的路由机制 ⭐⭐⭐
**Q24:** 梯度裁剪在 Transformer 训练中的必要性 ⭐
**Q25:** 学习率 Warmup + Cosine Decay 的原理 ⭐⭐
**Q26:** 混合精度训练中的 Loss Scaling ⭐⭐
**Q27:** 模型并行 vs 数据并行 vs 流水线并行 ⭐⭐⭐
**Q28:** Transformer 的推理优化技术综述 ⭐⭐
**Q29:** 量化 (INT8/INT4) 在推荐推理中的应用 ⭐⭐
**Q30:** 未来方向：State Space Models 能否替代 Transformer？⭐⭐⭐
