<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fixes the TCP zero-copy functionality...

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1018

As discussed in #1008 
It appears that this worked at some point but then got broken.
To reproduce: call FreeRTOS_send() with pvBuffer being NULL and the call always fails.
