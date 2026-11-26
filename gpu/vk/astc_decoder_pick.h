// (Hookshot) Which GPU ASTC decoder the Vulkan back end runs (vk_texture.cpp astc_ready). tests/test_astc_decoder_pick.py
//
// Two builds of Eden's decoder are compiled in:
// - lds (host_shaders/astc_decoder.comp, 8fe93bbf): its scratch in workgroup memory and its per-texel loops hoisted, 5.3x
//   faster on the terrain arrays of an AMD Radeon 860M, the only device it was tested on.
// - classic (host_shaders/astc_decoder_classic.comp): the decoder as it was before, in v3.0.2 and earlier.
// On NVIDIA's driver the lds one writes nothing a draw can see: an RTX 3080 Ti Laptop (driver 621.40) showed no title logo,
// no item icons in the pause menu, dark hearts, and black rocks, cliffs and horse in Hyrule Field, all of which came back with
// RX_VK_ASTC_CPU=1 and with v3.0.2's renderer on the same PC. It passes the repository's GPU fixture on lavapipe, so the
// difference is the NVIDIA shader compiler's; until that is found, NVIDIA's driver runs the classic one.
#pragma once
#include <cstring>

namespace astc_decoder_pick {

enum class Decoder { lds, classic };

/// sw: RX_VK_ASTC_DECODER's value (null: unset); nvidia: the device runs NVIDIA's own driver (VK_DRIVER_ID_NVIDIA_PROPRIETARY).
/// "classic" or "lds" picks that decoder on any device; unset (or anything else), classic on NVIDIA's driver, lds elsewhere
inline Decoder pick(const char* sw, bool nvidia) {
    if (sw && !std::strcmp(sw, "classic")) return Decoder::classic;
    if (sw && !std::strcmp(sw, "lds")) return Decoder::lds;
    return nvidia ? Decoder::classic : Decoder::lds;
}

inline const char* name(Decoder d) {
    return d == Decoder::classic ? "classic" : "lds";
}

} // namespace astc_decoder_pick
