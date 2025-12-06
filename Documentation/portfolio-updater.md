# Portfolio README Automation

The portfolio README is automatically refreshed by the GitHub Actions workflow defined in [`.github/workflows/portfolio-update.yml`](../.github/workflows/portfolio-update.yml). The workflow runs weekly (and on manual dispatch) to ensure the "Latest Repositories" section always reflects your most recently updated public projects.

## Local usage

The update logic lives in [`scripts/update_portfolio.py`](../scripts/update_portfolio.py). Run it locally to preview changes:

```bash
python scripts/update_portfolio.py --offline --verbose
```

Key options:

- `--limit`: number of repositories to display (defaults to 8).
- `--include-forks` / `--include-archived`: opt-in flags for forks and archived repos.
- `--offline`: skip the network call and rely on the cached payload at `scripts/cache/latest_repos.json`.
- `--cache`: change the cache location.

If the network call fails, the script gracefully falls back to the cached payload. The cache is refreshed whenever the GitHub API is reachable.

## Continuous integration

During workflow execution we:

1. Update submodules to ensure embedded projects stay in sync.
2. Run `python -m unittest discover -s tests -p 'test_*.py'` to guarantee the updater’s core helpers work as expected.
3. Refresh the README via `python scripts/update_portfolio.py --limit 8`.
4. Commit and push changes when a diff is present.

This keeps the portfolio self-maintaining without manual intervention.
