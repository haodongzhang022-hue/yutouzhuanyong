# V2 框架蓝本 · 03 · 细纲：数据模型与 Schema

> 数据契约是各层间的唯一纽带。本章定义 V2 全部表结构、索引列与迁移约定。
> 原则：**只读派生**（组织/卷由 builtin+主表派生，可重建）；**Schema 版本化可迁移**。

---

## 1. 数据库与迁移约定

- 存储：SQLite 单文件 `data/physics_bank.db`（WAL 模式，已启用）。
- 引入 `PRAGMA user_version` 作为 schema 版本，启动时按版本号执行增量迁移脚本（见 M1 交付物 `src/models/migrations.py`）。
- 迁移脚本：`src/models/migrations/`，命名 `v{n:03d}_{描述}.sql`，只增不改。

| 版本 | 说明 |
|------|------|
| v1 | 现结构（questions/fetch_logs）基线 |
| v2 | questions 加组织索引列 + 新增 practice/papers 相关表（本蓝图） |

---

## 2. 主表设计

### 2.1 `questions`（题表，v1 已有 + v2 增列）

| 列 | 类型 | 说明 | v2 变更 |
|----|------|------|---------|
| id | INTEGER PK AUTOINCREMENT | 主键 | 不变 |
| exam_type | TEXT NOT NULL | ap_physics_1 / physics_bowl_d1 | 不变 |
| question_type | TEXT | mc/fr | 建议归一为短码(mc/fr) |
| source | TEXT | 来源 | 不变 |
| external_id | TEXT | 源题号 | 不变 |
| topic | TEXT | 原始 topic | 保留（溯源） |
| **kp_code** | TEXT | 归并后知识点码 | **新增**，建索引 |
| **kp_name** | TEXT | 知识点中文名冗余 | **新增** |
| **norm_type** | TEXT | mc/fr 短码 | **新增** |
| **norm_qid** | TEXT | 规范化题号 EXAM-KPxx-Qn | **新增**，UNIQUE |
| difficulty | TEXT | easy/medium/hard | 不变 |
| question_text / options / correct_answer / explanation | TEXT | 题内容 | 不变 |
| created_at | TEXT | 时间 | 不变 |

> 说明：kp 相关列是**组织层回填的派生列**，由 M2 在入库/重建时刷新，让组织查询走索引避免全量重扫。

### 2.2 `fetch_logs`（采集日志，已有）
- 增加可选 `request_id` 列以便关联一次调度的多源日志。

### 2.3 `paper_runs`（专项卷构建登记，v2 新增，M3）
| 列 | 说明 |
|----|------|
| id | PK |
| exam_type | 考试 |
| trigger | full / incremental / manual |
| built_at | 构建时间 |
| total_papers | 本次产卷数 |
| status | success/partial/failed |
| message | 备注 |
| git_or_version | 产物快照标记 |

### 2.4 `practice_attempts`（作答记录，v2 新增，M4）
| 列 | 说明 |
|----|------|
| id | PK |
| question_id | FK→questions.id |
| session_id | 作答会话 |
| user_key | 用户标识（未上登录前可为匿名/设备号） |
| submitted_at | 提交时间 |
| user_answer | 用户选择/文本 |
| is_correct | 0/1 |
| response_ms | 用时(ms) |

### 2.5 `mistakes`（错题本，v2 新增，M4）
| 列 | 说明 |
|----|------|
| id | PK |
| user_key | 用户 |
| question_id | FK |
| added_at | 收录时间 |
| review_count / mastered | 复习次数 / 是否掌握 |

### 2.6 `study_plans`（学习计划，v2 新增，M4）
| 列 | 说明 |
|----|------|
| id | PK |
| user_key | 用户 |
| exam_type | 考试 |
| kp_code / difficulty | 目标筛选 |
| daily_target | 每日目标题量 |
| enabled | 启停 |
| created_at | 时间 |

> 学习/练习相关用户字段：**不引入强鉴权**（MVP 可匿名 user_key），待接入真实账号体系再统一。

---

## 3. 统一编码规范（承接 V1，固化）

| 维度 | 编码 | 取值 |
|------|------|------|
| 考试 exam | 小写下划线 | `ap_physics_1` / `physics_bowl_d1` |
| 题型 type | 短码 | `mc` / `fr` |
| 难度 difficulty | 小写 | `easy` / `medium` / `hard` |
| 知识点 kp_code | 稳定码 | `KP01`..`KP16`（见知识点目录，不得改名） |
| 规范化题号 qid | 组合 | `{EXAM}-{kp_code}-Q{nn}`，EXAM 用 AP1/PB |

---

## 4. 知识点目录（M8 维护物）

见 `data/catalog/knowledge_points.yaml`（V1 已落地 16 个 kp，跨考试同义归并）。
V2 扩展目录字段（可选，渐进）：
- `syllabus`：所属考纲章节编号
- `prereq`：前置知识点
- `tags`：标签，便于跨模块语义检索

---

## 5. 数据一致性原则

1. 主数据源 = `questions` 表（含 builtin 全量导入）；`data/builtin/*.json` 视为"题源快照"，不回写。
2. 组织派生（kp 列/索引/专项卷）为**可从主表重建**的冗余，出现漂移时以重建任务修复。
3. 卷登记表与文件系统产物以 `built_at + version` 对齐，避免"有文件没登记 / 有登记没文件"。
