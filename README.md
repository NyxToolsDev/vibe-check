# Vibe Check

**Production-readiness scanner for AI-generated and vibe-coded projects.**

[![PyPI](https://img.shields.io/pypi/v/vibe-code-check)](https://pypi.org/project/vibe-code-check/)
[![Python](https://img.shields.io/pypi/pyversions/vibe-code-check)](https://pypi.org/project/vibe-code-check/)
[![License](https://img.shields.io/pypi/l/vibe-code-check)](https://github.com/NyxToolsDev/vibe-check/blob/main/LICENSE)

AI-assisted coding is fast. Shipping it to production without checking for security holes, missing tests, and bad patterns is dangerous. **Vibe Check** scans your project in seconds and gives you a letter grade (A-F) across 6 categories.

```
$ vibe-check scan .

  Vibe Check Report — Grade: B (74/100)

  Category        Score  Grade  Findings
  ──────────────  ─────  ─────  ────────
  Security          70     B       2
  Testing           85     A       1
  Code Quality      90     A       1
  Architecture      80     B       2
  Dependencies      95     A       0
  HIPAA             --    Pro      -
```

## Install

```bash
pip install vibe-code-check
```

Requires Python 3.10+.

## Quick Start

```bash
# Scan current directory
vibe-check scan .

# JSON output for CI pipelines
vibe-check scan . -f json

# Markdown report
vibe-check scan . -f markdown -o report.md

# Scan only security + testing
vibe-check scan . -c security -c testing

# CI mode — fail if grade below B
vibe-check scan . --ci --threshold B
```

## What It Scans

### Security (30% of score)

| Rule | Severity | What it catches |
|------|----------|-----------------|
| SEC-001 | FAIL | Hardcoded API keys, passwords, tokens, AWS credentials |
| SEC-002 | FAIL | SQL injection via string interpolation |
| SEC-003 | FAIL | `eval()` / `exec()` usage |
| SEC-004 | WARN | Debug mode left enabled |
| SEC-005 | WARN | Wildcard CORS (`Access-Control-Allow-Origin: *`) |
| SEC-006 | FAIL | `dangerouslySetInnerHTML` without DOMPurify |
| SEC-007 | FAIL | Hardcoded database connection strings with credentials |
| SEC-008 | FAIL | Unsafe deserialization (`pickle.load`, `yaml.load` without SafeLoader) |
| SEC-009 | FAIL | Shell injection (`subprocess` with `shell=True`, `os.system()`) |
| SEC-010 | WARN | Path traversal via user input in file operations |
| SEC-011 | FAIL | `.env` files not in `.gitignore` |

### Testing (20% of score)

| Rule | Severity | What it catches |
|------|----------|-----------------|
| TST-001 | FAIL | No test directory found |
| TST-002 | WARN | Missing test files for source modules |
| TST-003 | FAIL/WARN | Low test-to-source ratio (<0.3 fail, <0.5 warn) |
| TST-004 | WARN | No test runner configuration |

### Code Quality (15% of score)

| Rule | Severity | What it catches |
|------|----------|-----------------|
| CQ-001 | WARN | Functions longer than 50 lines |
| CQ-002 | WARN | Files longer than 500 lines |
| CQ-003 | WARN | Deeply nested code (>4 levels) |
| CQ-004 | FAIL/WARN | Excessive TODO/FIXME/HACK comments |

### Architecture (15% of score)

| Rule | Severity | What it catches |
|------|----------|-----------------|
| ARC-001 | WARN | God files (>500 lines) |
| ARC-002 | INFO | Missing error handling (no try/except or try/catch) |
| ARC-003 | WARN | Bare `except:` clauses (catches SystemExit) |
| ARC-004 | INFO | Missing type hints in Python files |

### Dependencies (10% of score)

| Rule | Severity | What it catches |
|------|----------|-----------------|
| DEP-001 | WARN | Missing lock file |
| DEP-002 | WARN | Unpinned dependency versions |
| DEP-003 | WARN | Wildcard or "latest" versions in package.json |
| DEP-004 | FAIL/WARN | Excessive dependencies (>50 fail, >30 warn) |

### HIPAA Compliance (10% of score) -- Pro

| Rule | Severity | What it catches |
|------|----------|-----------------|
| HIPAA-001 | FAIL | PHI fields in log/print statements |
| HIPAA-002 | FAIL | Missing HTTPS/TLS configuration |
| HIPAA-003 | WARN | No audit logging detected |
| HIPAA-004 | FAIL | PHI fields in error handling blocks |
| HIPAA-005 | WARN | No session timeout configuration |
| HIPAA-006 | WARN | Database operations without encryption library |

## Grading Scale

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 85-100 | Production-ready |
| B | 70-84 | Good, minor issues |
| C | 55-69 | Needs work before shipping |
| D | 40-54 | Significant issues |
| F | 0-39 | Not ready for production |

## CI/CD Integration

```yaml
# GitHub Actions
- name: Vibe Check
  run: |
    pip install vibe-code-check
    vibe-check scan . --ci --threshold B
```

```yaml
# GitLab CI
vibe-check:
  script:
    - pip install vibe-code-check
    - vibe-check scan . --ci --threshold B -f json -o vibe-report.json
  artifacts:
    paths:
      - vibe-report.json
```

The `--ci` flag exits with code 1 if the overall grade falls below `--threshold` (default: C).

## Output Formats

| Format | Flag | Use case |
|--------|------|----------|
| Terminal | `-f terminal` | Human-readable with colors (default) |
| JSON | `-f json` | CI pipelines, dashboards |
| Markdown | `-f markdown` | PR comments, reports |
| All | `-f all` | Generate all formats at once |

## Pro: HIPAA Compliance Module

The HIPAA scanner detects PHI handling violations specific to healthcare applications -- context-aware detection that distinguishes `patient_ssn` from `patient_count`.

```bash
# Activate with a license key
vibe-check scan . --license-key YOUR_KEY

# Or set as environment variable
export VIBE_CHECK_LICENSE_KEY=YOUR_KEY
vibe-check scan .
```

Get a Pro license at [nyxtools.gumroad.com](https://nyxtools.gumroad.com).

## Supported Languages

- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- Go (.go), Java (.java), Ruby (.rb), Rust (.rs) -- file discovery and basic checks

## How Scoring Works

Each category starts at 100 points. Deductions:

- **FAIL** finding: -15 points
- **WARN** finding: -5 points
- **INFO** finding: -1 point

The overall score is a weighted average across all categories. Security is weighted heaviest at 30% because a single security vulnerability can take down your entire application.

## Built by NyxTools

Part of the [NyxTools](https://github.com/NyxToolsDev) suite of developer and healthcare IT tools.

**NyxTools - LEW Enterprises LLC**

## License

MIT
