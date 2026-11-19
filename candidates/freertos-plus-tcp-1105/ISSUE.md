<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fixes ARP messages from being sent through wrong endpoints

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1105

<!--- Title -->

Description
-----------
This PR fixes #1088, by adding a new API `FreeRTOS_OutputARPRequest_Multi` which requires the interface to be targeted while sending the ARP messages. 

This PR also fixes some variable declarations that are present after code.

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
#1088 

By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
