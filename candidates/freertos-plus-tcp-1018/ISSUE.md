# FreeRTOS_send() with a NULL buffer always fails (TCP zero copy)

For a TCP socket, FreeRTOS_send() called with pvBuffer == NULL is the zero-copy mode: the caller has already placed the data in the socket's transmit stream buffer and only asks the stack to send it. This used to work, but now the call always fails with -pdFREERTOS_ERRNO_EINVAL, even for an established connection with enough space in the stream buffer.

Expected:
- FreeRTOS_send( socket, NULL, uxDataLength, flags ) on an established TCP socket with room in the transmit stream buffer returns the number of bytes accepted (uxDataLength).
- When the stream buffer has less space than uxDataLength, it returns the number of bytes that fit.
- The checks of the socket (valid TCP socket, not closed or closing, uxDataLength non-zero) are still made.
