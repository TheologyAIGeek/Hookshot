"""Which GPU ASTC decoder the Vulkan back end runs (gpu/vk/astc_decoder_pick.h, vk_texture.cpp astc_ready; no game, no GPU).

The decoder made faster in 8fe93bbf (its scratch in workgroup memory) draws nothing on NVIDIA's driver: on an RTX 3080 Ti
Laptop (driver 621.40) the title logo, the pause menu's item icons and every big ASTC texture were blank or black, and came
back with RX_VK_ASTC_CPU=1 and with v3.0.2's renderer. NVIDIA's driver runs the decoder as it was before (the classic one).
Checked:

- astc_ready makes its pipeline from the decoder astc_decoder_pick::pick chooses, by RX_VK_ASTC_DECODER and whether the
  device runs NVIDIA's own driver, and says which in its log line (on main it builds the faster one on every device);
- pick, compiled and run: classic on NVIDIA's driver and lds elsewhere, unset; RX_VK_ASTC_DECODER=classic or =lds over that on
  any device; another value as unset;
- both decoders are compiled in: two SPIR-V arrays, each a module (its magic word), not the same words.

That the classic decoder draws right on NVIDIA's driver is the game's to show (no NVIDIA GPU in CI); that both decode as the
CPU reference does is tests/test_astc_decoder_gpu.py --gpu's.

python -I -B tests/test_astc_decoder_pick.py [--cxx g++]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
TEXTURE = ROOT / "gpu/vk/vk_texture.cpp"
SHADERS = ROOT / "gpu/vk/host_shaders"

PROGRAM = r"""
#include "astc_decoder_pick.h"
#include <cstdio>
using astc_decoder_pick::Decoder;
using astc_decoder_pick::pick;
static int bad = 0;
static void want(const char* sw, bool nvidia, Decoder d) {
    const Decoder got = pick(sw, nvidia);
    if (got != d) {
        std::printf("FAIL: RX_VK_ASTC_DECODER=%s on %s: %s, wanted %s\n", sw ? sw : "(unset)", nvidia ? "NVIDIA's driver" : "another driver",
                    astc_decoder_pick::name(got), astc_decoder_pick::name(d));
        bad++;
    }
}
int main() {
    want(nullptr, true, Decoder::classic);
    want(nullptr, false, Decoder::lds);
    want("classic", false, Decoder::classic);
    want("classic", true, Decoder::classic);
    want("lds", true, Decoder::lds);
    want("lds", false, Decoder::lds);
    want("", true, Decoder::classic);
    want("CLASSIC", false, Decoder::lds);
    want("1", true, Decoder::classic);
    want("0", false, Decoder::lds);
    return bad ? 1 : 0;
}
"""


def body_of(src, signature):
    """The text of the function whose definition starts with signature, from it to its closing brace"""
    at = src.find(signature)
    if at < 0:
        return None
    i = src.index("{", at)
    depth = 0
    for j in range(i, len(src)):
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        if depth == 0:
            return src[at:j + 1]
    return None


def check_wiring():
    src = TEXTURE.read_text(encoding="utf-8")
    body = body_of(src, "bool astc_ready()")
    if body is None:
        sys.exit("vk_texture.cpp has no astc_ready(): update this check")
    if "ASTC_DECODER_CLASSIC_COMP_SPV" not in body or "astc_decoder_pick::pick(" not in body:
        sys.exit("FAIL: astc_ready makes ASTC_DECODER_COMP_SPV (the decoder of 8fe93bbf) on every device: NVIDIA's driver "
                 "draws the textures it decodes blank or black, and nothing picks the classic decoder there")
    for needle in ('getenv("RX_VK_ASTC_DECODER")', "VK_DRIVER_ID_NVIDIA_PROPRIETARY", "BUILTIN_SPV(ASTC_DECODER_COMP_SPV)",
                   "BUILTIN_SPV(ASTC_DECODER_CLASSIC_COMP_SPV)", "astc_decoder_pick::name("):
        if needle not in body:
            sys.exit("FAIL: astc_ready no longer has " + needle)
    for needle in ('#include "astc_decoder_pick.h"', '#include "host_shaders/astc_decoder_classic_comp_spv.h"'):
        if needle not in src:
            sys.exit("FAIL: vk_texture.cpp no longer has " + needle)
    print("PASS: astc_ready makes the decoder pick chooses, by RX_VK_ASTC_DECODER and NVIDIA's driver, and logs which")


def words(path):
    text = path.read_text(encoding="utf-8")
    return re.findall(r"0x[0-9a-fA-F]{8}", text[text.index("{"):])


def check_shaders():
    lds, classic = words(SHADERS / "astc_decoder_comp_spv.h"), words(SHADERS / "astc_decoder_classic_comp_spv.h")
    assert lds and classic and lds[0].lower() == classic[0].lower() == "0x07230203", "a decoder header is not a SPIR-V module"
    assert lds != classic, "the classic decoder's header holds the same SPIR-V as the lds one's"
    assert "ASTC_DECODER_CLASSIC_COMP_SPV[]" in (SHADERS / "astc_decoder_classic_comp_spv.h").read_text(encoding="utf-8")
    print("PASS: both decoders are compiled in (%d and %d SPIR-V words)" % (len(lds), len(classic)))


def check_pick(cxx):
    with tempfile.TemporaryDirectory(prefix="astc-decoder-pick-") as tmp:
        src, exe = Path(tmp) / "pick.cpp", Path(tmp) / "pick"
        src.write_text(PROGRAM, encoding="utf-8")
        subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu/vk"), str(src), "-o", str(exe)],
                       check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode:
            sys.exit("FAIL: astc_decoder_pick::pick")
    print("PASS: classic on NVIDIA's driver and lds elsewhere; RX_VK_ASTC_DECODER=classic|lds over that on any device")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    check_wiring()
    check_shaders()
    check_pick(a.cxx)


if __name__ == "__main__":
    main()
