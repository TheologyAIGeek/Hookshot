"""scripts/seed_builder_parts.py and the seed list (scripts/release_parts.py previous): a repository with no release yet gets its
Builder's tool parts from an installed Builder's tools folder. Checked, on a made-up tools folder:

- the tools folder is only read: every file's bytes and the folder's names are the same after;
- one zip per part (app with tools/work alone, python, emsdk, cpm, third_party, wgpu-native), named by its SHA-256, holding
  HookshotBuilder/tools/<part>/... as make_setup_parts.py's do, the same bytes when made again;
- hookshot-setup.txt, tagged "seed", names each part as a release's list does, and make_setup_parts.py --reuse takes the tool
  parts from it for a package with no tools of its own;
- release_parts.py named_part finds the app part's profile and the third_party part in it;
- release_parts.py previous takes the seed list from the builder-parts release when no stable release has a list, a stable
  release's list first when there is one, and a folder with no python, cpm or third_party is refused.

python -I -B tests/test_seed_builder_parts.py
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tree(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


def make_tools(tools):
    for rel, data in {"python/python.exe": b"py", "python/Lib/os.py": b"os", "emsdk/upstream/bin/clang.exe": b"clang",
                      "cpm/vulkanheaders/v1.4.345/include/vulkan/vulkan.h": b"vk", "third_party/zbic/zbic.dll": b"zbic",
                      "third_party/a64emit.dll": b"a64", "wgpu-native/lib/wgpu_native.dll": b"wgpu", "work/hot_order.txt": b"order",
                      "work/hookshot_pieces.prof": b"prof", "version.txt": b"v3.0.2\n", "nx2/make_game.py": b"code"}.items():
        p = tools / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def main():
    seed_mod = load("seed_builder_parts")
    rp = load("release_parts")
    with tempfile.TemporaryDirectory(prefix="seed-parts-") as tmp:
        tmp = Path(tmp)
        tools = tmp / "HookshotBuilder" / "tools"
        make_tools(tools)
        before = tree(tools)
        out = tmp / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            lines = seed_mod.seed(str(tools), str(out))
        assert tree(tools) == before, "the tools folder was written to"
        assert lines[0] == "tag seed", lines[0]
        zips = {}
        for line in lines[1:]:
            w = line.split()
            assert len(w) == 7 and w[0] == "part" and w[3:6] == [".", "-", "-"], line
            assert w[6].startswith(seed_mod.BASE + "/HookshotBuilder-"), w[6]
            name = w[6].rsplit("/", 1)[-1]
            part = name[len("HookshotBuilder-"):].rsplit("-", 1)[0]
            z = out / name
            assert hashlib.sha256(z.read_bytes()).hexdigest() == w[1] and z.stat().st_size == int(w[2]) and w[1][:12] in name
            zips[part] = sorted(zipfile.ZipFile(z).namelist())
        assert sorted(zips) == ["app", "cpm", "emsdk", "python", "third_party", "wgpu-native"], sorted(zips)
        assert zips["app"] == ["HookshotBuilder/tools/work/hookshot_pieces.prof", "HookshotBuilder/tools/work/hot_order.txt"], zips["app"]
        assert zips["third_party"] == ["HookshotBuilder/tools/third_party/a64emit.dll", "HookshotBuilder/tools/third_party/zbic/zbic.dll"]
        assert all(not n.startswith("HookshotBuilder/tools/nx2/") for names in zips.values() for n in names), "code is not a tool part"
        assert (out / "hookshot-setup.txt").read_text(encoding="utf-8").splitlines() == lines
        # (made again: the same bytes)
        with contextlib.redirect_stdout(io.StringIO()):
            again = seed_mod.seed(str(tools), str(tmp / "out2"))
        assert again == lines, "not the same parts when made again"
        print("PASS: the parts are zipped from the tools folder, which is left as it was, the same bytes each time")

        # (make_setup_parts.py --reuse: a package with no tools of its own takes the tool parts from the seed list)
        pkg = tmp / "pkg"
        (pkg / "tools").mkdir(parents=True)
        (pkg / "HookshotBuilder.exe").write_bytes(b"exe")
        (pkg / "tools" / "nx2").mkdir()
        (pkg / "tools" / "nx2" / "make_game.py").write_bytes(b"code")
        r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "make_setup_parts.py"), str(pkg), "v3.0.4", str(tmp / "rel"),
                            "--reuse", str(out / "hookshot-setup.txt")], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        made = (tmp / "rel" / "hookshot-setup.txt").read_text(encoding="utf-8").splitlines()
        for part in ("python", "emsdk", "cpm", "third_party", "wgpu-native"):
            seeded = next(l for l in lines if "/HookshotBuilder-%s-" % part in l)
            assert seeded in made, "make_setup_parts.py did not reuse " + part
        print("PASS: make_setup_parts.py --reuse takes the tool parts from the seed list")

        # (release_parts.py: named_part reads the app part's profile and the third_party part, previous finds the seed)
        served = {seed_mod.BASE + "/" + p.name: p.read_bytes() for p in out.iterdir()}
        releases = []

        def fake_get(url, api=False, tries=5):
            if url in served:
                return served[url]
            if url.endswith("/releases?per_page=30"):
                return json.dumps(releases).encode()
            if url.endswith("/releases/tags/builder-parts"):
                return json.dumps({"tag_name": "builder-parts", "prerelease": True, "assets": [
                    {"name": "hookshot-setup.txt", "browser_download_url": seed_mod.BASE + "/hookshot-setup.txt"}]}).encode()
            if url == "https://github.com/x/stable/hookshot-setup.txt":
                return b"tag v3.0.4\n"
            raise AssertionError("asked for " + url)
        rp.get = fake_get
        rp.CACHE = str(tmp / "cache")
        work = tmp / "work"
        with contextlib.redirect_stdout(io.StringIO()):
            assert rp.profile(argparse.Namespace(list=str(out / "hookshot-setup.txt"), work=str(work))) == 0
        assert (work / "hot_order.txt").read_bytes() == b"order"
        assert rp.named_part(str(out / "hookshot-setup.txt"), "third_party")
        got = tmp / "previous.txt"
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(io.StringIO()):
            assert rp.previous(argparse.Namespace(out=str(got), repo=["TheologyAIGeek/Hookshot"], skip_tag="")) == 0
        assert printed.getvalue().strip() == "builder-parts" and got.read_text(encoding="utf-8").splitlines() == lines
        releases.append({"draft": False, "prerelease": False, "tag_name": "v3.0.4",
                         "assets": [{"name": "hookshot-setup.txt", "browser_download_url": "https://github.com/x/stable/hookshot-setup.txt"}]})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            assert rp.previous(argparse.Namespace(out=str(got), repo=["TheologyAIGeek/Hookshot"], skip_tag="")) == 0
        assert printed.getvalue().strip() == "v3.0.4" and got.read_text() == "tag v3.0.4\n", "a stable release's list comes first"
        print("PASS: CI takes a stable release's list first, else the seed list on builder-parts")

        # (a folder without python, cpm or third_party is no Builder's tools folder)
        bare = tmp / "bare" / "tools"
        (bare / "python").mkdir(parents=True)
        (bare / "python" / "python.exe").write_bytes(b"py")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                seed_mod.seed(str(bare), str(tmp / "out3"))
        except SystemExit as e:
            assert "no cpm" in str(e), e
        else:
            raise AssertionError("a tools folder with no cpm was taken")
        print("PASS: a tools folder missing a part the Builder needs is refused")


if __name__ == "__main__":
    main()
