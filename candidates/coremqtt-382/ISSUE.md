<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix property serialization bounds checks

Source: https://github.com/FreeRTOS/coreMQTT/pull/382

Description
-----------
Fix property serialization bounds checks


Thank you XueDugu for reporting the issue.

Test Steps
-----------
- Added `test_MQTTPropAdd_ReasonString_BufferTooSmall` to `core_mqtt_prop_serializer_utest.c`. 
- Added a CBMC proof `test/cbmc/proofs/MQTTPropAdd_ReasonString/` covering the write path of `addPropUtf8` via `MQTTPropAdd_ReasonString`. 

Checklist:
----------
- [x] I have tested my changes. No regression in existing tests.
- [x] I have modified and/or added unit-tests to cover the code changes in this Pull Request.

Related Issue
-----------
N/A

By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
