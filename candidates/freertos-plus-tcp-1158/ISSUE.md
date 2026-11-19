<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix Buffer Over-Read (CWE-126) in DNS Response Parser

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1158

Description
-----------
This change addresses a potential buffer over-read in the DNS Response Parser when parsing domain names in a DNS response. A carefully crafted DNS response with domain name length value greater than the actual domain name length, could cause the parser to read beyond the DNS response buffer. This issue affects applications using DNS functionality of the FreeRTOS-Plus-TCP stack. Applications that do not use DNS functionality are not affected, even when the DNS functionality is enabled.

This issue has been fixed by modifying the code to ensure that the DNS Response Parser never attempts to read beyond the DNS response buffer boundary.

We would like to thank Paschal Amusuo, James C. Davis, and Aravind Machiry of Purdue University, for reporting this issue.

Test Steps
-----------
<!-- Describe the steps to reproduce. -->

Checklist:
----------
<!--- Go over all the following points, and put an `x` in all the boxes that apply. -->
<!--- If you're unsure about any of these, don't hesitate to ask. We're here to help! -->
- [x] I have tested my changes. No regression in existing tests.
- [x] I have modified and/or added unit-tests to cover the code changes in this Pull Request.

Related Issue
-----------
<!-- If any, please provide issue ID. -->


By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
