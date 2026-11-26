"""The setup downloads from this repository's releases on GitHub only (builder/setup/setup.c). The original project's own
server, git.notrexed.dev, and the fallback address it had without Cloudflare (2026-11-15) are gone, and with them the
second host. Checked by source:

- HOOKSHOT_REPO and its wide twin name the same repository, TheologyAIGeek/Hookshot;
- every address the setup opens is GitHub's: the setup list and the latest release page (github.com), the API
  (api.github.com), and an API answer's download link is taken only when it is github.com's;
- http_get passes each request straight to http_get_once, which is called from nowhere else: no second host;
- no other host is named, the original project's above all.

python -I -B tests/test_setup_fallback_host.py
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def body(text, head):
    start = text.index(head)
    depth, i = 0, text.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i + 1]
        i += 1


def main():
    src = (ROOT / "builder/setup/setup.c").read_text(encoding="utf-8")
    assert '#define HOOKSHOT_REPO "TheologyAIGeek/Hookshot"' in src
    assert '#define HOOKSHOT_REPO_W L"TheologyAIGeek/Hookshot"' in src
    get = body(src, "static int http_get(const char *url8")
    assert "return http_get_once(url8, sink, user, expect, accept);" in get, "http_get: straight to http_get_once"
    once = body(src, "static int http_get_once(")
    assert "g_http_error = 0, g_http_status = 0;" in once, "a request's status is its own"
    calls = [m.start() for m in re.finditer(r"\bhttp_get_once\(", src)]
    inside = [c for c in calls if src.index(get) <= c < src.index(get) + len(get)]
    assert len(calls) - len(inside) == 1, "http_get_once is only defined, and called from http_get"
    # (the addresses: GitHub's alone)
    hosts = set(re.findall(r"https://([A-Za-z0-9.-]+)/", src))
    assert hosts <= {"github.com", "api.github.com"}, "hosts other than GitHub's: %s" % sorted(hosts - {"github.com", "api.github.com"})
    for need in ('"https://github.com/" HOOKSHOT_REPO "/releases/download/%s/hookshot-setup.txt"',
                 '"https://github.com/" HOOKSHOT_REPO "/releases/latest/download/hookshot-setup.txt"',
                 '"https://api.github.com/repos/%s/releases/tags/%s"', '"https://api.github.com/repos/%s/releases/latest"',
                 '!strncmp(out, "https://github.com/", 19)', 'static const char pre[] = "https://github.com/";'):
        assert need in src, need
    for gone in ("notrexed", "sslip.io", "kFallbackHost", "g_fallback"):
        assert gone not in src, gone
    print("PASS: the setup downloads from this repository's GitHub releases only")


if __name__ == "__main__":
    main()
