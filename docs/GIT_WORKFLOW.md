# Git 工作流规范（企业级）

> 适用：个人项目也要按企业规范走，因为**面试官会看你的 GitHub 历史**。
> 一个"每天 3 次规范提交、分支清晰、PR 有描述"的仓库，比 20 个 `update` 堆出来的仓库可信得多。

---

## 1. 分支模型

```
main      ●──────────●──────────────●──────────►  只放可发布版本（保护分支）
           ╲        ╱ ╲            ╱
develop     ●──●──●    ●──●──●──●──●             集成分支，随时可跑通
             ╲ ╱          ╲   ╱
feature/*     ●            ●                    功能分支，一天一合
```

| 分支 | 作用 | 规则 |
|---|---|---|
| `main` | 可发布 | **禁止直接提交**，只接受 `develop` 的 PR；每次合并打 tag |
| `develop` | 集成 | 允许小步提交；CI 必须绿 |
| `feature/<主题>` | 单个功能 | 从 `develop` 切出，完成后 PR 回 `develop` |
| `fix/<主题>` | 缺陷修复 | 同上 |
| `docs/<主题>` | 纯文档 | 同上 |
| `hotfix/<主题>` | 线上紧急修复 | 从 `main` 切出，修完同时合回 `main` 和 `develop` |

**个人项目简化版**：保留 `main` + `feature/*` 两条就够，但仍要走 PR（自己 approve 自己），目的是练出"有 PR 记录"的仓库。

### 分支命名

```
feature/hybrid-retrieval
feature/eval-60-cases
fix/log-signature-regex
docs/git-workflow
```

规则：`类型/短横线小写英文`，≤ 30 字符，别用中文、别用日期（日期在 commit 里）。

---

## 2. Commit 规范（Conventional Commits）

### 格式

```
<type>(<scope>): <subject>

<body 可选：为什么这么改，而不是改了什么>

<footer 可选：BREAKING CHANGE / Closes #12>
```

### type 取值

| type | 用途 | 例子 |
|---|---|---|
| `feat` | 新功能 | `feat(retrieval): add RRF fusion` |
| `fix` | 修缺陷 | `fix(logs): replace digits without word boundary` |
| `refactor` | 重构（行为不变） | `refactor(loop): extract terminator helpers` |
| `test` | 测试 | `test(registry): cover write-tool guard` |
| `docs` | 文档 | `docs(readme): add architecture diagram` |
| `chore` | 构建/依赖/配置 | `chore(ci): add python 3.12 matrix` |
| `perf` | 性能 | `perf(context): compress earlier tool messages` |

### subject 写法

- ✅ 祈使句、小写开头、不加句号：`add hybrid retrieval with RRF`
- ✅ 说清"做了什么"：`fix(logs): replace digits without word boundary`
- ❌ `update`、`fix bug`、`修改一下`、`提交`
- ❌ 一条 commit 塞 5 个不相关改动（拆开）

### 好的真实示例（本项目）

```
fix(logs): replace digits without word boundary

31850ms 里的数字后紧跟字母，\b 不成立导致替换失败，
签名无法聚合，top_signatures 每条 count 都是 1。

改为 \d+(\.\d+)? 后，同一异常聚合为一条，count=35。
影响：日志工具输出体积下降 60%，评测成功率 62.5% → 100%。
```

**为什么 body 要写"影响"**：半年后你自己回看、或面试官翻你的 commit，这行是最有价值的。

---

## 3. 首次连接 GitHub

### 3.1 在 GitHub 建仓库

1. 打开 https://github.com/new
2. Repository name：`ops-copilot`
3. 可见性：**Private**（求职期建议私有，等打磨好再转 Public；转 Public 前务必确认 `.env` 没进去）
4. **不要**勾选 "Add a README"（本地已有）
5. Create repository

### 3.2 本地初始化并关联

```powershell
cd D:\dsh_sessions\ops-copilot

# 1) 先确认忽略规则生效（极其重要）
git init
git add .gitignore
git commit -m "chore: add gitignore"

# 2) 关联远程（把 <you> 换成你的 GitHub 用户名）
git remote add origin https://github.com/<you>/ops-copilot.git

# 3) 首次推送
git branch -M main
git push -u origin main
```

### 3.3 认证方式（二选一）

**方式 A：Git Credential Manager（最省事，推荐）**

