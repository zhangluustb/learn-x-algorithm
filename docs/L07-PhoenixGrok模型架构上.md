# L07 - Phoenix Grok 模型架构（上）：Transformer 核心

> **"Grok-1 是为对话而生的，但经过巧妙适配，它成为了推荐系统的大脑。"**

---

## 📌 本节目标

1. 理解从 Grok-1 到推荐系统的适配思路
2. 掌握 TransformerConfig 配置参数
3. 深入 DecoderLayer 的 MHA + FFN 残差结构
4. 理解 GQA 在 x-algorithm 中的具体实现
5. 认识 SiLU 门控 FFN（DenseBlock）

---

## 📚 前置知识

- L02 中的 Transformer / Attention 基础
- L03 中的 JAX/Haiku 基本用法

---

## 正文讲解

### 1. 从 Grok-1 到推荐系统的适配

> **类比**：Grok-1 原本是一位"全能翻译官"，能理解和生成自然语言。x-algorithm 把它改造成了一位"鉴赏师"——不再生成文字，而是观察用户的行为历史和候选帖子，预测用户会做出什么反应。

**关键改动：**

| 方面 | Grok-1 (LLM) | Phoenix (推荐) |
|------|--------------|----------------|
| 输入 | Token 序列 | 用户行为序列 + 候选帖子 |
| 输出 | 下一个 Token 的概率 | 19 种行为的概率 |
| 注意力 | 因果掩码（只看前文） | 因果 + 候选隔离掩码 |
| 嵌入 | Token embedding | Multi-hash embedding |
| 位置编码 | RoPE | RoPE（保留） |

核心 Transformer 组件（Attention、FFN、RMSNorm、RoPE）完全复用 Grok-1，只改变了输入输出和注意力掩码。

### 2. TransformerConfig 配置解读

```python
@dataclass
class TransformerConfig:
    emb_size: int          # 嵌入维度（如 2048）
    key_size: int          # 每个注意力头的维度（如 64）
    num_q_heads: int       # Query 头数（如 32）
    num_kv_heads: int      # Key/Value 头数（GQA，如 8）
    num_layers: int        # Transformer 层数（如 12）
    widening_factor: float # FFN 扩展倍数（默认 4.0）
```

**参数关系：**

$$\text{hidden\_dim} = \text{emb\_size} = \text{key\_size} \times \text{num\_q\_heads}$$

$$\text{FFN\_dim} = \text{emb\_size} \times \text{widening\_factor}$$

例如：`emb_size=2048, key_size=64, num_q_heads=32, widening_factor=4.0`
- 隐藏维度 = 2048
- FFN 维度 = 8192
- GQA 分组：32/8 = 每 4 个 Q 头共享一对 KV

### 3. DecoderLayer：MHA → FFN 残差结构

每个 DecoderLayer 包含两个子层，各自带有 RMSNorm 和残差连接：

```python
class DecoderLayer(hk.Module):
    def __call__(self, x, mask, position):
        # 子层 1: Multi-Head Attention
        residual = x
        x = RMSNorm()(x)                    # Pre-norm
        x = MultiHeadAttention()(x, mask, position)
        x = x + residual                     # 残差连接
        
        # 子层 2: Feed-Forward Network
        residual = x
        x = RMSNorm()(x)                    # Pre-norm
        x = DenseBlock()(x)                  # SiLU 门控 FFN
        x = x + residual                     # 残差连接
        
        return x
```

**Pre-Norm vs Post-Norm：**

| 方式 | 公式 | 特点 |
|------|------|------|
| Post-Norm | $x + \text{SubLayer}(x)$, then Norm | 原始 Transformer |
| **Pre-Norm** | $x + \text{SubLayer}(\text{Norm}(x))$ | 训练更稳定，x-algorithm 使用 |

Pre-Norm 让残差路径上的梯度更加平滑，有利于深层网络训练。

### 4. GQA 在 x-algorithm 中的实现

