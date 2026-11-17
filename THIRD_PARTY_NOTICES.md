# Third-party notices

Agent patches in `cases/**/agents/**/agent-fix.patch` modify third-party source code. Those patches and any reproduced upstream code fragments are governed by the license of the respective upstream project, rather than U-Pump's [MIT](LICENSES/MIT.txt) or [CC BY 4.0](LICENSES/CC-BY-4.0.txt) licenses. The links below point to the license file at each case's exact `base` commit in `case.yaml`.

| Upstream project | Repository | SPDX license | License at case base commit |
| --- | --- | --- | --- |
| coreMQTT | [FreeRTOS/coreMQTT](https://github.com/FreeRTOS/coreMQTT) | MIT | [coremqtt-331](https://github.com/FreeRTOS/coreMQTT/blob/ad72f6aff6c08ac7fe91d7aac0ea6b046b52cd94/LICENSE) |
| cpp-peglib | [yhirose/cpp-peglib](https://github.com/yhirose/cpp-peglib) | MIT | [cpp-peglib-121](https://github.com/yhirose/cpp-peglib/blob/14305f9f53cde207568f21675a1b9294a3ab28b4/LICENSE) |
| fmt | [fmtlib/fmt](https://github.com/fmtlib/fmt) | MIT | [fmt-4490](https://github.com/fmtlib/fmt/blob/8f3a965186d49dba299a2302bee1bd093401b969/LICENSE), [fmt-4742](https://github.com/fmtlib/fmt/blob/be98ea8addfd8f0dd6f319e7818f94988728ca0a/LICENSE), [fmt-4800](https://github.com/fmtlib/fmt/blob/e60274b29c0a748df2c6280d0a374e6eef3b6c73/LICENSE), [fmt-4933](https://github.com/fmtlib/fmt/blob/8dc5d3f69f15417d13c60a4a21f7298ed24db41c/LICENSE), [fmt-4942](https://github.com/fmtlib/fmt/blob/fd0a9b6620c8f44fac2122adb1cc29664aa96325/LICENSE), [fmt-4960](https://github.com/fmtlib/fmt/blob/4afd0e498e9e1dd68775cc52087df774a19c761f/LICENSE), [fmt-4978](https://github.com/fmtlib/fmt/blob/89a7f4a7ca354bf008d9810fc86bc06d97631dbc/LICENSE) |
| spdlog | [gabime/spdlog](https://github.com/gabime/spdlog) | MIT | [spdlog-3049](https://github.com/gabime/spdlog/blob/6766f873d680e696c29541dbd144f4ef0785f547/LICENSE) |
| zlib-ng | [zlib-ng/zlib-ng](https://github.com/zlib-ng/zlib-ng) | Zlib | [zlibng-2465](https://github.com/zlib-ng/zlib-ng/blob/75eb731258d9a2dc0fe6180f6d0d45e440da140f/LICENSE.md) |

Only the fmt license at the `fmt-4490` base commit includes an optional exception for portions embedded in compiled object code. The six later fmt base commits listed above contain the standard MIT text without that exception. The spdlog license file also notes its dependency on fmt. Consult the linked license files for their complete terms.
