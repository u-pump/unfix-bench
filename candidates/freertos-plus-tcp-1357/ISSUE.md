<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix IPv6 address printing bounds checks

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1357

Description
-----------
Fix IPv6 address printing bounds checks


Thank you XueDugu for reporting the issue.

Test Steps
-----------
- Added `test_FreeRTOS_inet_ntop6_MaxAddressExactSize` to `FreeRTOS_Sockets_IPv6_utest.c`. 
- Added a CBMC proof `test/cbmc/proofs/FreeRTOS_inet_ntop6/`. 

Checklist:
----------
- [x] I have tested my changes. No regression in existing tests.
- [x] I have modified and/or added unit-tests to cover the code changes in this Pull Request.

Related Issue
-----------
N/A

By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
