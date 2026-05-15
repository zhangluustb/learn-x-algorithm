# L02 - Transformer 基础与注意力机制

> **"注意力是你的意识的聚光灯——Transformer 就是让机器学会'该看哪里'。"**

---

## 📌 本节目标

1. 理解从 RNN 到 Attention 的演进动机
2. 掌握 Self-Attention 的数学原理
3. 了解 Multi-Head Attention 与 Grouped Query Attention（GQA）
4. 理解 RoPE 旋转位置编码的直觉与公式
5. 认识 RMSNorm 与残差连接的作用

---

## 📚 前置知识

- 基础线性代数（矩阵乘法、向量点积）
- 了解神经网络的基本概念（前向传播、反向传播）

---

## 正文讲解

### 1. 从 RNN 到 Attention——为什么我们需要 Transformer

> **类比**：RNN 像是一个人在逐字阅读一本书，读到第 1000 页时，第 1 页的内容已经模糊了。而 Attention 机制让你可以随时"翻页"回到任何一页查阅。

**RNN 的瓶颈：**
- 顺序处理，无法并行化
- 长序列中的信息衰减（梯度消失/爆炸）
- 计算复杂度 $O(n)$ 但无法利用 GPU 并行

**Attention 的突破：**
- 全局视野：任何位置可以直接关注任何其他位置
- 可并行化：所有位置的 Attention 可以同时计算
- Transformer（2017）= Self-Attention + FFN + 残差

### 2. Self-Attention 的数学原理

Self-Attention 的核心是三个投影：**Query(Q)、Key(K)、Value(V)**。

> **类比**：想象你在图书馆找书。
> - **Query** = 你心里想找的"关键词"
> - **Key** = 每本书封面上的"标签"
> - **Value** = 书的实际内容
> 
> 你用 Query 去匹配每本书的 Key，匹配度越高的书，你越仔细地阅读它的 Value。

#### 数学公式

给定输入序列 $X \in \mathbb{R}^{n \times d}$：

$$Q = XW_Q, \quad K = XW_K, \quad V = XW_V$$

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

逐步拆解：

| 步骤 | 操作 | 直觉 |
|------|------|------|
| 1 | $QK^T$ | 计算每对位置的"匹配度" |
| 2 | $\div \sqrt{d_k}$ | 缩放，防止 softmax 进入饱和区 |
| 3 | softmax | 转化为概率分布（权重之和为 1） |
| 4 | $× V$ | 用权重加权聚合 Value |

**为什么要除以 $\sqrt{d_k}$？** 当 $d_k$ 较大时，点积值的方差约为 $d_k$，softmax 会趋于 one-hot，梯度几乎为零。除以 $\sqrt{d_k}$ 让方差回到 1。

### 3. Multi-Head Attention 与 GQA

#### 3.1 Multi-Head Attention (MHA)

> **类比**：一个翻译团队中有 8 个专家，每人关注不同的语言特征——有人关注语法，有人关注语义，有人关注情感。最后把各自的理解合并。

$$\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, ..., \text{head}_h)W_O$$

$$\text{head}_i = \text{Attention}(QW_Q^i, KW_K^i, VW_V^i)$$

在 x-algorithm 的 Grok 模型中，使用了 **Grouped Query Attention (GQA)**：

#### 3.2 GQA：参数效率的折中

| 方案 | Q 头数 | KV 头数 | 特点 |
|------|--------|---------|------|
| MHA | $h$ | $h$ | 每个 Q 头有独立的 KV 对 |
| MQA | $h$ | $1$ | 所有 Q 头共享一对 KV |
| **GQA** | $h$ | $g$ (< $h$) | 每 $h/g$ 个 Q 头共享一对 KV |

在 x-algorithm 的 `grok.py` 中：
```python
@dataclass
class TransformerConfig:
    num_q_heads: int    # 例如 32
    num_kv_heads: int   # 例如 8（GQA，4:1 分组）
    key_size: int       # 每个头的维度
```

GQA 在几乎不损失性能的前提下，显著减少了 KV 缓存的内存占用。

