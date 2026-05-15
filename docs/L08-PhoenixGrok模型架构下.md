# L08 - Phoenix Grok 模型架构（下）：嵌入与注意力掩码

> **"候选隔离是一个小巧的技巧，却带来了巨大的工程价值——让每条帖子的分数独立于批次。"**

---

## 📌 本节目标

1. 掌握 Multi-Hash Embedding 策略
2. 理解三层 Embedding Reduction 流程
3. 深入 Candidate Isolation 注意力掩码（关键创新）
4. 了解混合精度计算策略
5. 熟悉 RecsysBatch 数据容器

---

## 📚 前置知识

- L07 中的 Transformer 核心组件
- L02 中的注意力机制数学

---

## 正文讲解

### 1. Multi-Hash Embedding 策略

> **类比**：传统嵌入像"身份证号"——每个实体一个唯一 ID 映射到一个向量。Multi-Hash 像是给每个人拍了 3 张不同角度的照片，然后合成一张立体像。即使某一张照片模糊了（哈希冲突），其他角度仍能提供信息。

```python
@dataclass
class HashConfig:
    num_user_hashes: int = 2     # 每个用户 2 个哈希
    num_item_hashes: int = 3     # 每个帖子 3 个哈希
    num_author_hashes: int = 2   # 每个作者 2 个哈希
```

**为什么用 Hash 而不是直接的 ID 嵌入？**

| 方案 | 嵌入表大小 | 优势 | 劣势 |
|------|-----------|------|------|
| ID 嵌入 | 用户数 × 维度 | 精确 | 需要巨大嵌入表 |
| 单 Hash | 桶数 × 维度 | 内存可控 | 哈希冲突丢失信息 |
| **Multi Hash** | $N_{hash}$ × 桶数 × 维度 | 减少冲突 | 略增计算量 |

使用多个哈希函数，即使某个哈希冲突了，其他哈希仍可区分不同实体。

### 2. 三层 Embedding Reduction

模型输入是 `RecsysBatch`，但 Transformer 需要固定维度的序列。三层 Reduction 负责将多哈希嵌入"压缩"为统一的表示：

```
原始哈希 ID → 查表得到多个嵌入 → Reduction → 统一维度表示
```

#### 2.1 User Reduction

```python
def block_user_reduce(user_hash_embeddings):
    """
    输入: [B, num_user_hashes, emb_dim]  # 如 [B, 2, 2048]
    输出: [B, 1, emb_size]               # 如 [B, 1, 2048]
    """
    # 拼接多个哈希嵌入
    concat = concatenate(user_hash_embeddings)  # [B, 2*2048]
    # 投影到目标维度
    reduced = Linear(emb_size)(concat)          # [B, 2048]
    return reduced.unsqueeze(1)                  # [B, 1, 2048]
```

#### 2.2 History Reduction

```python
def block_history_reduce(history_post_embs, history_author_embs, 
                          history_actions, history_surface):
    """
    将每条历史记录的帖子+作者+行为+surface信息压缩为一个向量
    输入: 每条历史有 num_item_hashes + num_author_hashes 个嵌入
    输出: [B, history_seq_len, emb_size]
    """
    for each history position:
        # 拼接该位置的所有嵌入
        concat = [post_hash_1, post_hash_2, post_hash_3,
                  author_hash_1, author_hash_2,
                  action_embedding, surface_embedding]
        # 投影
        reduced = Linear(emb_size)(concat)
    return history_sequence  # [B, H, emb_size]
```

#### 2.3 Candidate Reduction

```python
def block_candidate_reduce(candidate_post_embs, candidate_author_embs,
                            candidate_surface):
    """
    同 History Reduction，但没有 action 信息（候选还没被用户交互）
    输出: [B, candidate_seq_len, emb_size]
    """
```

**最终拼接成序列：**

```
[USER] [HISTORY_1] ... [HISTORY_H] [CANDIDATE_1] ... [CANDIDATE_C]
  1         H 个                         C 个
```

总序列长度 = $1 + H + C$

### 3. Candidate Isolation 注意力掩码（关键创新）

这是 x-algorithm 最重要的设计创新。

> **类比**：想象一场面试。面试官（用户上下文）可以看到所有候选人。但候选人之间用隔板隔开——每个候选人只能和面试官交流，看不到其他候选人。这确保了对每个候选人的评价是**独立的**。

#### 掩码结构

```
                  User  History  Cand_1  Cand_2  Cand_3
         User  [  1      0       0       0       0   ]  ← 因果
      History  [  1      causal  0       0       0   ]  ← 因果
       Cand_1  [  1      1       1       0       0   ]  ← 看 User+History+自己
       Cand_2  [  1      1       0       1       0   ]  ← 看 User+History+自己
       Cand_3  [  1      1       0       0       1   ]  ← 看 User+History+自己
```

