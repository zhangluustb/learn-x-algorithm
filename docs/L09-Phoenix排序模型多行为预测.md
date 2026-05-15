# L09 - Phoenix 排序模型：多行为预测

> **"不是预测'你是否感兴趣'，而是预测'你会点赞、回复、转发还是屏蔽'——精细度决定了推荐质量。"**

---

## 📌 本节目标

1. 掌握 PhoenixModel 的完整前向传播流程
2. 理解 19 种用户行为预测的含义
3. 分析 RecsysModelOutput 输出结构
4. 了解 runners.py 的模型初始化与推理过程

---

## 📚 前置知识

- L07-L08 中的 Transformer + 嵌入 + 掩码

---

## 正文讲解

### 1. PhoenixModel——完整前向传播

```python
class PhoenixModel(hk.Module):
    def __call__(self, batch: RecsysBatch) -> RecsysModelOutput:
        config = self.config  # PhoenixModelConfig
        
        # ==========================================
        # Step 1: 嵌入查表
        # ==========================================
        embeddings = self._lookup_embeddings(batch)
        # 所有哈希 ID → 对应的嵌入向量
        
        # ==========================================
        # Step 2: 三层 Reduction
        # ==========================================
        user_repr = block_user_reduce(embeddings.user)
        # [B, 1, emb_size]
        
        history_repr = block_history_reduce(
            embeddings.history_posts,
            embeddings.history_authors,
            batch.history_actions,
            batch.history_product_surface
        )  # [B, H, emb_size]
        
        candidate_repr = block_candidate_reduce(
            embeddings.candidate_posts,
            embeddings.candidate_authors,
            batch.candidate_product_surface
        )  # [B, C, emb_size]
        
        # ==========================================
        # Step 3: 拼接成序列
        # ==========================================
        sequence = jnp.concatenate(
            [user_repr, history_repr, candidate_repr], 
            axis=1
        )  # [B, 1+H+C, emb_size]
        
        # ==========================================
        # Step 4: 构建 Candidate Isolation 掩码
        # ==========================================
        mask = build_candidate_isolation_mask(
            context_len=1 + config.history_seq_len,
            num_candidates=config.candidate_seq_len
        )
        
        # ==========================================
        # Step 5: Transformer 前向传播
        # ==========================================
        output = Transformer(config.model)(
            sequence, mask, positions
        )  # [B, 1+H+C, emb_size]
        
        # ==========================================
        # Step 6: 取候选位置的输出，投影到行为维度
        # ==========================================
        candidate_start = 1 + config.history_seq_len
        candidate_output = output[:, candidate_start:, :]
        # [B, C, emb_size]
        
        logits = Linear(config.num_actions)(candidate_output)
        # [B, C, 19]
        
        return RecsysModelOutput(logits=logits)
```

> **类比**：整个过程就像一场"选秀评审"：
> 1. 评委（User）带着自己的偏好
> 2. 翻阅选手们的历史表现（History）
> 3. 逐个审视每位参赛者（Candidate）
> 4. 给每位参赛者打出多维评分（19 种行为概率）

### 2. 19 种用户行为预测

PhoenixModel 预测每个候选帖子引发 19 种行为的概率：

#### 正面行为（高权重）

| 编号 | 行为 | 含义 | 信号强度 |
|------|------|------|---------|
| 1 | **favorite** | 点赞 ❤️ | ⭐⭐⭐ |
| 2 | **reply** | 回复 💬 | ⭐⭐⭐⭐ |
| 3 | **retweet** | 转发 🔁 | ⭐⭐⭐⭐ |
| 4 | **quote** | 引用转发 | ⭐⭐⭐ |
| 5 | **click** | 点击展开 | ⭐⭐ |
| 6 | **profile_click** | 点击作者主页 | ⭐⭐ |
| 7 | **video_view** | 观看视频 🎥 | ⭐⭐ |
| 8 | **photo_expand** | 展开图片 📷 | ⭐ |
| 9 | **share** | 分享 | ⭐⭐⭐ |
| 10 | **share_via_dm** | 通过私信分享 | ⭐⭐⭐ |
| 11 | **share_via_copy_link** | 复制链接分享 | ⭐⭐ |
| 12 | **dwell** | 停留阅读 | ⭐⭐ |
| 13 | **quoted_click** | 点击引用内容 | ⭐ |
| 14 | **follow_author** | 关注作者 | ⭐⭐⭐⭐⭐ |

#### 负面行为（负权重）

