# L04 - x-algorithm 项目导览

> **"磨刀不误砍柴工——在深入每个模块之前，先建立对项目全貌的清晰认知。"**

---

## 📌 本节目标

1. 掌握仓库目录结构与文件布局
2. 理解四大模块的依赖关系
3. 完成环境搭建与 Demo 运行
4. 追踪一次完整请求的数据流

---

## 📚 前置知识

- L01-L03 的内容
- Git 基本操作

---

## 正文讲解

### 1. 仓库目录结构解读

```
x-algorithm/
├── README.md                  # 项目总览与架构说明
├── LICENSE                    # Apache 2.0
├── CODE_OF_CONDUCT.md
│
├── candidate-pipeline/        # 🔧 通用管道框架（Rust）
│   ├── lib.rs                 #   模块导出
│   ├── candidate_pipeline.rs  #   核心执行引擎
│   ├── source.rs              #   Source trait
│   ├── hydrator.rs            #   Hydrator trait
│   ├── filter.rs              #   Filter trait
│   ├── scorer.rs              #   Scorer trait
│   ├── selector.rs            #   Selector trait
│   ├── side_effect.rs         #   SideEffect trait
│   └── query_hydrator.rs      #   QueryHydrator trait
│
├── thunder/                   # ⚡ In-Network 帖子存储（Rust gRPC）
│   ├── main.rs                #   服务启动
│   ├── lib.rs
│   ├── thunder_service.rs     #   gRPC 服务实现
│   ├── posts/
│   │   └── post_store.rs      #   内存帖子存储核心
│   ├── kafka/                 #   Kafka 事件消费
│   │   └── mod.rs
│   ├── deserializer.rs        #   事件反序列化
│   └── ...                    #   config, metrics 等
│
├── home-mixer/                # 🏠 编排层（Rust gRPC）
│   ├── main.rs                #   服务启动
│   ├── server.rs              #   ScoredPostsService
│   ├── candidate_pipeline/    #   管道配置
│   │   ├── phoenix_candidate_pipeline.rs  # 核心管道组装
│   │   ├── candidate.rs       #   PostCandidate 结构
│   │   ├── candidate_features.rs
│   │   ├── query.rs           #   ScoredPostsQuery
│   │   └── query_features.rs
│   ├── sources/               #   候选来源
│   │   ├── thunder_source.rs  #   In-Network
│   │   └── phoenix_source.rs  #   Out-of-Network
│   ├── candidate_hydrators/   #   5 个数据补全器
│   ├── filters/               #   12 个过滤器
│   ├── scorers/               #   4 个评分器
│   ├── selectors/             #   Top-K 选择器
│   ├── side_effects/          #   缓存副作用
│   └── query_hydrators/       #   Query 数据补全
│
└── phoenix/                   # 🐦 ML 模型（Python/JAX）
    ├── pyproject.toml         #   依赖：JAX, Haiku, NumPy
    ├── README.md              #   详细模型文档
    ├── grok.py                #   Transformer 核心架构
    ├── recsys_model.py        #   排序模型
    ├── recsys_retrieval_model.py  #   检索模型（双塔）
    ├── runners.py             #   模型初始化与推理
    ├── run_ranker.py          #   排序 Demo
    ├── run_retrieval.py       #   检索 Demo
    └── test_*.py              #   单元测试
```

### 2. 四大模块关系图

```
                    ┌──────────────────────┐
                    │     Home Mixer       │
                    │   (编排/gRPC 服务)    │
                    └──────┬───────────────┘
                           │
              ┌────────────┼────────────────┐
              │            │                │
              ▼            ▼                ▼
    ┌─────────────┐  ┌──────────┐   ┌───────────┐
    │  Candidate  │  │ Thunder  │   │  Phoenix   │
    │  Pipeline   │  │ (存储)   │   │  (ML模型)  │
    │  (框架)     │  └──────────┘   └───────────┘
    └─────────────┘
```

**依赖关系：**

| 调用方 | 被调用方 | 通信方式 |
|--------|---------|---------|
| Home Mixer | Candidate Pipeline | Rust crate 依赖（编译时） |
| Home Mixer | Thunder | gRPC |
| Home Mixer | Phoenix | gRPC / 进程内调用 |
| Thunder | Kafka | 消费者客户端 |

**数据流方向：**
1. 用户请求 → Home Mixer
2. Home Mixer 并行调用 Thunder + Phoenix Retrieval
3. 候选合并 → 通过 Candidate Pipeline 框架执行过滤/评分
4. Phoenix Scorer 调用 Phoenix Ranking 模型
5. 最终排好序的帖子 → 用户

### 3. 环境搭建与首次运行

#### 3.1 Python / Phoenix 环境

```bash
# 克隆仓库
git clone https://github.com/xai-org/x-algorithm
cd x-algorithm/phoenix

# 安装依赖（推荐用 uv）
pip install -e .
# 或
uv sync

# 运行排序 Demo
python run_ranker.py

# 运行检索 Demo  
python run_retrieval.py
```

