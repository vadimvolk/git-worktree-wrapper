# Branch Protection Setup

This document describes how to set up branch protection for the `main` branch using GitHub's API or web interface.

## Option 1: Using GitHub Web Interface (Recommended)

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Branches**
3. Click **Add rule** or edit the existing rule for `main`
4. Configure the following settings:
   - **Branch name pattern**: `main`
   - ✅ **Require a pull request before merging**
     - ✅ Require approvals: `1` (or more)
     - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ **Require status checks to pass before merging**
     - ✅ Require branches to be up to date before merging
     - Select required status checks:
       - `Test (Python 3.11) / ubuntu-latest`
       - `Test (Python 3.11) / macos-latest`
       - `Test (Python 3.12) / ubuntu-latest`
       - `Test (Python 3.12) / macos-latest`
       - `Test (Python 3.13) / ubuntu-latest`
       - `Test (Python 3.13) / macos-latest`
       - `Lint`
   - ✅ **Require conversation resolution before merging**
   - ✅ **Do not allow bypassing the above settings**
   - ✅ **Restrict who can push to matching branches** (optional, but recommended)
   - ✅ **Allow force pushes** (unchecked - disable force pushes)
   - ✅ **Allow deletions** (unchecked - prevent branch deletion)

## Option 2: Using GitHub CLI

```bash
# Install GitHub CLI if not already installed
# brew install gh  # macOS
# apt install gh   # Linux

# Authenticate
gh auth login

# Set branch protection rules
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Test (Python 3.11) / ubuntu-latest","Test (Python 3.11) / macos-latest","Test (Python 3.12) / ubuntu-latest","Test (Python 3.12) / macos-latest","Test (Python 3.13) / ubuntu-latest","Test (Python 3.13) / macos-latest","Lint"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

Replace `:owner` and `:repo` with your GitHub username and repository name.

## Option 3: Using GitHub API with curl

```bash
# Set your GitHub token
export GITHUB_TOKEN=your_token_here

# Set branch protection
curl -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/vadimvolk/git-worktree-wrapper/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": [
        "Test (Python 3.11) / ubuntu-latest",
        "Test (Python 3.11) / macos-latest",
        "Test (Python 3.12) / ubuntu-latest",
        "Test (Python 3.12) / macos-latest",
        "Test (Python 3.13) / ubuntu-latest",
        "Test (Python 3.13) / macos-latest",
        "Lint"
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews": true
    },
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false
  }'
```

## Verification

After setting up branch protection, verify it works:

1. Create a test branch: `git checkout -b test-branch-protection`
2. Make a change and push: `git push origin test-branch-protection`
3. Create a pull request to `main`
4. Verify that:
   - The PR cannot be merged until CI tests pass
   - The PR requires at least one approval
   - Force push to `main` is blocked

## Notes

- The CI workflow runs on all branches (push events) and on pull requests to `main`
- After merging to `main`, the CI will run again to verify the merge
- Status checks must pass before merging pull requests
- **Important**: After the first CI run completes, check the actual status check names in GitHub:
  1. Go to any pull request or commit
  2. View the "Checks" tab
  3. Note the exact names of the status checks (e.g., "Test (Python 3.11)", "Lint")
  4. Update the branch protection settings with the exact check names
- Alternatively, you can require only the job names (`test` and `lint`) if GitHub supports that, or require "any status check" to pass
