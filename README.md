# Agent Radar

A curated, reproducible radar for AI agents, execution harnesses, evaluation, trust, security, governance and related infrastructure.

**Start with [the latest report](reports/latest.md).** This first milestone establishes a verified metadata baseline. It does not claim that high-star repositories are currently trending.

## Run it

Requirements: Python 3.10 or later, [GitHub CLI](https://cli.github.com/), and a GitHub account authenticated with `gh auth login` (or `GH_TOKEN` in your environment). No Python packages are required.

```sh
python3 radar.py collect
python3 radar.py discover
python3 -m unittest discover -s tests -v
```

`collect` reads the curated seeds, fetches public repository metadata, saves an immutable timestamped snapshot and generates both an archived report and `reports/latest.md`. It follows canonical repository names returned by GitHub and deduplicates by repository ID. Four concurrent readers and bounded retries keep collection modest. Failed repositories appear in the report and produce a nonzero exit status. An entirely failed run preserves existing reports.

`discover` runs the editable topic searches and saves unreviewed candidates separately. It takes the 20 most recently updated matches per query, deduplicates them and records the query that found each one. It is a bounded discovery sample, not an exhaustive GitHub index or a trending ranking. Review candidates before adding them to the seed file. Search API limits can differ from general API limits; failures are saved explicitly.

## Daily collection

The [daily GitHub workflow](.github/workflows/collect.yml) is prepared to run at **06:17 UTC each day** after this repository is published to GitHub with Actions enabled. That is 1:17 a.m. Chicago daylight time or 12:17 a.m. standard time. GitHub may delay scheduled runs.

It runs the tests, collects metadata, and commits snapshots and reports to the default branch. It uses the built-in GitHub token; no personal token secret is needed. Concurrent collection runs are serialized. Partial observations are retained, but an incomplete collection still marks the run failed. If all lookups fail, existing reports remain unchanged.

For the first hosted run, select **Actions → Daily repository radar → Run workflow**. Publishing and a successful hosted run must be verified before treating daily collection as active. Repository policies must allow Actions and writes to the default branch.

To pause collection, disable the workflow in GitHub Actions. Discovery remains a manual command so unreviewed candidates cannot silently enter the baseline.

## Coverage and curation

- **Agents:** frameworks and orchestration.
- **Harnesses:** execution loops, coding agents and browser agents.
- **Evaluation:** benchmarks, test environments and evaluation frameworks.
- **Security:** guardrails, prompt-injection testing, sensitive-data handling and sandboxes.
- **Governance:** agent governance plus general-purpose authorization and responsible-AI tools relevant to agent systems.
- **Infrastructure:** protocols, memory, gateways and observability.

Edit `config/seeds.tsv` to change the baseline and its editorial inclusion notes. Edit `config/searches.json` to change discovery searches. Each repository has one primary category; the taxonomy is a navigation aid, not an assertion that capabilities are exclusive. The baseline uses editorial selection and live metadata to assess topical fit; it is not a code audit or certification. General-purpose and model-level tools are explicitly labeled in their inclusion notes.

No minimum star threshold is imposed on the curated baseline. Archived entries remain visible with their status, so significant projects are not silently lost.

## Measurements

Snapshots retain GitHub repository ID, canonical name, source URL, description, topics, stars, forks, creation and push dates, archive status, detected license and per-repository fetch time. `open_issues_and_prs` deliberately reflects GitHub's combined count.

7-day and 30-day growth is the difference in total stars against the newest matching observation at least that old, within a 12-hour collection-timing allowance. Missing history is displayed as `—`, never zero. Counts can decrease. Repository IDs keep comparisons intact after renames. Missed collection windows lead to unavailable measurements rather than misleading estimates. The first report is ordered by total stars within categories; no composite trend score exists yet.

## Files

- `radar.py`: collection, discovery and Markdown reporting.
- `config/`: reviewed seed list and discovery searches.
- `data/snapshots/`: immutable baseline and subsequent observations.
- `data/candidates/`: unreviewed discovery results, when generated.
- `reports/`: readable reports, including the latest result.
- `tests/`: checks for observation windows, renamed repositories and failed collection.

## Data sources

[GitHub repository API](https://docs.github.com/en/rest/repos/repos#get-a-repository), [repository search syntax](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories), and [search API](https://docs.github.com/en/rest/search/search#search-repositories). Each report links the individual repository and metadata endpoint. Metrics are observations at collection time, not continuously refreshed values. No third-party repository code is downloaded or executed.
