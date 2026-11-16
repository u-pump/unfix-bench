<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix compiler warnings with optimizations enabled

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1218

<!--- Title -->

Description
-----------
This PR fixes compiler warnings that are generated when compiled with optimizations enabled in GCC and adds CI build checks with optimization settings on.

Thanks, @StefanBalt, for reporting this issue in #1217.

This PR also fixes the false positive warnings emitted by GCC version GNU 13.1.0:

``` sh
/home/ubuntu/Projects/FreeRTOS-Plus-TCP/source/FreeRTOS_DNS_Callback.c: In function ‘xDNSDoCallback’:
/home/ubuntu/Projects/FreeRTOS-Plus-TCP/build/_deps/freertos_kernel-src/include/./list.h:241:75: error: array subscript ‘ListItem_t {aka const struct xLIST_ITEM}[0]’ is partly outside array bounds of ‘List_t[1]’ {aka ‘struct xLIST[1]’} [-Werror=array-bounds=]
  241 | #define listGET_NEXT( pxListItem )                        ( ( pxListItem )->pxNext )
      |                                                                           ^~
/home/ubuntu/Projects/FreeRTOS-Plus-TCP/source/FreeRTOS_DNS_Callback.c:72:54: note: in expansion of macro ‘listGET_NEXT’
   72 |             for( pxIterator = ( const ListItem_t * ) listGET_NEXT( pxEnd );
      |                                                      ^~~~~~~~~~~~
/home/ubuntu/Projects/FreeRTOS-Plus-TCP/source/FreeRTOS_DNS_Callback.c:45:19: note: at offset 16 into object ‘xCallbackList’ of size 40
   45 |     static List_t xCallbackList;
```

Test Steps
-----------
Tested with DNS

Checklist:
----------
<!--- Go over all the following points, and put an `x` in all the boxes that apply. -->
<!--- If you're unsure about any of these, don't hesitate to ask. We're here to help! -->
- [x] I have tested my changes. No regression in existing tests.
- ~[ ] I have modified and/or added unit-tests to cover the code changes in this Pull Request.~

Related Issue
-----------
#1217 


By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.
