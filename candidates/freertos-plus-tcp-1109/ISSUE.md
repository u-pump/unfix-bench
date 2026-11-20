<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix DNS to use correct DNS IP preference

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1109

<!--- Title -->

Description
-----------
This PR updates DNS code to use correct DNS IP preference which was previously only set to `xPreferenceIPv6` for IPv6 and then never updated.

Thanks @evpopov for detailed bug report: #1107 

This PR also removes the unused variable `xNeed_Endpoint`, as `xDNS_IP_Preference` can be either `xPreferenceIPv4` or `xPreferenceIPv6` only.

Test Steps
-----------
Tested DNSv4 query after DNSv6 query [no IPv6 connection/endpoint]:
```

/*==================== dnsq4  aws.amazon.com (2/4) ====================*/

xHandleTestingCommand: the function xHandleTesting() was not called
pxDNSLookup: 'aws.amazon.com' IPv4 Sync DNS-clear = false
ARP 192.168.0.1 miss using 192.168.0.1
pxEasyFit: ARP 192.168.0.100 -> 192.168.0.1
ipARP_REPLY from 192.168.0.1 to 192.168.0.100 end-point 192.168.0.100
DNS_ReadReply returns -11
prvIncreaseDNS4Index: from 0 to 0
FreeRTOS_ProcessDNSCache: add: 'aws.amazon.com' @ 65.8.79.190 (TTL 54)
DNS[0xAF80]: The answer to 'aws.amazon.com' (65.8.79.190) will be stored
FreeRTOS_getaddrinfo: rc 0
Found Address: 65.8.79.190
dns query4: 'aws.amazon.com' = 65.8.79.190 rc = 0


/*==================== dnsq6  google.nl (3/4) ====================*/

xHandleTestingCommand: the function xHandleTesting() was not called
pxDNSLookup: 'google.nl' IPv6 Sync DNS-clear = false
Can not find a DNS address, along with an end-point.
Can not find a DNS address, along with an end-point.
Can not find a DNS address, along with an end-point.
Can not find a DNS address, along with an end-point.
FreeRTOS_getaddrinfo: rc -2
dns query6: 'google.nl' No results


/*==================== dnsq4  google.es (4/4) ====================*/

xHandleTestingCommand: the function xHandleTesting() was not called
pxDNSLookup: 'google.es' IPv4 Sync DNS-clear = false
FreeRTOS_ProcessDNSCache: add: 'google.es' @ 142.250.77.163 (TTL 300)
DNS[0x9513]: The answer to 'google.es' (142.250.77.163) will be stored
FreeRTOS_getaddrinfo: rc 0
Found Address: 142.250.77.163
dns query4: 'google.es' = 142.250.77.163 rc = 0
Server task now ready.
pxEasyFit: ARP 192.168.0.1 -> 192.168.0.100
ipARP_REQUEST from 192.168.0.1 to 192.168.0.100 end-point 192.168.0.100

```

Checklist:
----------
<!--- Go over all the following points, and put an `x` in all the boxes that apply. -->
<!--- If you're unsure about any of these, don't hesitate to ask. We're here to help! -->
- [x] I have tested my changes. No regression in existing tests.
- [x] I have modified and/or added unit-tests to cover the code changes in this Pull Request.

Related Issue
-----------
<!-- If any, please provide issue ID. -->
#1107 

By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
