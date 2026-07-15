"""Create reproducible demo PRs in a disposable scratch repository."""

import os

from github import Github


SCENARIOS = [
    ("demo/n-plus-one", "Seeded N+1 query example", "demo_n_plus_one.py", "for order in user.orders:\n    for item in order.items:\n        product = Product.query.get(item.product_id)\n"),
    ("demo/borderline-query", "Seeded borderline query example", "demo_borderline.py", "for order in user.orders:\n    product = Product.query.get(order.product_id)\n"),
    ("demo/clean-pr", "Seeded clean PR example", "demo_clean.py", "def get_orders(user):\n    return user.orders\n"),
]


def main() -> None:
    repository = Github(os.environ["GITHUB_TOKEN"]).get_repo(os.environ["SCRATCH_REPO"])
    base = repository.default_branch
    base_sha = repository.get_branch(base).commit.sha
    for branch, title, path, content in SCENARIOS:
        try:
            repository.get_branch(branch)
            print(f"Skipping existing branch {branch}")
            continue
        except Exception:
            pass
        repository.create_git_ref(f"refs/heads/{branch}", base_sha)
        repository.create_file(path, title, content, branch=branch)
        pull_request = repository.create_pull(
            title=title,
            body="Reproducible PR Risk Agent demo fixture.",
            head=branch,
            base=base,
        )
        print(f"Created PR #{pull_request.number}: {pull_request.html_url}")


if __name__ == "__main__":
    main()
