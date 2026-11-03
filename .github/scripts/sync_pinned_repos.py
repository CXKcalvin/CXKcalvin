import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


USERNAME = "cxkcalvin"
README_PATH = "README.md"
PROJECT_URL_PATTERN = re.compile(
    r"https://www\.gitskins\.com/api/section/projects\?[^\s\"']+"
)
GRAPHQL_QUERY = """
query {
  user(login: "cxkcalvin") {
    pinnedItems(first: 6, types: [REPOSITORY]) {
      nodes {
        ... on Repository {
          nameWithOwner
        }
      }
    }
  }
}
"""


def fetch_pinned_repositories(token):
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": GRAPHQL_QUERY}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"GitHub GraphQL request failed: {error}") from error

    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {result['errors']}")

    user = (result.get("data") or {}).get("user")
    if user is None:
        raise RuntimeError(f"GitHub user {USERNAME!r} was not found")

    return [
        node["nameWithOwner"]
        for node in user["pinnedItems"]["nodes"]
        if node and node.get("nameWithOwner")
    ]


def update_project_url(url, repositories):
    parts = urlsplit(url)
    parameters = parse_qsl(parts.query, keep_blank_values=True)
    updated_parameters = []
    repos_added = False

    for key, value in parameters:
        if key == "repos":
            if not repos_added:
                updated_parameters.append(("repos", ",".join(repositories)))
                repos_added = True
        else:
            updated_parameters.append((key, value))

    if not repos_added:
        updated_parameters.append(("repos", ",".join(repositories)))

    query = urlencode(updated_parameters, quote_via=quote)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def sync_readme(repositories):
    with open(README_PATH, "r", encoding="utf-8") as readme:
        content = readme.read()

    updated_content, matches = PROJECT_URL_PATTERN.subn(
        lambda match: update_project_url(match.group(0), repositories), content
    )
    if matches == 0:
        raise RuntimeError("No gitskins projects URLs were found in README.md")
    if updated_content == content:
        print(f"Pinned repository list is already current ({len(repositories)} repos).")
        return False

    with open(README_PATH, "w", encoding="utf-8") as readme:
        readme.write(updated_content)
    print(f"Updated {matches} project URLs with {len(repositories)} pinned repos.")
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to query pinned repositories")
    repositories = fetch_pinned_repositories(token)
    sync_readme(repositories)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
