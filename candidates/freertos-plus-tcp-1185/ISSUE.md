<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix ARP failure with loopback addresses

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1185

<!--- Title -->

Description
-----------
This PR updates the `eARPGetCacheEntry` to handle loopback addresses correctly and assign the loopback endpoint's MAC address as the lookup MAC address. 

Update the loopback interface to refresh the ARP/ND caches correctly and drop packets that cannot find a matching endpoint that can handle the packet.

We thank @htibosch for this fix.

Also thanks to @rickou and [@grap](https://forums.freertos.org/u/grap/summary) for reporting this issue in #1179 and in the [FreeRTOS forum.](https://forums.freertos.org/t/freertos-tcp-how-to-use-loopback-interface-on-stm32h723-board/21370)


Test Steps
-----------
Loopback test on TCP socket with STM32H7 NUCLEO.

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
