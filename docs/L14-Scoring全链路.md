# L14 - Scoring 全链路：从 ML 预测到最终排分

> **"四个评分器像接力赛跑——第一棒是 AI 预测，最后一棒是多样性调整，每一棒都不可或缺。"**

---

## 📌 本节目标

1. 掌握 PhoenixScorer 调用 Transformer 的过程
2. 理解 WeightedScorer 的加权组合公式
3. 了解 AuthorDiversityScorer 的衰减机制
4. 认识 OONScorer 的 Out-of-Network 调整
5. 熟悉 PhoenixScores 结构体

---

## 📚 前置知识

- L09 中的 Phoenix 排序模型
- L11 中的管道评分阶段

---

## 正文讲解

### 1. PhoenixScorer——AI 预测的入口

> **类比**：PhoenixScorer 就像给每个候选帖子做了一次"全面体检"——不是简单查个血压，而是同时检查 19 项指标。

```rust
pub struct PhoenixScorer {
    phoenix_client: Arc<PhoenixRankingClient>,
}

#[async_trait]
impl Scorer<ScoredPostsQuery, PostCandidate> for PhoenixScorer {
    fn name(&self) -> &str { "PhoenixScorer" }
    
    async fn score(&self, query: &ScoredPostsQuery, 
                   candidates: Vec<PostCandidate>) -> Vec<PostCandidate> 
    {
        // 1. 构建模型输入
        let model_input = build_phoenix_input(
            &query.user_action_sequence,  // 用户行为序列
            &candidates,                   // 候选帖子列表
        );
        
        // 2. 调用 Phoenix Transformer 模型
        let predictions = self.phoenix_client
            .predict(model_input)
            .await;
        // predictions: [num_candidates, 19]
        
        // 3. 填充预测分数到候选
        candidates.into_iter()
            .zip(predictions)
            .map(|(mut candidate, pred)| {
                candidate.phoenix_scores = PhoenixScores {
                    favorite_score:    Some(sigmoid(pred[0])),
                    reply_score:       Some(sigmoid(pred[1])),
                    retweet_score:     Some(sigmoid(pred[2])),
                    quote_score:       Some(sigmoid(pred[3])),
                    click_score:       Some(sigmoid(pred[4])),
                    profile_click_score: Some(sigmoid(pred[5])),
                    vqv_score:         Some(sigmoid(pred[6])),
                    photo_expand_score: Some(sigmoid(pred[7])),
                    share_score:       Some(sigmoid(pred[8])),
                    share_via_dm_score: Some(sigmoid(pred[9])),
                    share_via_copy_link_score: Some(sigmoid(pred[10])),
                    dwell_score:       Some(sigmoid(pred[11])),
                    quoted_click_score: Some(sigmoid(pred[12])),
                    follow_author_score: Some(sigmoid(pred[13])),
                    not_interested_score: Some(sigmoid(pred[14])),
                    block_author_score: Some(sigmoid(pred[15])),
                    mute_author_score: Some(sigmoid(pred[16])),
                    report_score:      Some(sigmoid(pred[17])),
                    dwell_time:        Some(pred[18]),
                };
                candidate.prediction_request_id = Some(pred.request_id);
                candidate.last_scored_at_ms = Some(now_ms());
                candidate
            })
            .collect()
    }
}
```

**PhoenixScores 结构体：**

```rust
pub struct PhoenixScores {
    // 正面行为（概率 0-1）
    pub favorite_score: Option<f64>,
    pub reply_score: Option<f64>,
    pub retweet_score: Option<f64>,
    pub quote_score: Option<f64>,
    pub click_score: Option<f64>,
    pub profile_click_score: Option<f64>,
    pub vqv_score: Option<f64>,
    pub photo_expand_score: Option<f64>,
    pub share_score: Option<f64>,
    pub share_via_dm_score: Option<f64>,
    pub share_via_copy_link_score: Option<f64>,
    pub dwell_score: Option<f64>,
    pub quoted_click_score: Option<f64>,
    pub follow_author_score: Option<f64>,
    
    // 负面行为（概率 0-1）
    pub not_interested_score: Option<f64>,
    pub block_author_score: Option<f64>,
    pub mute_author_score: Option<f64>,
    pub report_score: Option<f64>,
    
    // 连续值
    pub dwell_time: Option<f64>,
}
```

