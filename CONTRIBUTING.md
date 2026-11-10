# 贡献指南

## 快速开始

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
python sim/inject.py pool_exhaust && python -m eval.run_eval --only easy
```

## 分支与提交

- 分支：`feature/<主题>` / `fix/<主题>` / `docs/<主题>`，从 `develop` 切出
- 提交：Conventional Commits，见 [docs/GIT_WORKFLOW.md](GIT_WORKFLOW.md)
- 合并：Squash and merge，CI 必须绿

## 提交前自查

- [ ] `pytest -q` 通过
- [ ] `ruff check .` 无新增告警
- [ ] 新增逻辑有对应测试
- [ ] 若改动影响效果，附上 `eval_report.md` 前后对比
- [ ] 没有把 `data/`、`.env`、`*.db` 加进暂存区

## 改动效果类代码的额外要求

凡是影响 Agent 行为的改动（prompt、工具、检索、终止策略），必须在 PR 描述里给出：

| 指标 | 改动前 | 改动后 |
|---|---|---|
| TaskSuccessRate | | |
| AvgSteps | | |
| AvgTokens | | |

**没有指标对比的效果类改动不予合并**——这是本项目的硬规则。
