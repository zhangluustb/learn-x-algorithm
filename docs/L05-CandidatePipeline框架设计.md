# L05 - Candidate Pipeline 框架设计

> **"一个好的框架就像乐高积木——标准化的接口让你可以自由组合，构建出任何你想要的管道。"**

---

## 📌 本节目标

1. 理解 Pipeline Stage 枚举与执行顺序
2. 掌握六大核心 Trait 的接口设计
3. 区分并行与顺序执行策略
4. 了解 PipelineResult 结构与错误处理

---

## 📚 前置知识

- L03 中的 Rust trait 基础
- L04 中的项目结构

---

## 正文讲解

### 1. Pipeline Stage——管道的七个阶段

> **类比**：Candidate Pipeline 就像一条工厂流水线。原材料（候选帖子）从一端进入，经过清洗（过滤）、加工（补全）、质检（评分）、包装（选择），最终从另一端输出精品。

```rust
pub enum PipelineStage {
    QueryHydrator,          // 1. 丰富查询信息
    Source,                 // 2. 获取候选
    Hydrator,               // 3. 补全候选数据
    Filter,                 // 4. 过滤不合格候选
    Scorer,                 // 5. 打分排名
    PostSelectionHydrator,  // 6. 选后补全
    PostSelectionFilter,    // 7. 选后过滤
}
```

执行顺序是**固定的**——这保证了管道行为的可预测性：

```
QueryHydrator → Source → Hydrator → Filter → Scorer 
→ Selector → PostSelectionHydrator → PostSelectionFilter
→ SideEffect
```

### 2. 六大核心 Trait

#### 2.1 Source——候选生成

```rust
#[async_trait]
pub trait Source<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    fn enable(&self, query: &Q) -> bool { true }
    async fn get(&self, query: &Q) -> Vec<C>;
}
```

- **职责**：从数据源获取候选列表
- **并行执行**：多个 Source 同时运行
- **x-algorithm 实例**：`ThunderSource`（In-Network）、`PhoenixSource`（Out-of-Network）

> **类比**：Source 就像渔船——多艘船同时出海（并行），各自捕获不同的鱼（候选），最后在港口合并。

#### 2.2 Hydrator——数据补全

```rust
#[async_trait]
pub trait Hydrator<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    fn enable(&self, query: &Q) -> bool { true }
    async fn hydrate(&self, query: &Q, candidates: Vec<C>) -> Vec<C>;
}
```

- **职责**：为候选添加额外信息（不改变数量）
- **并行执行**：多个 Hydrator 同时运行
- **关键约束**：**必须保持候选数量和顺序不变**
- **x-algorithm 实例**：`CoreDataHydrator`、`GizmoduckHydrator`

#### 2.3 Filter——候选过滤

```rust
#[async_trait]
pub trait Filter<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    fn enable(&self, query: &Q) -> bool { true }
    async fn filter(&self, query: &Q, candidates: Vec<C>) 
        -> FilterResult<C>;
}

pub struct FilterResult<C> {
    pub kept: Vec<C>,       // 保留的候选
    pub removed: Vec<C>,    // 被移除的候选
}
```

- **职责**：将候选分为"保留"和"移除"两组
- **顺序执行**：每个 Filter 依次运行（后一个看到前一个的结果）
- **为什么顺序？** 过滤有依赖关系（先去重再检查年龄）

> **类比**：Filter 就像层层筛子——粗筛去大石头，细筛去沙子，每层筛掉不同类型的杂质。

#### 2.4 Scorer——评分排名

```rust
#[async_trait]
pub trait Scorer<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    fn enable(&self, query: &Q) -> bool { true }
    async fn score(&self, query: &Q, candidates: Vec<C>) -> Vec<C>;
}
```

- **职责**：为每个候选计算分数
- **顺序执行**：Scorer 依次运行（后一个可以基于前一个的分数再调整）
- **关键约束**：**必须保持候选数量和顺序不变**
- **x-algorithm 实例**：PhoenixScorer → WeightedScorer → AuthorDiversityScorer → OONScorer

#### 2.5 Selector——选择截断

```rust
#[async_trait]
pub trait Selector<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    async fn select(&self, query: &Q, candidates: Vec<C>) -> Vec<C>;
}
```