```python
class MultiHeadAttention(hk.Module):
    def __call__(self, x, mask, position):
        # 1. 投影 Q, K, V
        q = Linear(num_q_heads * key_size)(x)    # [B, L, H_q * D]
        k = Linear(num_kv_heads * key_size)(x)   # [B, L, H_kv * D]
        v = Linear(num_kv_heads * key_size)(x)   # [B, L, H_kv * D]
        
        # 2. 重塑为多头
        q = q.reshape(B, L, num_q_heads, key_size)   # [B, L, 32, 64]
        k = k.reshape(B, L, num_kv_heads, key_size)  # [B, L, 8, 64]
        v = v.reshape(B, L, num_kv_heads, key_size)   # [B, L, 8, 64]
        
        # 3. 应用 RoPE 位置编码
        q = RotaryEmbedding()(q, seq_len, offset)
        k = RotaryEmbedding()(k, seq_len, offset)
        
        # 4. GQA：将 KV 头扩展以匹配 Q 头数
        #    每个 KV 头被 num_q_heads/num_kv_heads = 4 个 Q 头共享
        k = repeat_kv(k, num_q_heads // num_kv_heads)  # [B, L, 32, 64]
        v = repeat_kv(v, num_q_heads // num_kv_heads)   # [B, L, 32, 64]
        
        # 5. 计算注意力
        attn_weights = (q @ k.T) / sqrt(key_size)
        attn_weights = attn_weights + mask    # 应用掩码
        attn_weights = softmax(attn_weights)
        output = attn_weights @ v
        
        # 6. 合并多头 + 输出投影
        output = output.reshape(B, L, num_q_heads * key_size)
        output = Linear(emb_size)(output)
        return output
```

**GQA 的内存节省：**

$$\text{KV 缓存大小} = 2 \times \text{num\_kv\_heads} \times \text{key\_size} \times \text{seq\_len} \times \text{num\_layers}$$

使用 GQA (8 KV heads) 相比 MHA (32 KV heads)，KV 缓存减少了 **75%**。

### 5. SiLU 门控 FFN（DenseBlock）

> **类比**：门控 FFN 就像一个"双通道过滤器"——一个通道处理信息，另一个通道决定"放行多少"。

```python
class DenseBlock(hk.Module):
    def __call__(self, x):
        # x: [B, L, emb_size]
        
        # 门控分支：决定"放行多少"
        gate = Linear(ffn_dim)(x)      # [B, L, ffn_dim]
        gate = jax.nn.silu(gate)        # SiLU 激活
        
        # 值分支：实际信息
        value = Linear(ffn_dim)(x)      # [B, L, ffn_dim]
        
        # 门控相乘
        hidden = gate * value           # 逐元素乘法
        
        # 降维回原始维度
        output = Linear(emb_size)(hidden)  # [B, L, emb_size]
        return output
```

**SiLU (Sigmoid Linear Unit)：**

$$\text{SiLU}(x) = x \cdot \sigma(x) = \frac{x}{1 + e^{-x}}$$

比 ReLU 更平滑，在 $x < 0$ 时不完全截断，保留了一些负值信息。

**门控机制的直觉：**
- `gate` 经过 SiLU 后，值域在 $(-0.28, +\infty)$
- `value` 是原始变换后的信息
- 两者相乘 = gate 控制 value 的"通行量"
- 模型学会对不同维度"开关门"

### 6. Transformer：层层堆叠

```python
class Transformer(hk.Module):
    def __call__(self, x, mask, position):
        for i in range(num_layers):
            x = DecoderLayer(name=f"layer_{i}")(x, mask, position)
        x = RMSNorm()(x)  # 最终 norm
        return x
```

每一层都在残差基础上"精炼"表示——浅层捕获局部模式，深层捕获全局语义。

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| Grok 适配 | 复用 Transformer 核心，改变输入输出和注意力掩码 |
| DecoderLayer | Pre-Norm + MHA + 残差 + Pre-Norm + FFN + 残差 |
| GQA | 32 个 Q 头共享 8 对 KV，节省 75% KV 缓存 |
| SiLU 门控 FFN | 双分支结构，gate 控制 value 的通行量 |
| Transformer | N 层 DecoderLayer 堆叠，逐层精炼表示 |

---

## 📝 习题集7

**概念理解：**
1. Pre-Norm 为什么比 Post-Norm 训练更稳定？从梯度流的角度分析。
2. `widening_factor=4.0` 意味着 FFN 的中间维度是输入维度的 4 倍。为什么 FFN 需要"先扩展再压缩"？

**数学推导：**
3. 计算 GQA 配置 `num_q_heads=32, num_kv_heads=8, key_size=64` 的 KV 缓存大小（假设序列长度 1000，12 层，bfloat16）。
4. 证明 SiLU 的导数为 $\sigma(x)(1 + x(1-\sigma(x)))$，解释为什么它在零点附近梯度不为零。

**设计思考：**
5. x-algorithm 为什么选择 12 层而不是更深的网络？推荐系统对延迟的要求如何影响模型选择？

---

> 下一课我们将学习 **L08 - Phoenix Grok 模型架构（下）：嵌入与注意力掩码**，解锁 x-algorithm 的关键创新。
