# L10 - Phoenix 检索模型：双塔架构

> **"如何从 10 亿条帖子中找到你可能感兴趣的那几千条？双塔模型用向量相似度'秒答'。"**

---

## 📌 本节目标

1. 理解 Two-Tower 模型的基本原理
2. 掌握 User Tower 的编码过程
3. 了解 Candidate Tower 的嵌入与 L2 归一化
4. 理解 Dot Product 相似度搜索
5. 掌握 Top-K 检索流程

---

## 📚 前置知识

- L08 中的 Multi-Hash Embedding
- L09 中的 PhoenixModel 概念

---

## 正文讲解

### 1. Two-Tower 模型——检索的核心思想

> **类比**：双塔模型就像"相亲平台"——一个塔把你的喜好编码成一张"趣味卡片"，另一个塔把每条帖子编码成一张"内容卡片"。匹配度最高的帖子就是你最可能喜欢的。

```
              User Tower                    Candidate Tower
        ┌─────────────────┐           ┌─────────────────────┐
        │ 用户哈希嵌入      │           │ 帖子哈希嵌入          │
        │ 历史行为序列      │           │ 作者哈希嵌入          │
        │ 行为类型嵌入      │           │ 产品界面嵌入          │
        └────────┬────────┘           └─────────┬───────────┘
                 │                               │
                 ▼                               ▼
        ┌─────────────────┐           ┌─────────────────────┐
        │   Reduction +    │           │   Reduction +        │
        │   Transformer    │           │   L2 归一化           │
        └────────┬────────┘           └─────────┬───────────┘
                 │                               │
                 ▼                               ▼
            user_repr                      candidate_repr
           [1, emb_size]              [N_corpus, emb_size]
                 │                               │
                 └──────── dot product ──────────┘
                                │
                                ▼
                         similarity scores
                        Top-K 最相似的帖子
```

**关键设计：双塔独立编码**

| 特性 | 优势 |
|------|------|
| User 和 Candidate 独立计算 | Candidate 嵌入可以离线预计算 |
| 向量维度相同 | 可以用高效的 ANN 索引（如 FAISS） |
| 点积相似度 | 计算极快，支持海量检索 |

### 2. User Tower：用户特征编码

User Tower 复用了排序模型的 Transformer 架构，但只取用户表示：

```python
class PhoenixRetrievalModel(hk.Module):
    def __call__(self, batch: RecsysBatch) -> RetrievalOutput:
        # 1. 嵌入查表
        embeddings = self._lookup_embeddings(batch)
        
        # 2. User + History Reduction
        user_repr = block_user_reduce(embeddings.user)
        history_repr = block_history_reduce(
            embeddings.history_posts,
            embeddings.history_authors,
            batch.history_actions,
            batch.history_product_surface
        )
        
        # 3. 拼接 User + History
        context = jnp.concatenate(
            [user_repr, history_repr], axis=1
        )  # [B, 1+H, emb_size]
        
        # 4. causal mask（只有上下文部分）
        mask = build_causal_mask(1 + history_seq_len)
        
        # 5. Transformer 编码
        output = Transformer(config)(context, mask, positions)
        
        # 6. 取最后一个位置作为用户表示
        user_representation = output[:, -1, :]  # [B, emb_size]
        
        return user_representation
```

**为什么取最后一个位置？** 因为因果注意力下，最后一个位置能"看到"前面所有的信息——它是整个用户上下文的"摘要"。

### 3. Candidate Tower：帖子嵌入

Candidate Tower 相对简单——不需要 Transformer，只需要将帖子的多哈希嵌入压缩并归一化：

```python
class CandidateTower(hk.Module):
    def __call__(self, post_embeddings, author_embeddings):
        # 1. Reduction：合并帖子+作者的多哈希嵌入
        concat = jnp.concatenate(
            [post_embeddings, author_embeddings], axis=-1
        )
        repr = Linear(emb_size)(concat)  # [N, emb_size]
        
        # 2. L2 归一化
        repr = repr / jnp.linalg.norm(repr, axis=-1, keepdims=True)
        
        return repr  # [N, emb_size], L2 norm = 1
```

**为什么要 L2 归一化？**

当两个向量都是单位向量时：

$$\text{dot}(\mathbf{u}, \mathbf{v}) = \cos(\theta)$$

点积 = 余弦相似度，值域 $[-1, 1]$，含义清晰：
- $1$ = 完全匹配
- $0$ = 无关
- $-1$ = 完全相反