- **职责**：排序并取 Top-K
- **只有一个**：整个管道只有一个 Selector
- **x-algorithm 实例**：`TopKScoreSelector`

#### 2.6 SideEffect——副作用

```rust
#[async_trait]
pub trait SideEffect<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    async fn apply(&self, query: &Q, candidates: &[C]);
}
```

- **职责**：执行不影响结果的副作用（日志、缓存、监控）
- **Fire-and-forget**：不阻塞主流程

### 3. 并行 vs 顺序执行策略

| 阶段 | 执行方式 | 原因 |
|------|---------|------|
| QueryHydrator | **并行** | 各自获取独立数据，互不依赖 |
| Source | **并行** | 不同数据源独立查询 |
| Hydrator | **并行** | 各自补全不同字段 |
| Filter | **顺序** | 后续过滤器依赖前序结果 |
| Scorer | **顺序** | 后续评分器可能依赖前序分数 |
| Selector | **单一** | 只有一个选择器 |
| PostSelectionHydrator | **并行** | 同 Hydrator |
| PostSelectionFilter | **顺序** | 同 Filter |
| SideEffect | **Fire-forget** | 异步执行，不阻塞 |

### 4. PipelineResult 与执行引擎

```rust
pub struct PipelineResult<Q, C> {
    pub retrieved_candidates: Vec<C>,    // Source 阶段获取的全部候选
    pub filtered_candidates: Vec<C>,     // 被过滤掉的候选（可用于调试）
    pub selected_candidates: Vec<C>,     // 最终选出的候选
    pub query: Arc<Q>,                   // 最终的 Query（经过 hydration）
}
```

**执行引擎伪代码：**

```rust
async fn execute(query: Q) -> PipelineResult<Q, C> {
    // 1. 并行 hydrate query
    let query = join_all(query_hydrators.map(|h| h.hydrate(query))); 
    
    // 2. 并行获取候选
    let candidates = join_all(sources.map(|s| s.get(&query)))
        .flatten();
    
    // 3. 并行补全
    let candidates = join_all(hydrators.map(|h| h.hydrate(&query, candidates)));
    
    // 4. 顺序过滤
    let (kept, removed) = filters.fold(candidates, |c, f| f.filter(&query, c));
    
    // 5. 顺序评分
    let scored = scorers.fold(kept, |c, s| s.score(&query, c));
    
    // 6. 选择 Top-K
    let selected = selector.select(&query, scored);
    
    // 7. 选后补全 + 过滤
    let final_candidates = post_process(selected);
    
    // 8. 异步副作用
    spawn(side_effects.map(|se| se.apply(&query, &final_candidates)));
    
    PipelineResult { ... }
}
```

**错误处理策略：**
- 每个组件有 `enable()` 方法，可以条件性跳过
- 单个 Source 失败不会导致整个管道失败（其他 Source 继续）
- Filter/Scorer 失败会记录日志但尽量继续

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| Pipeline Stage | 固定的七阶段执行顺序，保证行为可预测 |
| Source | 并行获取候选，多数据源合并 |
| Filter | 顺序执行，将候选分为保留/移除 |
| Scorer | 顺序执行，逐步细化评分 |
| Selector | 排序截断，取 Top-K |
| 并行策略 | 无依赖的阶段并行，有依赖的阶段顺序 |

---

## 📝 习题集5

**代码阅读：**
1. 阅读 `candidate_pipeline.rs` 的 `execute()` 方法，列出所有使用 `join_all` 的并行阶段。
2. `FilterResult` 为什么同时保留 `kept` 和 `removed`？这对调试有什么帮助？

**设计思考：**
3. 如果将 Filter 也改为并行执行，会出现什么问题？举例说明。
4. 为什么 Hydrator 必须保持候选数量不变？如果 Hydrator 发现某个候选数据获取失败，应该怎么处理？
5. 对比 x-algorithm 的 Pipeline 框架和 Unix 管道（`cat | grep | sort`），找出设计理念的异同。

---

> 下一课我们将深入 **L06 - Thunder 实时帖子存储引擎**，了解 In-Network 候选的获取方式。
