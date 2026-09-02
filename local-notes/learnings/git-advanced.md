# Git — Advanced Patterns

*Last updated: 2026-09-03.*

---

## Multi-remote workflows (private + public repo)

A single local repository can push to multiple remotes. This is useful when
you have a private development repo and a public-facing repo that only gets
a clean subset of the code.

```bash
git remote add origin   git@github.com:user/private-repo.git
git remote add public   git@github.com:user/public-repo.git
```

### The refspec — critical to get right

A refspec maps a local branch to a remote branch. The format is `local:remote`.

```bash
git push public publish:main
#               ↑       ↑
#          local branch  remote branch
```

This pushes the local `publish` branch to the `main` branch on the `public` remote.
The local branch and remote branch do not need the same name.

**The most common mistake:** omitting the `:main` mapping:
```bash
git push public publish   # WRONG — creates a "publish" branch on the public remote
git push public publish:main  # RIGHT — pushes to "main" on the public remote
```

Without the refspec, git creates a remote branch with the same name as the local
branch. If you didn't want that branch to exist on the remote (e.g. it's a
staging-only branch), you now have a stale branch on the public remote that may
become the default branch on GitHub, hiding your actual code.

### Cleaning up a wrongly-pushed branch

```bash
git push public --delete publish  # delete "publish" branch from public remote
```

### Preventing accidental pushes

After a refspec push, break the upstream tracking so `git push public publish`
(without the mapping) fails with a clear error instead of silently creating
the wrong branch:

```bash
git branch --unset-upstream publish
```

Now the only way to push to the public remote is the explicit refspec.

---

## Rewriting git history with `git filter-repo`

`git filter-repo` is the modern replacement for `git filter-branch`. Use it to:
- Strip sensitive content (API keys, credentials) from commit history
- Remove attribution lines (e.g. "Co-Authored-By") from all commits
- Delete files from history entirely

Install: `pip install git-filter-repo` or `brew install git-filter-repo`.

### Strip text from all commit messages

```bash
git filter-repo --force --message-callback '
import re
message = re.sub(rb"Co-Authored-By:[^\n]*\n?", b"", message)
message = re.sub(rb"Sensitive-Header:[^\n]*\n?", b"", message)
return message.rstrip() + b"\n"
'
```

The `--force` flag is required when the repo has a remote (filter-repo's safety
check assumes a fresh clone by default). The callback receives and returns bytes.

**After running filter-repo:**
- All commit hashes change — every commit in history gets a new SHA
- Remote tracking refs are stripped (filter-repo removes them as a safety measure)
- Force-push to all remotes: `git push origin main --force`
- Re-add remotes if needed: `git remote add origin <url>`

### Remove a file from all history

```bash
git filter-repo --force --path path/to/file.txt --invert-paths
```

### Why hashes change

git commits are content-addressed — the hash is a digest of the content. If you
change anything in a commit (including the message), the hash changes. Since each
commit's hash includes its parent's hash, changing one commit cascades and changes
every subsequent commit's hash. This is why a history rewrite requires a force push.

### GitHub's contributor cache

GitHub computes contributors based on `Co-Authored-By` trailers in commit messages
across all branches. After rewriting history and force-pushing:
- The attribution is gone from the git objects
- GitHub's contributor cache takes hours (sometimes longer) to recompute
- There is no way to force an immediate refresh — wait it out

If a stale branch on the remote still references the old commits (with the
old attribution), the contributor appears until that branch is deleted and
GitHub garbage-collects the unreferenced objects.

---

## Checking what's on each remote before pushing

```bash
git branch -r                    # list all remote-tracking branches
git log public/main --oneline    # see what's on public remote's main
git diff main public/main        # diff local main vs public remote main
```

---

## Related

- [[cicd-github-actions]] — CI runs on push events; understanding remotes matters for branch protection rules