Git for Windows 自带。第一次 `git push` 时会弹出浏览器窗口让你登录 GitHub，登录后凭据会被记住。**什么都不用配。**

**方式 B：Personal Access Token（PAT）**

1. GitHub → 右上头像 → Settings → Developer settings
2. → Personal access tokens → **Tokens (classic)** → Generate new token (classic)
3. Note 填 `ops-copilot`，Expiration 选 90 天，勾选 **`repo`** 权限
4. 生成后复制 `ghp_xxxxxxxx`（只显示一次）
5. 用它当密码：

```powershell
git remote set-url origin https://<token>@github.com/<you>/ops-copilot.git
```

> ⚠️ 这会把 token 明文写进 `.git/config`。个人电脑可以，公用电脑别用。
> 更安全的做法：`git config --global credential.helper manager`，让它走方式 A。

**方式 C：SSH Key（长期最稳）**

```powershell
ssh-keygen -t ed25519 -C "2316727414@qq.com"      # 一路回车
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub   # 复制输出
# 粘贴到 GitHub → Settings → SSH and GPG keys → New SSH key
ssh -T git@github.com                              # 看到 "Hi <you>!" 即成功

git remote set-url origin git@github.com:<you>/ops-copilot.git
```

---

## 4. 每日同步流程（照做即可）

### 每天开工（2 分钟）

```powershell
cd D:\dsh_sessions\ops-copilot

git checkout develop
git pull --rebase            # 拉最新，rebase 保持历史线性

# 今天做什么就切什么分支
git checkout -b feature/eval-60-cases
```

### 开发中（每次完成一个可验证的小功能就提交）

```powershell
git status                          # 先看改了什么
git diff                            # 看具体改动
git add agent/tools/logs.py         # 只加相关文件，别偷懒用 git add .
git commit -m "fix(logs): replace digits without word boundary"
```

> **提交粒度标准**：这一次提交后，`pytest` 能过、程序能跑。不要把"写着写着报错"的中间态提交上去。

### 每天收工（3 分钟）

```powershell
git push -u origin feature/eval-60-cases
```

然后到 GitHub 页面：
1. 点 **Compare & pull request**
2. 标题按 commit 规范写
3. 描述按 `.github/PULL_REQUEST_TEMPLATE.md` 填（自测清单 + 指标变化）
4. 等 CI 绿 → **Squash and merge** → **Delete branch**

### 第二天重复

```powershell
git checkout develop
git pull --rebase
git branch -d feature/eval-60-cases     # 删本地已合并分支
```

---

## 5. PR 合并策略

| 策略 | 何时用 | 结果 |
|---|---|---|
| **Squash and merge**（默认） | 功能分支多个零碎 commit | 压成 1 个干净 commit 进 develop |
| Rebase and merge | commit 本身已规范 | 保留线性历史 |
| Merge commit | **不用** | 会产生大量"Merge branch..."噪音 |

---

## 6. 版本与 Tag

```powershell
# 里程碑：评测体系就绪
git checkout main
git merge --no-ff develop
git tag -a v0.1.0 -m "eval-ready: 60 scenarios, real-LLM baseline"
git push origin main --tags
```

版本含义：`0.1.0` = 主版本.次版本.修订号；`0.x` 阶段允许不兼容变更。

---

## 7. 救急命令速查

| 场景 | 命令 |
|---|---|
| 改错了还没 add | `git checkout -- <file>` |
| 已 add 想撤回暂存 | `git restore --staged <file>` |
| 想丢弃全部本地改动 | `git reset --hard HEAD`（**危险**） |
| 改最后一条 commit 信息 | `git commit --amend -m "新信息"` |
| 漏了文件想补进上次提交 | `git add <file>; git commit --amend --no-edit` |
| 写一半要切分支 | `git stash` → 切分支 → `git stash pop` |
| 提交到错的分支 | `git reset --soft HEAD~1`（撤销提交，改动保留） |
| 想看某文件历史 | `git log -p -- agent/tools/logs.py` |
| 想看谁改的某行 | `git blame -L 30,50 agent/tools/logs.py` |
| 回滚某次提交（生成反向提交） | `git revert <sha>`（**比 reset 安全**） |
| 误删已提交文件 | `git checkout HEAD~1 -- <file>` |

### 冲突解决

