<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix for name resolution responses containing 0.0.0.0

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1127

Description
-----------
Note that the DUTs described below power up with an IPv4 endpoint set to 0.0.0.0 and after a short initial wait, that endpoint gets assigned a valid IPv4 address like for example 172.30.30.215
Even though this may be a bit controversial, configuring +TCP to use a DHCP server would have the very similar effect of the IPv4 endpoint having its ipv4_settings.ulIPAddress set to 0.0.0.0 in the very early stages of the boot process.

I was working with 2 DUTs both running FreeRTOS+TCP. On power up, DUT_1 attempts to resolve DUT_2's IP address by name and then send UDP data to it. Since DUT_1 is pretty quick to begin sending mDNS and LLMNR request, DUT_2 was responding to them with 0.0.0.0 in the answer field.
This caused DUT_1 to call the user callback given to `FreeRTOS_getaddrinfo_a()` and also to store this 0.0.0.0 address in the DNS cache.

My resolution was 4-fold:

1. Modify my `xApplicationDNSQueryHook_Multi()` to return pdFALSE if my IPv4 endpoint had and IP address of 0.0.0.0 This of course is up to the user and as such is not part of this PR.
2. Modify my `FreeRTOS_getaddrinfo_a()` callback to ignore responses with 0.0.0.0. As this is also part of the user code, it is not part of this PR.
3. Force +TCP to drop mDNS and LLMNR responses the mention 0.0.0.0 in their answer. This prevents storing this invalid address in the DNS cache.
4. Ensure that +TCP never sends responses when the IPv4 endpoint modified by  `xApplicationDNSQueryHook_Multi()` has its `ipv4_settings.ulIPAddress` equal to zero.

In my specific test scenario, any one of the fixes above solves the problem, but in the general case where one of the devices is not a FreeRTOS+TCP device, I think it's best to have all 3 safeguards in place. 

Wireshark capture:
For the purposes of the capture, I allowed DUT_1 to power up first. Then, after it began sending it's LLMNR/mDNS request, I powered up DUT_2.
[LLMNR_Responses_0_0_0_0.zip](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/files/14838450/LLMNR_Responses_0_0_0_0.zip)
In this capture, DUT begins responding around the 2 second mark, but it still does not have a valid IP.
Around the 4 second mark DUT responds with it's valid IP.

This was a fairly quick fix, so please feel free to suggest better/cleaner solutions.
I also have not examined or tried to reproduce similar issues with IPv6. Potentially there may be similar problems if we receive responses with "::" in the answer.

By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
