# Removed from the draft ISSUE.md of freertos-plus-tcp-1018

Removed: The upstream pull request text ("Fixes the TCP zero-copy functionality...", reference to #1008). It points at the NULL-buffer case of FreeRTOS_send().

Kept out of ISSUE.md on purpose (the agent must not see them; they are in `case.yaml`):

- upstream pull request: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1018
- upstream fix: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/commit/c9e63fcbe819bf5f423970e8cc965c331aff2de7
- reference test: `test_FreeRTOS_send_IPTaskWithNULLBuffer` (ctest test FreeRTOS_Sockets_TCP_API_utest; granularity `ctest_module`)
- build: `cmake -S test/unit-test -B build -G Ninja -DBUILD_CLONE_SUBMODULES=OFF && cmake --build build -j2`
- test: `ctest --test-dir build -R '^FreeRTOS_Sockets_TCP_API_utest$' --output-on-failure`
