---
name: git-sync
description: Workflow for staging all changed files (git add .), creating a local git commit with a clear descriptive message, and pushing changes to the remote GitHub repository (git push).
---

# Git Sync Skill

This skill defines the standardized workflow for staging, committing, and pushing code changes to the remote GitHub repository.

## Workflow Steps

1. **Stage All Changes**:
   Stage all modified and untracked files in the repository:
   ```bash
   git add .
   ```

2. **Commit Changes**:
   Create a local commit with a clear, concise descriptive message explaining the modifications:
   ```bash
   git commit -m "<descriptive commit message>"
   ```

3. **Push to Remote**:
   Push the local commits to the main branch on the remote repository:
   ```bash
   git push origin main
   ```

4. **Verification**:
   Run `git status` to ensure the working tree is clean and up to date with `origin/main`.
