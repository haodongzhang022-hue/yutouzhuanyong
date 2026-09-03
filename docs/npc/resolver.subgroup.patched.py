# -*- coding: utf-8 -*-
"""
自适应 @ 定位解析器 —— 子组织(subgroup/三级路径)适配补丁
========================================================
补丁对象：dongjiagoushi/local-agent/handle/resolver.py
目标：让 @ 引用 / 自动补全 / 跨仓库协作在「子组织」结构下正确解析。

背景（子组织路径 · Issue #2 适配）：
  CNB 存在两种仓库路径：
    - 二级（根组织）：org/repo                    → @org/repo(角色)
    - 三级（子组织）：org/subgroup/repo           → @org/subgroup/repo(角色)（权限按完整 slug）
  原 resolver 只按「org/repo 两段」切，喂入 `dongdongxiaozu/yutoujing/yutouzhuanyong`
  时会把子组织 yutoujing 误当 org（git remote 源）或把带 '/' 的 CNB_GROUP_SLUG 整个
  当 org（env 源），导致跨仓库判定与召唤 handle 出错 → star/自动补全/互相 @ 失效。

本文件给出「可变段数」命名空间模型，三级/二级双兼容，且保持原函数签名可用。

用法：把本文件整体替换原 resolver.py，或在原文件头部 import 本模块的分段函数覆盖。
"""

import os
import re

DEFAULT_ORG = "dongdongxiaozu"
DEFAULT_REPO = "dongjiagoushi"
DEFAULT_CODEBUDDY_ROLE = "CodeBuddy"

# 支持 @ 三级/两级触发串：`@org/subgroup/repo(角色)` / `@org/repo(角色)` / `@repo`
_AT_FULL3_RE = re.compile(
    r"@\s*(?P<slug>[\w.-]+(?:/[\w.-]+){1,2})\s*(?:\(\s*(?P<role>[^()]+?)\s*\))?"
)
_AT_SINGLE_RE = re.compile(r"@\s*(?P<name>[\w.-]+)")


def split_slug(slug):
    """把仓库路径 slug 按段数拆成语义化结构。

    输入 'a/b/c'  → {root:'a', group:'a/b', repo:'c', level:3}
    输入 'a/b'    → {root:'a', group:'a',  repo:'b', level:2}
    空/单段       → {root:slug, group:slug, repo:slug, level:1}
    """
    slug = (slug or "").strip().strip("/")
    if not slug:
        return {"root": None, "group": None, "repo": None, "level": 0}
    parts = slug.split("/")
    if len(parts) >= 3:
        root, group = parts[0], parts[0] + "/" + parts[1]
        repo = "/".join(parts[2:]) if len(parts) > 3 else parts[2]
        return {"root": root, "group": group, "repo": repo, "level": 3}
    if len(parts) == 2:
        return {"root": parts[0], "group": parts[0], "repo": parts[1], "level": 2}
    return {"root": parts[0], "group": parts[0], "repo": parts[0], "level": 1}


