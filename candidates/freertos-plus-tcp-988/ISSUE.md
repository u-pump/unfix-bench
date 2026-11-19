<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Gratuituous ARP fixes 

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/988

<!--- Title -->

Description
-----------
This PR updates the Gratuitous ARP processing with more checks including verification of the packet for target hardware address and the subnet of the protocol address.

Test Steps
-----------
Jenkins and HW demo run.

Checklist:
----------
<!--- Go over all the following points, and put an `x` in all the boxes that apply. -->
<!--- If you're unsure about any of these, don't hesitate to ask. We're here to help! -->
- [ ] I have tested my changes. No regression in existing tests.
- [x] I have modified and/or added unit-tests to cover the code changes in this Pull Request.

Related Issue
-----------
<!-- If any, please provide issue ID. -->


By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
