# AP Physics 专项练习系统

每天自动获取 **AP Physics 1** 和 **Physics Bowl Division 1** 题目，保存到项目本地数据库，支持在线查询与专项练习。

## 功能特性

- 📚 **自动采集**：多源采集器框架，支持内置题库、网页/API 数据源扩展
- 🗄️ **本地数据库**：使用 SQLite 持久化存储，零额外部署成本
- ⏰ **每日定时**：内置调度器，每天自动获取新题目
- 🌐 **在线 API**：提供 REST API，随时在线获取题目进行练习
- 🎯 **专项练习**：区分 AP Physics 1 与 Physics Bowl D1 两个考试体系

## 🧭 架构蓝图（V2 框架完善 / 基建文档 / 团队设计）

本仓库已进入 **V2 框架完善**：把"可用原型"提升为可演进、可观测、可多人并行开发的生产级框架，
并按"先粗纲→功能模块→细纲"产出基建文档，配套团队规模设计供经理排期。

| 文档 | 说明 |
|------|------|
| `docs/architecture/v2_00_粗纲_总体架构v2.md` | 粗纲：五层架构 + 横向三件套 + 设计决策 |
| `docs/architecture/v2_02_功能模块地图.md` | 8 个功能模块职责 + 接口契约 |
| `docs/architecture/v2_03~v2_07` | 细纲：Schema / API / 流水线 / 运维 / 部署 |
| `docs/team/team_scaling.md` | 团队规模、RACI、里程碑排期 |



## 专项练习卷组织（新增）

默认抓取入库的 JSON 是**机器可读的一维记录**，适合程序消费，但不够像人看的试卷。
本项目在原有采集/API 基础上新增 **「知识点专项练习卷」组织层**：把每道题按知识点归组，
渲染成**像学生试卷那样逐题排版**的 Markdown，方便直接刷题。

- 🎯 每个知识点 = 一份**专项练习卷**（如「运动学专项练习」）
- 🧾 每题隐藏答案的**题目卷** + 单独**解析卷**，作答与复盘分离
- 🧭 按 **知识点 / 题型(mc·fr) / 难度** 三维索引，AI 或系统可任意组合检索
- 🗂️ 统一知识点目录 `data/catalog/knowledge_points.yaml`，完成 topic → 知识点码归并

> 📄 组织层设计文档见 `docs/architecture/`；一键生成命令见下方「生成专项练习卷」。

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 首次初始化（抓取题库）

```bash
python scripts/fetch_once.py
```

### 生成专项练习卷（按知识点组织成试卷）

把内置题库按**知识点**渲染成人类可读的专项练习卷（Markdown），
输出到 `data/papers/`（含每知识点题目卷 + 解析卷 + `INDEX.md` 目录 + `ai_index.json`）：

```bash
# 组织全部考试
python scripts/organize_bank.py

# 只处理指定考试 / 指定输出目录
python scripts/organize_bank.py --exam ap_physics_1
python scripts/organize_bank.py --outdir data/papers
```

产物示例：
```
data/papers/ap_physics_1/
  INDEX.md                                  # 专项练习目录（人浏览入口）
  ap_physics_1_KP01_Kinematics.md           # 运动学·题目卷（隐藏答案）
  ap_physics_1_KP01_Kinematics.answer.md    # 运动学·解析卷
  ai_index.json                             # 结构化索引（AI 按类型检索）
```

### 启动在线 API 服务

```bash
python -m src.main --mode api --port 8080
```

服务启动后自动立即执行一次题目抓取，随后每天定时抓取。

### 仅运行定时调度器（无 API）

```bash
python -m src.main --mode scheduler
```

## API 接口文档

### 1. 健康检查

```http
GET /api/health
```

### 2. 题库统计

```http
GET /api/stats
```

返回各考试类型题目数量及最近抓取日志。

### 3. 获取题目列表

```http
GET /api/questions?exam_type=ap_physics_1&limit=10&offset=0&topic=kinematics&difficulty=medium
```

### 4. 获取单道题

```http
GET /api/questions/{id}
```

返回题目详情（含答案、解析）。

### 5. 获取每日练习题目（专项练习模式）

```http
GET /api/daily/ap_physics_1?count=5&practice_mode=true
GET /api/daily/physics_bowl_d1?count=5&practice_mode=true
```

`practice_mode=true` 时隐藏答案，用于真实做题。
`practice_mode=false` 时显示答案与解析。

### 6. 手动触发抓取

```http
POST /api/fetch
Content-Type: application/json

{"exam_types": ["ap_physics_1"], "count": 5}
```

### 7. 强制全量采集

```http
POST /api/fetch/all
```

拉取当前配置下所有可用的题目。

### 8. 查看采集日志

```http
GET /api/logs?limit=20
```


### 9. 练习闭环（V2 · 作答会话 / 判分 / 错题本）

```http
# 开一个作答会话（下发题干，隐藏答案）
POST /api/practice/session
Content-Type: application/json
{"user_key":"u1","exam_type":"ap_physics_1","kp_code":"KP01",
 "type":"mc","difficulty":"medium","count":5}
→ data:{ session_id, count, questions:[{question_id, question_text, options,...}] }

# 提交整卷判分（自动记录作答 + 收录错题）
POST /api/practice/session/{session_id}/submit
{"user_key":"u1","answers":[{"question_id":1,"user_answer":"A"}, ...]}
→ data:{ total, correct, score, mistakes:[ids], results:[{...correct,correct_answer,explanation}] }

# 错题本（默认只看未掌握）
GET /api/practice/mistakes?user_key=u1&exam_type=&pending=true
# 复习/掌握错题
POST /api/practice/mistakes/{question_id}/review
{"user_key":"u1","mastered":true}

# 进度统计
GET /api/practice/stats?user_key=u1
→ data:{ total_attempts, correct_attempts, accuracy, by_exam, mistakes_pending, ... }
```