def _git_remote_slug():
    """从 git remote 提取**完整**仓库路径 slug（含子组织三级路径）。

    先剥离 scheme://host[:port]/ 与 git@host: 前缀，再取剩余路径 slug，
    避免 host 泄漏（如 cnb.cool/... 被误当 org）。支持 2 级与 3 级。
    """
    try:
        import subprocess
        out = subprocess.run(
            ["git", "remote", "-v"], capture_output=True, text=True,
            timeout=5, check=False,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            url = parts[1].strip()
            # 剥离协议与 host：https://host[:port]/、git@host:
            url = re.sub(r"^https?://[^/]+/", "", url)
            url = re.sub(r"^git@[^:]+:", "", url)
            # 剥离 .git 与末尾斜杠
            url = re.sub(r"\.git$", "", url)
            url = url.strip("/")
            # 只保留 2~3 段：org/repo 或 org/subgroup/repo
            m = re.fullmatch(r"[\w.-]+(?:/[\w.-]+){1,2}", url)
            if m:
                return m.group(0)
    return None


def _env_slug():
    """从环境变量提取**完整**仓库 slug，按权威度降序。"""
    for key in ("CNB_REPO_SLUG",):  # 最权威，天然三段
        v = os.environ.get(key)
        if v:
            return v
    org = os.environ.get("CNB_GROUP_SLUG") or os.environ.get("CNB_ROOT_SLUG")
    repo = os.environ.get("CNB_REPO_NAME")
    if org and repo:
        return f"{org}/{repo}"
    org = os.environ.get("CNB_ORG")
    repo = os.environ.get("CNB_REPO")
    if org and repo:
        return f"{org}/{repo}"
    return None


def detect_current_org_repo():
    """探测当前**操作仓库**的完整结构。返回兼容 dict：含原 org/repo + 新增 slug/group/root/level。

    探测顺序：env(完整 slug) → git remote(完整 slug) → 默认约定。
    """
    slug = _env_slug() or _git_remote_slug()
    if slug:
        info = split_slug(slug)
        return {
            "slug": slug,
            "root_org": info["root"],
            "group": info["group"],
            "org": info["group"],      # 兼容原字段：org = 子组织全路径(组)
            "repo": info["repo"],      # 真正的仓库名
            "level": info["level"],
        }
    return {
        "slug": f"{DEFAULT_ORG}/{DEFAULT_REPO}",
        "root_org": DEFAULT_ORG,
        "group": DEFAULT_ORG,
        "org": DEFAULT_ORG,
        "repo": DEFAULT_REPO,
        "level": 2,
    }


def parse_at(at_str):
    """解析 @ 触发串 → {slug, role, org, repo, level}，支持三级/两级。"""
    if not at_str:
        return None
    s = at_str.strip()
    m = _AT_FULL3_RE.search(s)
    if m:
        slug = m.group("slug")
        role = (m.group("role") or DEFAULT_CODEBUDDY_ROLE).strip()
        info = split_slug(slug)
        return {"slug": slug, "role": role, "level": info["level"],
                "org": info["group"], "repo": info["repo"]}
    m = _AT_SINGLE_RE.search(s)
    if m:
        name = m.group("name").strip()
        if "/" in name:
            info = split_slug(name)
            return {"slug": name, "role": DEFAULT_CODEBUDDY_ROLE,
                    "level": info["level"], "org": info["group"], "repo": info["repo"]}
        cur = detect_current_org_repo()
        return {"slug": f"{cur['org']}/{name}", "role": DEFAULT_CODEBUDDY_ROLE,
                "level": cur["level"], "org": cur["org"], "repo": name}
    return None


def format_at(org, repo, role=None, root_org=None):
    """按 org/repo(或 root/subgroup/repo) 生成标准 @ 格式。

    原 org 段若已含子组织('/')，则 org 即完整组路径，直接拼 repo。
    """
    role = role or DEFAULT_CODEBUDDY_ROLE
    org = (org or "").strip().strip("/")
    repo = (repo or "").strip().strip("/")
    if not org or not repo:
        return f"@{org or '?'}/{repo or '?'}({role})"
    return f"@{org}/{repo}({role})"


def format_at_slug(slug, role=None):
    """按完整 slug（含子组织）生成 @ 格式：`@org/subgroup/repo(角色)` 或 `@org/repo(角色)`。"""
    role = role or DEFAULT_CODEBUDDY_ROLE
    return f"@{slug}({role})"


def is_cross_repo(target_org=None, target_repo=None, current_org=None,
                  current_repo=None, target_slug=None, current_slug=None):
    """跨仓库判定。优先用完整 slug（避免子组织把 '/' 拆错）。

    - target_slug / current_slug 都给时，用 slug 字符串相等判定（最准）；
    - 否则回退到 org/repo 两段比较（兼容原逻辑）。
    """
    if target_slug and current_slug:
        return target_slug != current_slug
    c_org, c_repo = current_org, current_repo
    if not c_org or not c_repo:
        cur = detect_current_org_repo()
        c_org, c_repo = cur.get("org"), cur.get("repo")
    if target_org and target_org != c_org:
        return True
    if target_repo and target_repo != c_repo:
        return True
    return False


def resolve(at_str=None, target_org=None, target_repo=None, role=None,
            current_org=None, current_repo=None, target_slug=None, current_slug=None):
    """核心解析：返回可直接用于 @ 唤醒的标准 handle。

    子组织场景强烈建议走「完整 slug」：target_slug 用目标仓库 `org/subgroup/repo`，
    本函数据此生成 `@org/subgroup/repo(角色)`，保证被唤醒角色有目标仓库权限。
    """
    cur = detect_current_org_repo()
    c_slug = current_slug or cur["slug"]
    c_org = current_org or cur["org"]
    c_repo = current_repo or cur["repo"]

    trigger = parse_at(at_str) if at_str else None

    # 目标：显式 target_slug 最高优先；其次 target_org/target_repo；再次触发串；最后当前仓库
    if target_slug:
        t_slug = target_slug
        t_info = split_slug(t_slug)
        t_org, t_repo, t_role = t_info["group"], t_info["repo"], role or DEFAULT_CODEBUDDY_ROLE
    else:
        t_org = target_org or (trigger["org"] if trigger else None) or c_org
        t_repo = target_repo or (trigger["repo"] if trigger else None) or c_repo
        t_role = role or (trigger["role"] if trigger else None) or DEFAULT_CODEBUDDY_ROLE
        t_slug = f"{t_org}/{t_repo}"

    cross = is_cross_repo(t_org, t_repo, c_org, c_repo,
                          target_slug=t_slug, current_slug=c_slug)
    handle = format_at_slug(t_slug, t_role)

    if cross:
        note = (f"目标仓库 `{t_slug}` 与当前 `{c_slug}` 不同，属跨仓库/跨组织协作，"
                f"必须用目标仓库完整 @ `{handle}` 召唤，否则角色无目标仓库权限。")
    else:
        note = (f"目标仓库 `{t_slug}` 与当前一致，可复用本仓库 @ `{handle}`。")

    return {
        "trigger": trigger,
        "current": {"slug": c_slug, "org": c_org, "repo": c_repo},
        "target": {"slug": t_slug, "org": t_org, "repo": t_repo, "role": t_role},
        "handle": handle,
        "cross_repo": cross,
        "permission_note": note,
    }


resolve_handle = resolve

__all__ = [
    "DEFAULT_ORG", "DEFAULT_REPO", "DEFAULT_CODEBUDDY_ROLE",
    "split_slug", "detect_current_org_repo", "parse_at",
    "format_at", "format_at_slug", "is_cross_repo",
    "resolve", "resolve_handle",
]
