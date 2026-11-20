# Removed from the draft ISSUE.md of corehttp-210

Removed: The upstream pull request text. It explains the cause (zero-length on_header_field callback from llhttp, the guard added in #204) and the fix (reject a zero-length field only when no header field is in progress).

Kept out of ISSUE.md on purpose (the agent must not see them; they are in `case.yaml`):

- upstream pull request: https://github.com/FreeRTOS/coreHTTP/pull/210
- upstream fix: https://github.com/FreeRTOS/coreHTTP/commit/9cf8c78a17721193795d77de6f006162132a8991
- reference test: `test_HTTPClient_Send_parse_complete_header_field_at_read_boundary` (ctest test core_http_send_utest; granularity `ctest_module`)
- build: `cmake -S test -B build -DCMAKE_BUILD_TYPE=Debug -DUNITTEST=1 -DBUILD_CLONE_SUBMODULES=OFF && cmake --build build -j2`
- test: `ctest --test-dir build -R '^core_http_send_utest$' --output-on-failure`
