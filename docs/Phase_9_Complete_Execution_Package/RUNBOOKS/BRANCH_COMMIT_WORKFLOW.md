# Branch và commit workflow

## Start

```bash
cd ~/Documents/Construction_Management
git status --short
# Working tree phải sạch hoặc pre-existing changes phải được owner xử lý.
git switch <stable-phase8-branch>
git switch -c feature/phase-9-project-contractor-management
```

Không tự pull nếu user chưa yêu cầu.

## Trước commit mỗi step

```bash
git status --short
git diff --stat
git diff --check
```

Review từng file. Không dùng `git add -A` nếu working tree có unrelated files.

```bash
git add <explicit-files>
git diff --cached --stat
git diff --cached
```

Commit theo message trong `PHASE9_EXECUTION_MAP.md`.

```bash
git commit -m "<message>"
git status --short
git log -1 --oneline --decorate
```

Không amend hoặc force push tự động.

## Mỗi prompt phải báo cáo

- branch/head trước và sau;
- files changed;
- migration revision;
- targeted tests;
- full suite;
- runtime/security checks;
- commit hash;
- remaining limitations.
