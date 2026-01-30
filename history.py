import os
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import argparse
import click
import re
from operator import itemgetter
from wcwidth import wcswidth

# Adjust these:
PROJECTS_ROOT = os.path.expanduser("~/projects")
GIT_AUTHORS = ["lbrown@rkh.co.uk", "ayan.ftw@gmail.com"]
DATE_FORMAT = "%Y-%m-%d"


def get_last_monday():
    today = datetime.today()
    offset = (today.weekday() - 0) % 7  # Monday = 0
    last_monday = today - timedelta(days=offset or 7)
    return last_monday.strftime(DATE_FORMAT)


SINCE_DATE = get_last_monday()


def find_git_repos(root):
    """Find all git repos (including worktrees) under root"""
    projects = Path(root)
    dirs = [d for d in projects.iterdir() if d.is_dir() and (d / ".git").exists()]
    return dirs


def run_git_command(cwd, args):
    try:
        output = subprocess.check_output(
            ["git"] + args, cwd=cwd, text=True, stderr=subprocess.DEVNULL
        )
        return output.strip()
    except subprocess.CalledProcessError:
        return ""


def get_branches(repo_dir):
    output = run_git_command(
        repo_dir, ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"]
    )
    return output.splitlines()


def get_commits(repo_dir, branch, authors, since_date):
    """Return list of commits as tuples (hash, date, time, message)"""
    commit_separator = "\x1f"
    field_separator = "\x1e"
    log_format = f"%h{field_separator}%ad{field_separator}%at{field_separator}%B{commit_separator}"  # short hash {field_separator} date (YYYY-MM-DD) {field_separator} timestamp {field_separator} message
    authors_param = [f"--author={author}" for author in authors]

    output = run_git_command(
        repo_dir,
        [
            "log",
            branch,
            "--use-mailmap",
            *authors_param,
            f"--since={since_date}",
            f"--pretty=format:{log_format}",
            "--date=short",
        ],
    )
    commits = []
    if output:
        for line in output.strip(commit_separator).split(commit_separator):
            parts = line.strip().split(field_separator, 3)
            commit = {
                "hash": parts[0],
                "date_str": parts[1],
                "timestamp": int(parts[2]),
                "message": parts[3].strip(),
            }
            commits.append(commit)
    return commits


def indent(level: int = 0) -> str:
    return " " * level


def prefix(string: str, perfix_str: str = "-") -> str:
    return f"{perfix_str} {string}"


def outline(string_array, width=120):
    """
    Draw an outline box around the given array of strings.
    """
    first_line, *rest = string_array
    colour = "green"
    side = click.style("│", fg=colour)
    yield click.style(
        f"┌─ {first_line} {'─' * (width - wcswidth(first_line))}┐", fg=colour
    )
    for line in rest:
        unstyled_line = click.unstyle(line)
        yield f"{side} {line} {' ' * (width - wcswidth(unstyled_line) + 1)}{side}"
    yield click.style(f"└{'─' * (width + 3)}┘", fg=colour)


def ordinal(n: int) -> str:
    """
    Return the ordinal suffix for a given day of the month.
    e.g. 21st, 5th, 17th, 22nd
    """
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def main(since_date):
    print(f"Listing commits by '{GIT_AUTHORS}' since {since_date}\n")

    git_dirs = find_git_repos(PROJECTS_ROOT)
    seen = set()

    all_commits = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for git_dir in git_dirs:
        branches = get_branches(git_dir)
        for branch in branches:
            for commit in get_commits(git_dir, branch, GIT_AUTHORS, since_date):
                key = (git_dir.name, commit["hash"])
                if key in seen:
                    continue
                seen.add(key)
                all_commits[commit["date_str"]][git_dir.name][branch].append(commit)

    for date_str, repos in sorted(all_commits.items()):
        date = datetime.strptime(date_str, DATE_FORMAT)
        day_ordinal = ordinal(date.day)
        date_display = date.strftime(f"%A %d{day_ordinal} %B %Y")
        output = [date_display, ""]

        for repo, branches in sorted(repos.items()):
            level = 1
            output.append(click.style(f"{indent(level)}{repo}:", fg="cyan", bold=True))
            # level += 3
            for branch, commits in sorted(branches.items()):
                branch_name = re.sub(r"^refs/(heads|remotes/[^/]+)/", "", branch)
                output.append(
                    click.style(
                        f"{indent(level)}{prefix(branch_name)}: {len(commits)} commits",
                        fg="yellow",
                    )
                )
                level = 3
                commit_indent = indent(level + 2)
                for commit in sorted(commits, key=itemgetter("timestamp")):
                    date = datetime.fromtimestamp(commit["timestamp"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    hash = click.style(commit["hash"], fg="magenta")
                    output.append(
                        click.style(f"{indent(level)}{prefix(date)} {hash}", fg="white")
                    )
                    commit_msg = re.sub(
                        r"\n\s*", f"\n{commit_indent}", commit["message"]
                    )
                    commit_lines = [
                        line.strip() for line in commit["message"].splitlines()
                    ]
                    for line in commit_msg.splitlines():
                        output.append(f"{commit_indent}{line}")
                    output.append("")
        click.secho("\n".join(outline(output)), fg="white")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List git commits by me")
    parser.add_argument(
        "since_date", nargs="?", default=SINCE_DATE, help="Since date (YYYY-MM-DD)"
    )
    args = parser.parse_args()
    main(args.since_date)