### 2. WeightedScorer——从 19 维到 1 维

```rust
pub struct WeightedScorer;

impl Scorer<ScoredPostsQuery, PostCandidate> for WeightedScorer {
    async fn score(&self, _query: &Q, candidates: Vec<PostCandidate>) 
        -> Vec<PostCandidate> 
    {
        candidates.into_iter()
            .map(|mut c| {
                let s = &c.phoenix_scores;
                
                let weighted_score = 
                    // 正面行为（正权重）
                      0.5  * s.favorite_score.unwrap_or(0.0)
                    + 1.0  * s.reply_score.unwrap_or(0.0)
                    + 11.0 * s.retweet_score.unwrap_or(0.0)
                    + 11.0 * s.quote_score.unwrap_or(0.0)
                    + 0.5  * s.click_score.unwrap_or(0.0)
                    + 0.5  * s.profile_click_score.unwrap_or(0.0)
                    + 0.01 * s.vqv_score.unwrap_or(0.0)
                    + 0.005* s.photo_expand_score.unwrap_or(0.0)
                    + 1.0  * s.share_score.unwrap_or(0.0)
                    + 1.0  * s.share_via_dm_score.unwrap_or(0.0)
                    + 1.0  * s.share_via_copy_link_score.unwrap_or(0.0)
                    + 0.1  * s.dwell_score.unwrap_or(0.0)
                    + 11.0 * s.follow_author_score.unwrap_or(0.0)
                    // 负面行为（负权重）
                    - 74.0 * s.not_interested_score.unwrap_or(0.0)
                    - 74.0 * s.block_author_score.unwrap_or(0.0)
                    - 74.0 * s.mute_author_score.unwrap_or(0.0)
                    - 74.0 * s.report_score.unwrap_or(0.0);
                
                c.weighted_score = Some(weighted_score);
                c.score = Some(weighted_score);
                c
            })
            .collect()
    }
}
```

**权重设计哲学：**

$$\text{Final Score} = \sum_{i \in \text{positive}} w_i \cdot P(\text{action}_i) - \sum_{j \in \text{negative}} w_j \cdot P(\text{action}_j)$$

| 权重层级 | 行为 | 权重 | 理由 |
|----------|------|------|------|
| **极高** | retweet, quote, follow | 11.0 | 最强的正面参与信号 |
| **高** | reply, share | 1.0 | 高质量互动 |
| **中** | favorite, click, profile_click | 0.5 | 轻度参与 |
| **低** | dwell, video_view, photo | 0.01-0.1 | 被动消费 |
| **极高负** | block, mute, report, not_interested | -74.0 | 必须强力压制 |

> 负面权重 (-74) 远大于正面权重绝对值——即使一条帖子 P(like)=0.9，只要 P(block)=0.02，最终分数也会被大幅拉低。

### 3. AuthorDiversityScorer——防止"刷屏"

> **类比**：如果信息流前 10 条都是同一个人发的，用户体验会很糟糕。AuthorDiversityScorer 就像"限流阀"——同一个作者的帖子，第二条打八折，第三条打六折…

```rust
pub struct AuthorDiversityScorer;

impl Scorer<ScoredPostsQuery, PostCandidate> for AuthorDiversityScorer {
    async fn score(&self, _query: &Q, mut candidates: Vec<PostCandidate>) 
        -> Vec<PostCandidate> 
    {
        // 按当前分数降序排列
        candidates.sort_by(|a, b| 
            b.score.partial_cmp(&a.score).unwrap());
        
        // 统计每个作者已出现的次数
        let mut author_count: HashMap<u64, usize> = HashMap::new();
        
        for candidate in candidates.iter_mut() {
            let count = author_count
                .entry(candidate.author_id)
                .or_insert(0);
            *count += 1;
            
            if *count > 1 {
                // 衰减公式：score *= 1 / count
                let attenuation = 1.0 / (*count as f64);
                candidate.score = candidate.score
                    .map(|s| s * attenuation);
            }
        }
        
        candidates
    }
}
```