### 10. 学习计划（V2）

```http
GET  /api/study/plans?user_key=u1
POST /api/study/plans
{"user_key":"u1","exam_type":"ap_physics_1","kp_code":"KP01",
 "difficulty":"medium","daily_target":5}
DELETE /api/study/plans/{plan_id}?user_key=u1     # 停用计划
```

### 11. 专项卷重建与构建登记（V2）

```http
# 手动触发某考试专项卷重建（落盘 data/papers + 登记 paper_run）
POST /api/rebuild/papers
{"exam_type":"ap_physics_1"}

# 查看专项卷构建历史
GET /api/papers/runs?exam_type=&limit=10
```

> 采集器每抓取到**新题**会自动触发受影响考试专项卷增量重建（见 `fetch_service`），
> 无需人工干预。

## 配置说明

配置文件位于 `config/settings.yaml`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `scheduler.daily_fetch_time` | 每日抓取时间 | `08:00` |
| `scheduler.daily_fetch_count` | 每次抓取题量 | `5` |
| `collectors.ap_physics_1.sources` | AP 物理1 数据源 | 内置题库 |
| `collectors.physics_bowl_d1.sources` | 物理碗 D1 数据源 | 内置题库 |

### 添加新的数据源

支持 **内置题库**、**在线 JSON API**、**网页采集器** 三种方式：

**内置题库**（本地静态题库，稳定可靠）：

```yaml
collectors:
  ap_physics_1:
    sources:
      - name: "题库A"
        type: "builtin"
        path: "data/builtin/ap_physics_1.json"
```

**在线 JSON API 采集器**（从标准 JSON API 获取）：

```yaml
collectors:
  ap_physics_1:
    sources:
      - name: "在线题库"
        type: "json_api"
        url: "https://api.example.com/questions?category=ap-physics-1"
        data_path: "questions"      # 题目数组所在字段路径，默认 'questions'
        headers:
          Authorization: "Bearer token"  # 如有需要
```

支持 API 返回格式：
- 直接返回数组：`[{"question_text": "...", "correct_answer": "A", ...}]`
- 返回包装对象：`{"questions": [...], "data": [...]}`

**网页采集器**（需自定义解析器）：

```yaml
collectors:
  ap_physics_1:
    sources:
      - name: "网页题库"
        type: "web"
        url: "https://example.com/questions"
        module: "my_collector_module"
```

其中 `my_collector_module.py` 需定义 `collector` 类，继承 `WebCollector` 并实现 `_parse()` 方法。

## 数据库说明

数据存储于 `data/physics_bank.db`（SQLite 文件）。

主要表：
- `questions`：题目表（含题型、主题、难度、选项、答案、解析）
- `fetch_logs`：每日抓取日志

## 项目结构

```
├── config/settings.yaml       # 系统配置
├── data/
│   ├── builtin/              # 内置题库（采集原始数据）
│   │   ├── ap_physics_1.json
│   │   └── physics_bowl_d1.json
│   ├── catalog/              # 知识点目录（topic→kp 归并）
│   │   └── knowledge_points.yaml
│   ├── papers/               # ★ 生成的人读专项练习卷
│   │   ├── ap_physics_1/
│   │   └── physics_bowl_d1/
│   └── physics_bank.db       # SQLite 数据库（运行时生成）
├── src/
│   ├── __init__.py
│   ├── main.py               # 程序入口
│   ├── paths.py              # 路径配置
│   ├── api/
│   │   └── server.py         # Flask API 服务
│   ├── collectors/           # 采集器框架
│   │   ├── base.py           #   采集器基类
│   │   ├── builtin_collector.py
│   │   ├── web_collector.py
│   │   └── factory.py        #   采集器工厂
│   ├── models/
│   │   ├── database.py       #   SQLite 数据库操作
│   │   ├── question.py       #   题目数据模型
│   │   └── migrations/       # ★ Schema 迁移框架（v0/v1→v2）
│   │       ├── __init__.py         #  迁移运行器（user_version）
│   │       └── v002_schema_v2.py   #  kp/norm列 + 练习/卷表
│   ├── organization/        # ★ 题库组织层（新增：平铺JSON → 专项卷）
│   │   ├── kp_catalog.py         #  知识点目录加载与 topic→kp 归并
│   │   ├── question_normalizer.py#  题号/题型/topic 规范化
│   │   ├── topic_index.py        #  知识点↔题↔难度 双向索引
│   │   └── paper_renderer.py     #  题目 → 专项练习卷 Markdown 渲染
│   ├── core/                # V2 基础框架（配置/日志/指标/生命周期）
│   └── services/
│       ├── fetch_service.py  #  抓取编排服务
│       ├── scheduler.py      #  每日定时调度
│       ├── paper_builder.py  # ★ M3 专项卷生产+卷登记（可被API/调度调用）
│       └── practice/         # ★ M4 练习闭环（会话/判分/错题/计划）
│           └── service.py
├── scripts/
│   ├── fetch_once.py         # 手动单次抓取
│   └── organize_bank.py      # ★ 一键生成知识点专项练习卷
├── tests/                    # 测试用例
├── run.sh                    # 快捷启动脚本
├── Dockerfile                # 容器部署
└── requirements.txt          # Python 依赖
```

## 测试

```bash
pytest tests/ -v
```
