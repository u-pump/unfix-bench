# DNS reply parser reads past the end of the received packet when a name is longer than the data

When the DNS reply parser handles an answer record, it walks over the name field of the record. If a crafted reply declares a name that is longer than the bytes left in the packet, the parser keeps walking beyond the end of the received data instead of treating the reply as malformed.

Expected:
- parseDNSAnswer() returns 0 and reports 0 bytes read when the name field of the answer record is longer than the remaining bytes of the reply.
- It never reads beyond the end of the reply.
- Well-formed replies are parsed as before.
