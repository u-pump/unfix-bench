# Removed from the draft ISSUE.md of freertos-plus-tcp-1158

Removed: The upstream pull request text ("Fix Buffer Over-Read (CWE-126) in DNS Response Parser", reporter thanks, statement that the parser must never read beyond the buffer).

Kept out of ISSUE.md on purpose (the agent must not see them; they are in `case.yaml`):

- upstream pull request: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1158
- upstream fix: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/commit/ba4e25c350020abcb787a3a319fdf991bef70538
- reference test: `test_parseDNSAnswer_recordNOTstored_gt_count_diffUsType` (ctest test FreeRTOS_DNS_Parser_utest; granularity `ctest_module`)
- build: `cmake -S test/unit-test -B build -G Ninja -DBUILD_CLONE_SUBMODULES=OFF && cmake --build build -j2`
- test: `ctest --test-dir build -R '^FreeRTOS_DNS_Parser_utest$' --output-on-failure`