**衰减效果：**

| 出现次数 | 衰减因子 | 效果 |
|----------|---------|------|
| 第 1 条 | 1.0 | 原始分数 |
| 第 2 条 | 0.5 | 分数减半 |
| 第 3 条 | 0.33 | 分数三分之一 |
| 第 4 条 | 0.25 | 分数四分之一 |

### 4. OONScorer——Out-of-Network 调整

```rust
pub struct OONScorer;

impl Scorer<ScoredPostsQuery, PostCandidate> for OONScorer {
    async fn score(&self, _query: &Q, candidates: Vec<PostCandidate>) 
        -> Vec<PostCandidate> 
    {
        candidates.into_iter()
            .map(|mut c| {
                if c.in_network == Some(false) {
                    // Out-of-Network 帖子分数微调
                    // 确保 OON 内容有机会进入 Top-K
                    // 但不会过度压制 In-Network 内容
                    c.score = c.score.map(|s| s * OON_BOOST_FACTOR);
                }
                c
            })
            .collect()
    }
}
```

OONScorer 的职责是**校准** In-Network 和 Out-of-Network 之间的分数尺度。由于两者来自不同 Source，原始分数的分布可能不同。

### 5. 四级评分链路总结

```
候选帖子
    │
    ▼
┌───────────────────────────────────────────────────┐
│ ① PhoenixScorer                                   │
│   输入: 用户行为历史 + 候选帖子信息                    │
│   输出: 19 维预测概率 (PhoenixScores)               │
│   延迟: ~80ms (Transformer 推理)                    │
└───────────────────┬───────────────────────────────┘
                    ▼
┌───────────────────────────────────────────────────┐
│ ② WeightedScorer                                   │
│   输入: 19 维预测                                    │
│   输出: 单一加权分数 (weighted_score)                 │
│   公式: Σ(w_i × P_i) - Σ(w_j × P_j)              │
│   延迟: <1ms                                        │
└───────────────────┬───────────────────────────────┘
                    ▼
┌───────────────────────────────────────────────────┐
│ ③ AuthorDiversityScorer                            │
│   输入: 加权分数 + 作者 ID                           │
│   输出: 多样性调整后的分数                            │
│   规则: 同一作者第 N 条 → score × 1/N               │
│   延迟: <1ms                                        │
└───────────────────┬───────────────────────────────┘
                    ▼
┌───────────────────────────────────────────────────┐
│ ④ OONScorer                                        │
│   输入: 调整后分数 + in_network 标记                  │
│   输出: OON 校准后的最终分数                          │
│   延迟: <1ms                                        │
└───────────────────┬───────────────────────────────┘
                    ▼
              最终排序分数
```

---

## 💡 本节小结

| Scorer | 输入→输出 | 核心逻辑 |
|--------|----------|---------|
| PhoenixScorer | 帖子 → 19维概率 | Transformer 推理 |
| WeightedScorer | 19维 → 1维分数 | 加权求和，负面行为强力惩罚 |
| AuthorDiversityScorer | 分数 → 衰减分数 | 同作者衰减 1/N |
| OONScorer | 分数 → 校准分数 | In/Out-Network 尺度对齐 |

---

## 📝 习题集14

**概念理解：**
1. WeightedScorer 中，`retweet` 的权重 (11.0) 为什么比 `favorite` (0.5) 高这么多？
2. 负面行为权重 -74.0 是如何确定的？改为 -10 会怎样？

**数学推导：**
3. 假设一条帖子的 P(favorite)=0.3, P(retweet)=0.1, P(block)=0.01，计算其 weighted_score。
4. 如果一个作者有 5 条帖子，分数分别是 10, 8, 6, 4, 2。经过 AuthorDiversityScorer 后，各条的分数是多少？

**设计思考：**
5. 为什么评分器要顺序执行而不是并行？如果 WeightedScorer 和 AuthorDiversityScorer 并行会怎样？
6. 如果产品团队想增加视频内容的曝光，应该调整哪些权重？

---

> 下一课我们将学习 **L15 - Selection 与 Post-Processing**。