`run_ranker.py` 会：
1. 创建 `PhoenixModelConfig` 配置
2. 初始化模型参数（随机权重，Demo 模式）
3. 构造样例输入（用户历史 + 候选帖子）
4. 运行前向传播，输出 19 维预测分数

`run_retrieval.py` 会：
1. 创建检索模型配置
2. 初始化双塔模型
3. 构造用户查询
4. 检索 Top-K 最相似的帖子

#### 3.2 Rust / Home Mixer & Thunder

```bash
# 需要 Rust toolchain
rustup install stable

# 编译（注意：完整编译需要额外依赖）
cd candidate-pipeline
cargo check  # 检查类型正确性
```

> **注意**：Rust 部分是生产代码骨架，依赖内部基础设施（Kafka、Strato、VF 服务等），无法直接在本地完整运行。我们主要阅读和分析其代码逻辑。

### 4. 数据流全链路追踪

让我们追踪一次 "用户张三打开 For You" 的完整请求：

```
Step 1: gRPC 请求到达 Home Mixer
┌─────────────────────────────────────────┐
│ ScoredPostsQuery {                      │
│   viewer_id: 12345,                     │
│   seen_ids: [100, 101, 102],           │
│   served_ids: [100],                    │
│   country_code: "US",                   │
│ }                                       │
└─────────────────────────────────────────┘
        │
        ▼
Step 2: Query Hydration（并行）
├── UserActionSeqHydrator: 获取张三最近 500 条行为
│   → 点赞了帖子A、回复了帖子B、转发了帖子C...
└── UserFeaturesHydrator: 获取张三关注的 200 个账号
        │
        ▼
Step 3: Candidate Sources（并行）
├── ThunderSource: 从 200 个关注账号获取近期帖子
│   → 返回 80 条 In-Network 候选
└── PhoenixSource: 双塔模型检索全局帖子
    → 返回 300 条 Out-of-Network 候选
        │
        ▼
Step 4: 合并 380 条候选
        │
        ▼
Step 5: Hydration（并行）
├── CoreDataHydrator: 获取帖子文本、创建时间
├── GizmoduckHydrator: 获取作者粉丝数、昵称
├── InNetworkHydrator: 标记哪些是关注用户的帖子
├── SubscriptionHydrator: 检查付费订阅状态
└── VideoDurationHydrator: 获取视频时长
        │
        ▼
Step 6: Filtering（顺序，10 个过滤器）
380 条 → 去重 → 去除无效数据 → 去除旧帖 
→ 去除自己的帖 → 转发去重 → 去除已看过的 
→ 去除已推送过的 → 关键词过滤 → 社交关系过滤
→ 剩余约 250 条
        │
        ▼
Step 7: Scoring（顺序）
├── PhoenixScorer: Grok Transformer 预测 19 种行为概率
├── WeightedScorer: 加权公式计算综合得分
├── AuthorDiversityScorer: 同一作者的帖子衰减
└── OONScorer: 调整 Out-of-Network 得分
        │
        ▼
Step 8: Selection
TopKSelector: 按分数排序，取 Top-50
        │
        ▼
Step 9: Post-Selection
├── VFFilter: 安全过滤（删除/垃圾/暴力内容）
└── DedupConversationFilter: 同一对话只保留一条
→ 最终约 45 条
        │
        ▼
Step 10: Side Effects
CacheRequestInfo: 记录预测结果供后续分析
        │
        ▼
📱 张三看到 45 条精心排序的帖子
```

---

## 💡 本节小结

| 内容 | 要点 |
|------|------|
| 目录结构 | 4 个顶层目录对应 4 大模块，各司其职 |
| 模块关系 | Home Mixer 编排全局，调用 Thunder + Phoenix |
| Demo 运行 | `run_ranker.py` / `run_retrieval.py` 可直接体验 |
| 数据流 | 10 步从请求到信息流：Query → Source → Hydrate → Filter → Score → Select |

---

## 📝 习题集4

**代码阅读：**
1. 运行 `run_ranker.py`，观察输出中 19 维 logits 的含义。哪些 action 的预测值较高？
2. 阅读 `candidate-pipeline/candidate_pipeline.rs` 的 `execute()` 方法，画出执行流程图。

**设计思考：**
3. 为什么 Filtering 阶段要分 Pre-Selection 和 Post-Selection 两次？各自负责什么类型的过滤？
4. 从 380 条候选到最终 45 条，每个阶段大约过滤掉多少比例？这种漏斗设计的优势是什么？

**动手实践：**
5. 修改 `run_ranker.py`，将候选数从默认值改为 1，观察输出变化。
6. 在 `run_retrieval.py` 中，修改 Top-K 参数，观察检索结果的变化。

---

> 下一课我们将深入 **L05 - Candidate Pipeline 框架设计**，解析这个精妙的通用推荐管道框架。
