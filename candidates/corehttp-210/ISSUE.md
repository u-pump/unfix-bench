# HTTPClient_Send() fails with HTTPParserInternalError when a receive ends exactly at the end of a header field name

A response header such as `Content-Length: 4` can arrive split over two transport reads so that the first read ends right after `Content-Length` and the second one starts at the `:`. HTTPClient_Send() then returns HTTPParserInternalError although the response is valid. The same happens for a transport that returns one byte per read, whenever a read boundary falls directly after a header field name. Splitting in the middle of a field name or in the middle of a value works.

Expected:
- A valid response whose first read ends exactly at the end of a header field name is parsed successfully (HTTPSuccess), with the same status code, headers, header count and content length as when it arrives in one piece.
- A header field name that is really empty is still an error.