```python
def build_candidate_isolation_mask(history_len, num_candidates):
    total_len = 1 + history_len + num_candidates
    mask = np.full((total_len, total_len), -1e9)  # 默认全遮挡
    
    # User + History 部分：因果掩码
    context_len = 1 + history_len
    for i in range(context_len):
        for j in range(i + 1):
            mask[i][j] = 0  # 可见
    
    # Candidate 部分：每个候选看 User+History+自己
    for c in range(num_candidates):
        pos = context_len + c
        # 看 User + 全部 History
        mask[pos, :context_len] = 0
        # 看自己
        mask[pos, pos] = 0
        # 不看其他候选（保持 -1e9）
    
    return mask
```

#### 为什么这很重要？

| 没有 Candidate Isolation | 有 Candidate Isolation |
|-------------------------|----------------------|
| 候选 A 的分数取决于同批次的 B、C | 候选 A 的分数只取决于用户上下文 |
| 换一批候选，A 的分数会变 | 无论和谁同批，A 的分数不变 |
| 无法缓存分数 | **分数可以缓存和复用** |
| 批次组成影响排序 | 排序结果确定性 |

### 4. 混合精度：fp32 参数 + bfloat16 计算

```python
@dataclass
class PhoenixModelConfig:
    fprop_dtype: jnp.dtype = jnp.bfloat16  # 前向传播用 bfloat16
```

```python
class Linear(hk.Module):
    def __call__(self, x):
        # 参数以 float32 存储（精度高）
        w = hk.get_parameter("w", shape=..., 
                              init=hk.initializers.RandomNormal())
        # 计算时转为 bfloat16（速度快）
        w = w.astype(self.fprop_dtype)  # float32 → bfloat16
        x = x.astype(self.fprop_dtype)
        return x @ w
```

**bfloat16 vs float16 vs float32：**

| 类型 | 位数 | 指数位 | 尾数位 | 范围 | 精度 |
|------|------|--------|--------|------|------|
| float32 | 32 | 8 | 23 | 大 | 高 |
| float16 | 16 | 5 | 10 | 小 | 中 |
| **bfloat16** | 16 | **8** | **7** | **大** | 低 |

bfloat16 保留了 float32 的范围（8 位指数），牺牲精度。在深度学习中，范围比精度更重要（避免溢出）。

### 5. RecsysBatch 数据容器

```python
class RecsysBatch(NamedTuple):
    # 用户哈希 ID
    user_hashes: jnp.ndarray           # [B, num_user_hashes]
    
    # 历史行为序列
    history_post_hashes: jnp.ndarray   # [B, H, num_item_hashes]
    history_author_hashes: jnp.ndarray # [B, H, num_author_hashes]
    history_actions: jnp.ndarray       # [B, H]  行为类型
    history_product_surface: jnp.ndarray  # [B, H]  产品界面
    
    # 候选帖子
    candidate_post_hashes: jnp.ndarray   # [B, C, num_item_hashes]
    candidate_author_hashes: jnp.ndarray # [B, C, num_author_hashes]
    candidate_product_surface: jnp.ndarray  # [B, C]
```

**数据流图：**

```
RecsysBatch
    │
    ├── user_hashes ──────── block_user_reduce ──────┐
    ├── history_* ────────── block_history_reduce ───┤
    └── candidate_* ──────── block_candidate_reduce ─┤
                                                      │
                                                      ▼
                                              拼接成序列
                                       [USER][HISTORY...][CAND...]
                                                      │
                                                      ▼
                                    Transformer + Candidate Isolation Mask
                                                      │
                                                      ▼
                                         取候选位置的输出
                                                      │
                                                      ▼
                                    Linear → [B, C, num_actions=19]
```

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| Multi-Hash Embedding | 多个哈希函数减少冲突，提高嵌入质量 |
| Three-Level Reduction | User/History/Candidate 各自压缩为统一维度 |
| Candidate Isolation | 候选之间互不可见，保证分数独立性和可缓存性 |
| 混合精度 | fp32 存参数保精度，bfloat16 计算保速度 |
| RecsysBatch | 结构化的模型输入容器 |

---

## 📝 习题集8

**概念理解：**
1. 为什么 Candidate Isolation 让分数可以缓存？具体在什么场景下缓存有用？
2. Multi-Hash 使用 3 个哈希函数，冲突概率相比单哈希降低了多少？（假设每个哈希桶数为 $M$，实体数为 $N$）

**代码阅读：**
3. 在 `grok.py` 中找到注意力掩码的构建代码，画出 `history_len=3, num_candidates=2` 时的完整掩码矩阵。
4. `RecsysEmbeddings` 和 `RecsysBatch` 的区别是什么？为什么需要两个数据结构？

**设计思考：**
5. 如果去掉 Candidate Isolation（让候选互相看到），模型能学到什么额外信息？这些信息值得付出"分数不可缓存"的代价吗？

---

> 下一课我们将学习 **L09 - Phoenix 排序模型：多行为预测**，看模型如何输出 19 维预测。
