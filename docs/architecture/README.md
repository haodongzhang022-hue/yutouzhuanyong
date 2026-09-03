# 📐 题库「专项·试卷」组织架构（TPQ）

> 面向 AP Physics 1 / Physics Bowl D1 题库的**人机双读**组织方案。
> 解决「现在只有机器可读的 JSON，人类看不到『像试卷那样的一道道题』、也找不到『按知识点组织的专项练习』」的问题。

---

## 1. 一句话方案

把题库从 **"一维平铺的记录流"** 重构成 **"Topic(知识点)→ Paper(专项试卷)→ Question(单题)" 三层**：

- **Question 层**：每道题 = 一份规范化对象，带唯一题号、统一类型编码、所属知识点编码。
- **Paper 层**：每个知识点生成一份**专项练习试卷**（人类直接可读可做的 Markdown，卷内逐题编号，题目卷与解析卷分离）。
- **Topic 层**：一张**知识点目录**（编码 + 中文名 + 所属模块 + 题型构成 + 难度梯度），是"知识点↔题"一一对应的枢纽，也是人/AI 检索的入口。

**机可读**走规范化 JSON（保留并沉淀现有采集存储）；**人可读**走按知识点渲染的 Markdown/HTML 试卷；两者由统一的 Schema 与知识点目录绑定，永不脱节。

---

## 2. 为什么现在的"不行"

| # | 现状问题 | 人看到的后果 |
|---|---------|------------|
| 1 | 题库是 `data/builtin/*.json` 平铺记录，每题是字段对象 | 只有"代码"，没有"试卷排版"，无法当题做 |
| 2 | 题目没有卷号、册号、卷内题号 | 无法像试卷定位"第几卷第几题" |
| 3 | topic 用零散英文枚举，且**同名不同码**（AP 的 gravity vs PB 的 gravitation；electric_forces vs electric_fields；momentum vs impulse_momentum） | 无法建立统一的"知识点↔题"一一对应 |
| 4 | external_id 前缀语义与 topic 不一致（如 app1-w001 是 waves、app1-w001b/w002 却是 work_energy） | 编号不可信、无法靠 id 推断归属 |
| 5 | 没有"专项练习册"产物，采集到即入库即完 | 每个知识点下有多少题、要不要针对某知识点刷题，无出口 |

---

## 3. 三层数据契约（Schema）

### 3.1 Question —— 单题规范化对象

```jsonc
{
  "qid": "AP1-KP01-Q02",              // 规范化题号：考试-知识点-序号（人机唯一）
  "exam": "ap_physics_1",             // 考试体系枚举
  "kp_code": "KP01",                  // 知识点编码（见 Topic 层）
  "kp_name": "运动学 Kinematics",
  "type": "mc",                        // 题型类型编码：mc 单选 / fr 解答
  "difficulty": "medium",             // easy/medium/hard
  "stem": "小球以 20 m/s 竖直上抛……(原题文本)",   // 题干，可含公式/图占位
  "options": ["A. ...", "B. ...", ...],        // 选择题选项；解答题为空
  "answer": "B",                       // 标准答案（纸卷作答时隐藏）
  "key_points": ["v=v₀-gt", "竖直上抛最高点速度为零"],
  "explanation": "……解析……",
  "source_ref": "app1-k001",           // 保留原始采集 id（溯源）
  "paper_ref": "paper_AP1_KP01"        // 归属于哪份专项练习卷
}
```

### 3.2 Topic —— 知识点目录（Knowledge Point Catalog）

每个考试体系一张目录，作为"知识点↔题 一一对应"的枢纽：

| 字段 | 说明 |
|------|------|
| `kp_code` | 知识点编码（跨考试唯一索引，可归并同义概念） |
| `kp_name` | 中文名 |
| `kp_name_en` | 英文/原名 |
| `module` | 所属大模块（如 力学/电磁/热/波光/近代） |
| `aliases` | 同义词归并（gravity/gravitation 都归 KP-grav） |
| `qids` | 该知识点下的题目 qid 列表（一一对应） |
| `paper_ref` | 生成的专项练习卷文件 |
| `difficulty_spread` | 难度分布（easy/medium/hard 各几题） |

### 3.3 Paper —— 专项练习卷