### 4. RoPE 旋转位置编码

Transformer 本身没有位置信息（排列不变性）。我们需要告诉模型"第1个词在第2个词前面"。

> **类比**：RoPE 就像给时钟指针一个角度——第 1 个词在 12 点方向转了一小步，第 100 个词转了 100 步。两个词之间的"角度差"就编码了它们的相对距离。

#### 数学定义

对位置 $m$ 的向量 $\mathbf{x}$，RoPE 将相邻两个维度视为一个复数对，进行旋转：

$$\text{RoPE}(\mathbf{x}, m) = \mathbf{x} \odot \cos(m\theta) + \hat{\mathbf{x}} \odot \sin(m\theta)$$

其中 $\theta_i = 10000^{-2i/d}$，$\hat{\mathbf{x}}$ 是将相邻维度交换并取反的结果。

在 `grok.py` 中的实现：
```python
class RotaryEmbedding(hk.Module):
    # 默认 min_timescale=1, max_timescale=10000
    def __call__(self, x, seq_len, offset=0):
        # 生成频率：fraction = 2i/d
        # timescale = min * (max/min)^fraction
        # 旋转角 = position / timescale
```

**RoPE 的优势：**
- 天然编码**相对位置**（两个位置的旋转角之差只取决于它们的距离）
- 可外推到训练时未见的长度
- 不需要额外的可学习参数

### 5. RMSNorm 与残差连接

#### 5.1 RMSNorm

LayerNorm 的简化版，去掉了均值偏移，只做缩放：

$$\text{RMSNorm}(\mathbf{x}) = \frac{\mathbf{x}}{\text{RMS}(\mathbf{x})} \odot \gamma$$

其中：$\text{RMS}(\mathbf{x}) = \sqrt{\frac{1}{d}\sum_{i=1}^{d} x_i^2}$

```python
class RMSNorm(hk.Module):
    def __call__(self, x):
        # 1. 计算 RMS（在最后一维上）
        # 2. 除以 RMS（+ epsilon 防止除零）
        # 3. 乘以可学习的 scale 参数
```

**为什么不用 LayerNorm？** RMSNorm 计算更快（省去了均值计算），且在实践中效果几乎相同。

#### 5.2 残差连接

$$\mathbf{y} = \mathbf{x} + \text{SubLayer}(\text{RMSNorm}(\mathbf{x}))$$

> **类比**：残差连接就像"跳级通道"——即使子层学到的东西很少，原始信息也能完整传递，防止深层网络中信息丢失。

在 x-algorithm 中，每个 DecoderLayer 有两个残差连接：
1. MHA 输出 + 输入
2. FFN 输出 + MHA 输出

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| Self-Attention | $\text{softmax}(QK^T/\sqrt{d_k})V$，让每个位置根据"匹配度"聚合全局信息 |
| GQA | Q 头多、KV 头少的折中方案，减少内存占用 |
| RoPE | 通过旋转向量维度对编码相对位置，无需额外参数 |
| RMSNorm | 去掉均值偏移的 LayerNorm，更快更简洁 |
| 残差连接 | 保证信息在深层网络中不丢失 |

---

## 📝 习题集2

**概念理解：**
1. 为什么 Attention 的 softmax 分母要除以 $\sqrt{d_k}$？如果不除会怎样？
2. GQA 中 `num_q_heads=32, num_kv_heads=8` 意味着什么？KV 缓存节省了多少内存？

**数学推导：**
3. 证明 RoPE 编码使得位置 $m$ 和 $n$ 的 attention score 只取决于 $m-n$。
4. 写出 RMSNorm 对 $\mathbf{x} = [3, 4]$ 的计算过程（假设 $\gamma = [1, 1]$）。

**设计思考：**
5. x-algorithm 的推荐场景中，用户历史行为序列的长度可能很不一样。RoPE 的外推能力为什么在这里很重要？
6. 如果将 MHA 换成 MQA（所有头共享 KV），推荐质量可能会怎样变化？

---

> 下一课我们将学习 **L03 - Rust & Python 技术栈快速上手**，为阅读源码做技术准备。