### 4. Dot Product 相似度检索

```python
def retrieve_top_k(user_repr, candidate_pool, k=1000):
    """
    user_repr: [1, emb_size]         # 一个用户
    candidate_pool: [N, emb_size]     # N 个候选（全量语料库）
    """
    # 点积计算相似度
    scores = user_repr @ candidate_pool.T  # [1, N]
    
    # 取 Top-K
    top_k_indices = jnp.argsort(scores, axis=-1)[:, -k:][:, ::-1]
    top_k_scores = jnp.take_along_axis(scores, top_k_indices, axis=-1)
    
    return RetrievalOutput(
        user_representation=user_repr,
        top_k_indices=top_k_indices,    # [1, K]
        top_k_scores=top_k_scores,      # [1, K]
    )
```

**实际生产中的优化：**

直接对 10 亿候选做暴力点积太慢。生产环境使用**近似最近邻（ANN）**索引：

| 方法 | 原理 | 延迟 |
|------|------|------|
| 暴力搜索 | 遍历全部候选 | $O(N)$，秒级 |
| **HNSW** | 分层导航小世界图 | $O(\log N)$，毫秒级 |
| **IVF** | 倒排文件索引 | $O(N/K)$，毫秒级 |
| **ScaNN** | 量化 + 各向异性 | $O(\sqrt{N})$，亚毫秒 |

候选帖子的嵌入**离线计算并建立索引**，在线时只需：
1. 计算用户嵌入（User Tower 前向传播）
2. 在索引中查找最近邻（ANN 检索）

### 5. Top-K 检索流程（run_retrieval.py）

```python
# run_retrieval.py 的完整流程

# 1. 配置检索模型
config = PhoenixModelConfig(
    model=TransformerConfig(
        emb_size=256,
        key_size=32,
        num_q_heads=8,
        num_kv_heads=2,
        num_layers=4,
    ),
    history_seq_len=50,
    candidate_seq_len=0,  # 检索时不需要候选（只编码用户）
)

# 2. 初始化模型
retrieval_model = create_retrieval_runner(config)

# 3. 构造用户输入
user_batch = RecsysBatch(
    user_hashes=...,
    history_post_hashes=...,
    history_author_hashes=...,
    history_actions=...,
    # candidate 字段为空
)

# 4. 编码用户
user_repr = retrieval_model.encode_user(user_batch)
# [1, 256]

# 5. 准备候选池（通常离线完成）
candidate_pool = retrieval_model.encode_candidates(all_posts)
# [1_000_000, 256]

# 6. 检索 Top-K
results = retrieve_top_k(user_repr, candidate_pool, k=1000)
print(f"Top-K indices: {results.top_k_indices}")
print(f"Top-K scores:  {results.top_k_scores}")
```

**检索与排序的配合：**

```
Phoenix Retrieval (双塔)          Phoenix Ranking (Transformer)
10 亿帖子 → Top-1000 候选    →    1000 候选 → 精排 Top-50
  快速但粗糙                        慢但精准
  毫秒级                            10-100 毫秒
```

这就是经典的"漏斗架构"——检索层快速缩小范围，排序层精细打分。

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| Two-Tower | 用户和候选独立编码，通过点积匹配 |
| User Tower | Transformer 编码 User + History，取最后位置输出 |
| Candidate Tower | Reduction + L2 归一化，生成单位向量 |
| ANN 索引 | HNSW/IVF/ScaNN 实现毫秒级海量检索 |
| 漏斗架构 | 检索（粗排）→ 排序（精排）→ 重排 |

---

## 📝 习题集10

**概念理解：**
1. 为什么 Candidate Tower 比 User Tower 简单得多？可以给 Candidate Tower 也加 Transformer 吗？
2. L2 归一化后点积等于余弦相似度。如果不归一化，点积在推荐场景中会有什么问题？

**数学推导：**
3. 假设嵌入维度 256，候选池 1000 万。计算暴力检索的 FLOP 数，与 HNSW（假设平均访问 1000 个节点）对比。

**设计思考：**
4. 双塔模型的一个缺点是用户和候选的交互只通过点积，无法建模复杂交互。x-algorithm 如何通过"检索+排序"两阶段弥补这个缺点？
5. 候选嵌入多久需要更新一次？如何平衡索引更新的计算成本和内容新鲜度？

---

> 下一课我们将进入第三部分——**L11 - Home Mixer 编排层总览**，看四大模块如何协同工作。