| 编号 | 行为 | 含义 | 信号强度 |
|------|------|------|---------|
| 15 | **not_interested** | 不感兴趣 | ⭐⭐ |
| 16 | **block_author** | 屏蔽作者 🚫 | ⭐⭐⭐⭐ |
| 17 | **mute_author** | 静音作者 🔇 | ⭐⭐⭐ |
| 18 | **report** | 举报 ⚠️ | ⭐⭐⭐⭐⭐ |

#### 连续值

| 编号 | 行为 | 含义 |
|------|------|------|
| 19 | **dwell_time** | 预测停留时长（秒） |

**为什么预测这么多行为？**

单一的"相关度"分数无法区分"用户不喜欢"和"用户不讨厌但也没兴趣"。多行为预测让系统可以：

1. **精细调权**：产品团队可以通过调整权重来影响信息流的"风格"
2. **优化目标灵活**：增加回复权重 → 信息流更鼓励讨论
3. **安全防护**：block/mute/report 的高预测值 → 主动降权

### 3. RecsysModelOutput 输出解读

```python
class RecsysModelOutput(NamedTuple):
    logits: jnp.ndarray  # [B, num_candidates, num_actions]
```

**从 logits 到概率：**

```python
# logits 是原始分数（可正可负）
logits = model(batch).logits  # [B, C, 19]

# 前 18 个行为用 sigmoid 转为概率  
probabilities = jax.nn.sigmoid(logits[:, :, :18])
# P(favorite), P(reply), ..., P(report) ∈ (0, 1)

# 第 19 个是连续值（dwell_time），不需要 sigmoid
dwell_time = logits[:, :, 18]
```

**为什么用 sigmoid 而不是 softmax？**

| softmax | sigmoid |
|---------|---------|
| 行为互斥（概率之和=1） | 行为独立（可以同时点赞+回复） |
| 不适合推荐场景 | ✅ 用户对一条帖子可以做多种行为 |

### 4. runners.py——模型初始化与推理

```python
# runners.py 的核心流程

def create_runner(config: PhoenixModelConfig):
    """创建模型推理器"""
    
    # 1. 初始化配置
    config.initialize()  # 计算派生参数
    
    # 2. 使用 Haiku transform 转为纯函数
    def forward(batch):
        model = PhoenixModel(config)
        return model(batch)
    
    transformed = hk.transform(forward)
    
    # 3. 初始化参数
    rng = jax.random.PRNGKey(42)
    sample_batch = create_sample_batch(config)
    params = transformed.init(rng, sample_batch)
    
    # 4. JIT 编译推理函数
    @jax.jit
    def predict(params, batch):
        return transformed.apply(params, rng, batch)
    
    return predict, params
```

**run_ranker.py 的 Demo 流程：**

```python
# 1. 配置模型
config = PhoenixModelConfig(
    model=TransformerConfig(
        emb_size=256,  # Demo 用小模型
        key_size=32,
        num_q_heads=8,
        num_kv_heads=2,
        num_layers=4,
    ),
    history_seq_len=50,     # 最近 50 条行为
    candidate_seq_len=10,   # 10 个候选
    num_actions=19,
)

# 2. 创建推理器
predict, params = create_runner(config)

# 3. 构造样例输入
batch = create_random_batch(config)

# 4. 推理
output = predict(params, batch)
print(output.logits.shape)  # (1, 10, 19)
# 10 个候选，每个有 19 维预测
```

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| PhoenixModel | 嵌入 → Reduction → 拼接 → Transformer → 取候选输出 → 投影 |
| 19 种行为 | 14 正面 + 4 负面 + 1 连续值，独立预测概率 |
| sigmoid | 行为独立，可以同时做多种行为 |
| runners.py | Haiku transform + JIT 编译 = 高效推理 |

---

## 📝 习题集9

**概念理解：**
1. 为什么推荐系统要预测"屏蔽作者"和"举报"的概率？这些负面行为预测如何影响排序？
2. `dwell_time` 为什么是连续值预测而不是概率？它如何参与最终评分？

**代码实践：**
3. 修改 `run_ranker.py`，将 `candidate_seq_len` 从 10 改为 1，观察输出 logits 的变化。
4. 在 Demo 中添加代码：将 logits 转为概率，打印每个候选的 Top-3 最可能行为。

**设计思考：**
5. 如果产品团队想让信息流"更多有深度的对话"，应该如何调整 19 种行为的权重？
6. 为什么 x-algorithm 选择在一个模型中预测所有行为，而不是每种行为训练一个独立模型？

---

> 下一课我们将学习 **L10 - Phoenix 检索模型：双塔架构**，了解 Out-of-Network 候选是如何被发现的。
