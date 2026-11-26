"""The Hookshot Builder's tool parts, zipped from an installed Builder's tools folder, for a repository whose releases have none
yet: the seed of its builder-parts release.

    python -I scripts/seed_builder_parts.py <tools folder> <out folder> [--base <url the parts are served from>]

<tools folder> is an installed Builder's, e.g. %LOCALAPPDATA%\\HookshotBuilder\\versions\\<version>\\HookshotBuilder\\tools: the
folder that holds python, emsdk, cpm, third_party, wgpu-native and work. It is only read, never written.

The setup (builder/setup/setup.c) installs a release from its hookshot-setup.txt: the Builder's own parts, which CI makes for
every release, and the tool parts, which the Windows builder workflow reuses from the last release's list
(scripts/make_setup_parts.py --reuse). A repository with no release yet has no list to reuse: this makes one.

Written into <out folder>, to upload to the repository's builder-parts release (a prerelease):

- HookshotBuilder-<part>-<sha256 prefix>.zip, one per part: python, emsdk, cpm, third_party and wgpu-native (those the tools
  folder has), and app, holding tools/work alone: the play profile (scripts/release_parts.py profile reads it from the app
  part). Zipped as make_setup_parts.py zips them (the same names, order, dates and attributes), so the setup unpacks them as
  any release's.
- hookshot-setup.txt, the seed list: its tag line is "seed" and it names those parts. CI finds it on builder-parts when no
  stable release has a list (scripts/release_parts.py previous). It is never a release's own list: it has no Builder.

No game data is involved: the tools are the builder's Python, compilers, headers and libraries, and tools/work holds addresses
and counts from playing, as every release's app part does.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_setup_parts as msp  # noqa: E402

BASE = "https://github.com/TheologyAIGeek/Hookshot/releases/download/builder-parts"
GITHUB_ASSET_MAX = 2 * 1024 ** 3   # (GitHub's largest release asset: 2 GiB)


def seed(tools, out, base=BASE):
    """The parts and the seed list from tools into out; the list's lines"""
    tools = os.path.abspath(tools)
    if os.path.basename(tools.rstrip("\\/")) != "tools" or not os.path.isdir(os.path.join(tools, "python")):
        raise SystemExit("not an installed Hookshot Builder's tools folder (no tools\\python): %s" % tools)
    root = os.path.dirname(tools)   # (the parts' names start at tools/, as make_setup_parts.py's)
    os.makedirs(out, exist_ok=True)
    names = [("app", ["work"])] + [(t, [t]) for t in msp.TOOLS_PARTS]
    lines = ["tag seed"]
    for name, tops in names:
        files = [f for t in tops if os.path.isdir(os.path.join(tools, t)) for f in msp.files_under(root, "tools/" + t)]
        if not files:
            print("%-12s (not in the tools folder)" % name, flush=True)
            continue
        tmp = os.path.join(out, "HookshotBuilder-%s.zip" % name)
        sha, size = msp.write_zip(tmp, root, files)
        named = os.path.join(out, "HookshotBuilder-%s-%s.zip" % (name, sha[:12]))
        os.replace(tmp, named)
        lines.append("part %s %d . - - %s/%s" % (sha, size, base.rstrip("/"), os.path.basename(named)))
        print("%-12s %6d files %6d MB  %s" % (name, len(files), size >> 20, os.path.basename(named)), flush=True)
        if size > GITHUB_ASSET_MAX:
            print("  over GitHub's 2 GiB a release file: %s cannot be uploaded as it is" % os.path.basename(named), flush=True)
    for need in ("python", "cpm", "third_party"):
        if not any(l.split()[6].rsplit("/", 1)[-1].startswith("HookshotBuilder-%s-" % need) for l in lines[1:]):
            raise SystemExit("the tools folder has no %s: a list without it installs no working Builder" % need)
    with open(os.path.join(out, "hookshot-setup.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tools")
    p.add_argument("out")
    p.add_argument("--base", default=BASE, help="where the parts are served from (default: %(default)s)")
    a = p.parse_args()
    lines = seed(a.tools, a.out, a.base)
    print("\n%d parts and hookshot-setup.txt in %s: upload them all to the builder-parts release" % (len(lines) - 1, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
