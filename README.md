# AP Physics 专项练习系统

每天自动获取 **AP Physics 1** 和 **Physics Bowl Division 1** 题目，保存到项目本地数据库，支持在线查询与专项练习。

## 功能特性

- 📚 **自动采集**：多源采集器框架，支持内置题库、网页/API 数据源扩展
- 🗄️ **本地数据库**：使用 SQLite 持久化存储，零额外部署成本
- ⏰ **每日定时**：内置调度器，每天自动获取新题目
- 🌐 **在线 API**：提供 REST API，随时在线获取题目进行练习
- 🎯 **专项练习**：区分 AP Physics 1 与 Physics Bowl D1 两个考试体系

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 首次初始化（抓取题库）

```bash
python scripts/fetch_once.py
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
│   ├── builtin/              # 内置题库
│   │   ├── ap_physics_1.json    # AP Physics 1 题库
│   │   └── physics_bowl_d1.json # Physics Bowl D1 题库
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
│   │   └── question.py       #   题目数据模型
│   └── services/
│       ├── fetch_service.py  #  抓取编排服务
│       └── scheduler.py      #  每日定时调度
├── scripts/
│   └── fetch_once.py         # 手动单次抓取
├── tests/                    # 测试用例
├── run.sh                    # 快捷启动脚本
├── Dockerfile                # 容器部署
└── requirements.txt          # Python 依赖
```

## 测试

```bash
pytest tests/ -v
```
