# FreeRTOS_inet_ntop6() writes the NUL terminator outside the destination buffer

FreeRTOS_inet_ntop6() converts a 16-byte IPv6 address into text. The longest text form is 39 characters, so a destination of 40 bytes is needed to hold it together with the terminating NUL. When the caller passes a size of exactly 39 for such an address, the function does not notice that there is no room for the terminator and writes it at index 39, one byte past the end of the buffer the caller declared.

Expected:
- For an address whose text form is 39 characters long (for example ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff) and a destination size of 39, the function returns NULL and does not write at index 39 or after it.
- With a destination size of 40 or more the same address is converted as before.
- Shorter addresses and smaller sizes behave as before.
