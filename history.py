#!/usr/bin/env python

import click
from pydriller import Repository

from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from git.exc import GitCommandError

COMMIT_INDENT = 2


def commit_list():
    return defaultdict(list)


@click.command
@click.option(
    "--since",
    help="Since date",
    type=click.DateTime(),
    default=datetime.now() - timedelta(days=7),
)
def commits_by_date(since: datetime):
    projects = Path("~/projects").expanduser()
    urls = [str(p.parent) for p in projects.glob("*/.git")]

    commits = defaultdict(commit_list)

    for url in urls:
        try:
            for commit in Repository(
                url, only_authors=["lbrown"], since=since
            ).traverse_commits():
                commits[commit.author_date.date()][commit.project_name].append(commit)
        except GitCommandError:
            pass

    for date, data in sorted(commits.items()):
        click.secho(f"┌{'─'*12}┐", fg="green")
        click.secho(f"│ {date} │", fg="green")
        click.secho(f"└{'─'*12}┘\n", fg="green")

        for repo, commits in data.items():
            msg = f"{repo}: {len(commits)} commits"
            click.secho(msg, fg=(255, 12, 128))
            for commit in commits:
                first, *rest = commit.msg.splitlines()
                click.secho(f"{' '*COMMIT_INDENT}{commit.author_date:%H:%M} {first}")
                for r in rest:
                    click.secho(f"{' '*(COMMIT_INDENT + 5)} {first}")

            click.echo()


if __name__ == "__main__":
    commits_by_date()
