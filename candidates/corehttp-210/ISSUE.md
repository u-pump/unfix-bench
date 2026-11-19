<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix: accept zero-length header field continuation at receive boundaries

Source: https://github.com/FreeRTOS/coreHTTP/pull/210

<!--- Title -->

Description
-----------
When a transport receive ends exactly at the end of a header field name, llhttp reopens the field span at the start of the next llhttp_execute() buffer and closes it at the ':' separator, invoking on_header_field with a length of zero. This is a valid streaming continuation of the field.
The zero-length guard added to httpParserOnHeaderFieldCallback() in #204 rejected every zero-length callback with LLHTTP_STOP_PARSING, so valid responses failed with HTTPParserInternalError whenever a receive boundary fell right after a header field name (including byte-at-a-time receives).
Only reject a zero-length field when no header field is in progress. Genuinely empty header field names are still rejected by llhttp itself (HTTPSecurityAlertInvalidCharacter) before any span callback fires.

Test Steps
-----------
Add a unit test that splits the response at the end of a header field name and expects the response to parse successfully.

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
