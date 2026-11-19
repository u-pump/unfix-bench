<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Neighbor Solicitation Response Fix

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1096

Description
-----------
IPv6 Neighbor Solicitation Responses could go out the wrong interface. Fixed by using `pxNetworkBuffer->pxEndPoint` instead of searching for and end-point.

I allowed myself the liberty of cleaning up a bit and also enforcing that pxNetworkBuffer, pxNetworkBuffer->pxInterface, and pxNetworkBuffer->pxEndPoint are non-NULL for ALL received packets.

@shubnil , @htibosch, @HTRamsey,  Please let me know what you think

Related Issue
-----------
#1093 


By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
