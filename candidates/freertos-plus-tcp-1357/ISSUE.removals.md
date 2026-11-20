# Removed from the draft ISSUE.md of freertos-plus-tcp-1357

Removed: The upstream pull request text ("Fix IPv6 address printing bounds checks", reporter thanks, the new test and the CBMC proof). It names the fix area and the test.

Kept out of ISSUE.md on purpose (the agent must not see them; they are in `case.yaml`):

- upstream pull request: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1357
- upstream fix: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/commit/4e95d077203b86b103315fa90ad7889077467697
- reference test: `test_FreeRTOS_inet_ntop6_MaxAddressExactSize` (ctest test FreeRTOS_Sockets_IPv6_utest; granularity `ctest_module`)
- build: `cmake -S test/unit-test -B build -G Ninja -DBUILD_CLONE_SUBMODULES=OFF && cmake --build build -j2`
- test: `ctest --test-dir build -R '^FreeRTOS_Sockets_IPv6_utest$' --output-on-failure`