```powershell
git pull --rebase
# 出现 CONFLICT
git status                       # 看哪些文件冲突
# 打开文件，保留正确内容，删掉 <<<<<<< ======= >>>>>>> 标记
git add <file>
git rebase --continue
# 想放弃这次 rebase：
git rebase --abort
```

---

## 8. 每日 5 分钟同步脚本

保存为 `scripts/daily.ps1`：

```powershell
param([string]$Msg = "chore: daily sync")
$ErrorActionPreference = "Stop"
git add -A
git commit -m $Msg
$branch = git rev-parse --abbrev-ref HEAD
git push -u origin $branch
Write-Host "pushed branch: $branch" -ForegroundColor Green
```

用法：

```powershell
powershell -File scripts/daily.ps1 -Msg "feat(eval): extend to 60 scenarios"
```

---

## 9. 常见坑（都踩过）

| 坑 | 现象 | 解法 |
|---|---|---|
| **CRLF 换行符** | 每次 diff 全部文件都变了 | 加 `.gitattributes`：`* text=auto eol=lf` |
| **`.env` 泄漏** | token 被推到公开仓库 | 先提交 `.gitignore`；若已推，立刻撤销 token |
| **大文件** | push 卡死/仓库膨胀 | 别提交 `data/`、`*.db`、模型文件；`git rm --cached` |
| **force push 覆盖** | 别人/昨天的提交丢了 | `git push --force-with-lease` 而非 `--force`；个人仓库也尽量不用 |
| **提交了 `__pycache__`** | 一堆二进制噪音 | `.gitignore` 已包含；补救：`git rm -r --cached __pycache__` |
| **一次性 `git add .`** | 把临时文件也提交了 | 用 `git add -p` 或指定文件 |
| **merge 出大堆分支线** | 历史像地铁图 | 统一用 `pull --rebase` + squash merge |

---

## 10. 面试官会怎么看你的仓库

| 信号 | 说明 |
|---|---|
| ✅ 每天 3-6 次小提交 | 有持续投入，不是最后一天赶出来的 |
| ✅ commit body 写"为什么 + 影响" | 会思考，不是抄 |
| ✅ 有 PR、有 CI 徽章 | 有工程习惯 |
| ✅ 有 `fix` 类提交记录 bug 现象 | 真踩过坑（最值钱） |
| ❌ 一次 5000 行提交 | 大概率抄的 |
| ❌ 全是 `update`/`fix` | 没有工程素养 |
| ❌ 仓库里只有 final 版本 | 无法验证过程 |

> **本项目已有的真实 fix 记录，面试时可以直接讲**：
> `fix(logs): replace digits without word boundary` —— 数字后紧跟字母时 `\b` 不成立，
> 导致日志签名无法聚合、每条 count 都是 1，评测成功率从 62.5% 卡住。
> 这类"踩坑 commit"是仓库里最值钱的东西，别用 `--amend` 把它抹掉。

---

## 11. 本轮 Git 计划（配合 ROADMAP_DAILY v4）

| 日期 | 分支 | 主题 | 预计提交 |
|---|---|---|---|
| 11/11 | `feature/real-baseline` | 真实基线 + 失败归因 | 4 |
| 11/12 | `feature/hybrid-retrieval` | 混合检索 + 实验 A | 5 |
| 11/13 | `feature/eval-objectivity` | 结构化判分 + LLM-as-judge + 60 条 | 5 |
| 11/14 | `feature/mcp-server` | MCP + 工具路由 | 4 |
| 11/15 | `feature/parallel-fanout` | fan-out + 实验 D | 4 |
| 11/16 | `feature/fastapi-sse` | FastAPI + SSE 服务化 | 4 |
| 11/17 | `feature/gateway-hardening` | 限流/会话/审计/可观测 | 4 |
| 11/18 | `feature/scenario-b` | 场景 B + 评测扩到 120 | 5 |
| 11/19 | `feature/experiments-bc` | 实验 B/C + 汇总 | 4 |
| 11/20 | `release/v0.2.0` | 收口 + tag | 3 |
| 11/21–22 | `docs/interview-drill` | 追问演练 + 补漏 | 3 |

累计 ≈ 45 次提交、10 个 PR、2 个 tag。**每天至少 3 次提交**，这是面试官能看到的"持续投入"证据。
