#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply or print the recommended GitHub branch protection."
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--required-check", action="append", default=[])
    parser.add_argument("--required-approvals", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.required_approvals <= 6:
        parser.error("--required-approvals must be between 0 and 6")
    required_checks = args.required_check or ["cpp-ci"]
    policy = {
        "required_status_checks": {"strict": True, "contexts": required_checks},
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": args.required_approvals,
            "require_last_push_approval": args.required_approvals > 0,
        },
        "restrictions": None,
        "required_linear_history": True,
        "required_conversation_resolution": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    if not args.apply:
        print(json.dumps(policy, indent=2, sort_keys=True))
        return 0
    subprocess.run(
        [
            "gh",
            "api",
            f"repos/{args.repository}/branches/{args.branch}/protection",
            "--method",
            "PUT",
            "--input",
            "-",
        ],
        input=json.dumps(policy),
        text=True,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
