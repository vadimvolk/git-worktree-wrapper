#!/bin/bash
# Setup branch protection for main branch using GitHub CLI

set -e

REPO_OWNER="${GITHUB_REPOSITORY_OWNER:-vadimvolk}"
REPO_NAME="${GITHUB_REPOSITORY_NAME:-git-worktree-wrapper}"
BRANCH="main"

echo "Setting up branch protection for ${REPO_OWNER}/${REPO_NAME}:${BRANCH}"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Install it with: brew install gh  # macOS"
    echo "                 apt install gh   # Linux"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub CLI."
    echo "Run: gh auth login"
    exit 1
fi

# Set branch protection
echo "Configuring branch protection rules..."

# Create temporary JSON file for the protection payload
# After first CI run, update the "contexts" array with actual check names
# Example: "contexts": ["Test (Python 3.11)", "Test (Python 3.12)", "Lint"]
TMP_FILE=$(mktemp)
cat > "$TMP_FILE" <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": []
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": true,
  "allow_squash_merge": true,
  "allow_merge_commit": true,
  "allow_rebase_merge": true
}
EOF

gh api "repos/${REPO_OWNER}/${REPO_NAME}/branches/${BRANCH}/protection" \
  --method PUT \
  --input "$TMP_FILE"

# Clean up
rm "$TMP_FILE"

echo "✅ Branch protection configured successfully!"
echo ""
echo "Branch protection rules:"
echo "  - Require pull request reviews (1 approval)"
echo "  - Require conversation resolution before merging"
echo "  - Require status checks to pass"
echo "  - Require branches to be up to date"
echo "  - Enforce admins"
echo "  - Disallow force pushes"
echo "  - Disallow deletions"
echo ""
echo ""
echo "⚠️  Important: Status checks are currently set to an empty list."
echo "   After the first CI run completes:"
echo "   1. Go to any PR or commit and check the 'Checks' tab"
echo "   2. Note the exact status check names (e.g., 'Test (Python 3.11)', 'Lint')"
echo "   3. Update branch protection via GitHub web interface:"
echo "      Settings → Branches → Edit rule for 'main'"
echo "      → Add the status checks under 'Require status checks to pass'"
echo ""
echo "   Or update this script with the correct context names and run it again."