每知识点一份、每考一卷按卷生成。内容含：
- 卷头（考试 / 知识点 / 题型分布 / 难度 / 建议用时 / 题量）
- 题目区：逐题（卷内编号 1..N），隐藏答案 → 用于真实作答
- 解析区（可分文件）→ 用于对答案复盘

---

## 4. 双模检索

- **人类（按知识点刷题 / 打试卷）**：`试卷目录索引` 按考试 → 模块 → 知识点 → 专项卷 → 逐题。
- **AI / 系统（按类型找题）**：三种索引维度全走规范编码：
  1. 按 `kp_code` 知识点 → 返回该知识点全部题
  2. 按 `type` 题型类型 → 返回 mc / fr 分组
  3. 按 `difficulty` 难度 → easy/medium/hard

---

## 5. 目录规划（落地目标）

```
data/
  builtin/                       # 采集原始题库（保留）
  catalog/
    ap_physics_1.knowledge.yaml  # AP 知识点目录（含归并 aliases）
    physics_bowl_d1.knowledge.yaml
  papers/                        # ★ 生成的专项练习卷（人可读）
    ap_physics_1/
      kinematics_运动学.md        # 试卷题面（隐藏答案）
      kinematics_运动学.answer.md # 解析卷
      INDEX.md                    # 该考试试卷目录索引
    physics_bowl_d1/
      INDEX.md
src/
  organization/                  # ★ 新增组织层（取代只入库不组织）
    kp_catalog.py                # 知识点目录加载/归并
    topic_index.py               # 知识点↔题 双向索引
    paper_renderer.py            # 题目 → 试卷 Markdown 渲染
    question_normalizer.py       # 题号/类型/topic 规范化
scripts/
  organize_bank.py               # 一键：规范化 + 建索引 + 生成全部专项卷
docs/architecture/               # 本文档
```

---

## V2 框架蓝本（框架完善 / 基建文档 / 团队设计）

> 把"可用原型"提升为**可演进、可观测、可多人并行开发**的生产级框架。
> 方法论：先粗纲 → 功能模块 → 细纲；配套团队规模设计供经理排期。

| 层级 | 文档 | 内容 |
|------|------|------|
| 粗纲 | [v2_00 总体架构v2](./v2_00_粗纲_总体架构v2.md) | 五层架构 + 横向三件套 + 设计决策 D/R |
| 功能模块 | [v2_02 功能模块地图](./v2_02_功能模块地图.md) | 8 模块职责 + 接口契约 + 数据流 |
| 细纲 | [v2_03 数据模型与Schema](./v2_03_细纲_数据模型与Schema.md) | 表结构 / 编码 / 迁移 |
| 细纲 | [v2_04 API契约](./v2_04_细纲_API契约.md) | 统一错误码 / 端点 / 参数 |
| 细纲 | [v2_05 组织与专项卷流水线](./v2_05_细纲_组织与专项卷生产流水线.md) | 增量重建 / 版本化 / 一致性 |
| 细纲 | [v2_06 观测运维与生命周期](./v2_06_细纲_观测运维与生命周期.md) | 日志 / 健康 / 指标 / 停机 |
| 细纲 | [v2_07 配置与部署](./v2_07_细纲_配置与部署.md) | 配置分层 / 运行模式 / 部署 |
| 团队 | [team/team_scaling](../team/team_scaling.md) | 团队规模 / RACI / 里程碑排期 |

> 蓝图用于**经理按模块安排开发**、架构总师把关。

---

## NPC 协作 / 子组织适配（Issue #2）

> 子组织（subgroup）环境下 `@` 自动补全 / star / 互相 @ 协作失效的适配方案。
> 根因：两级 `@org/repo` 命名空间模型装不下 `org/subgroup/repo` 三级仓库路径。

| 文档 | 说明 |
|------|------|
| [npc/README](../npc/README.md) | NPC 子组织协作适配目录入口 |
| [npc/subgroup_@_adaptation.md](../npc/subgroup_@_adaptation.md) | 根因诊断 + 适配方案 |
| [npc/resolver.subgroup.patched.py](../npc/resolver.subgroup.patched.py) | resolver 三级路径修复补丁（交接 `dongjiagoushi` 合入） |
| [npc/settings.subgroup.example.yml](../npc/settings.subgroup.example.yml) | 子组织仓库 NPC 团队角色声明骨架 |
| [npc/selftest_subgroup.sh](../npc/selftest_subgroup.sh) | 解析器自检脚本 |
