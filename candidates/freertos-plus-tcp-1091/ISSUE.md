<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes every solution hint before this becomes an issue; nothing was removed automatically. -->

# Fix build warnings and update CI build checks to cover library header files

Source: https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1091

<!--- Title -->

Description
-----------
This PR fixes warnings related to C standard compliance and updates the CMake files to include the +TCP library header files to be included in the build checks.

Updates the unit tests with respect to the changes made.

Test Steps
-----------
Fix incompatable code and build checks in CI.

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
