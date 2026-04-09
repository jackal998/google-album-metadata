# Refactor GAlbumTool into GAlbumTools with Enhanced Error Handling

## Purpose of Changes
This PR refactors the existing `GAlbumTool` class into a more modular structure under the new `GAlbumTools` namespace. It introduces improved error handling capabilities for processing media files and their associated metadata.

## Summary of Implementation Details
- **Refactoring**: The monolithic `GAlbumTool` class is replaced with a set of classes organized under the `GAlbumTools` module, making the codebase easier to manage and extend.
- **New Error Handling System**: A new `ErrorManager` class is introduced, along with specific error handler classes for different error types (e.g., `MissingMetadata`, `FileExists`, `IncorrectExtension`). These handle various errors encountered during metadata processing.
- **Command-Line Options**: Modifications to `galbumtool` command-line options to support new features, including a new `--process-errors` option for processing error files from previous runs.
- **Output Management**: The output CSV generation now captures processing results more effectively, including error messages for failed operations.

## Technical Decisions and Trade-offs
- The decision to refactor the code into multiple classes enhances maintainability and readability but may require updates in related documentation and usage instructions.
- Error handling is centralized, which means that specific error scenarios will automatically be processed without needing to modify multiple parts of the codebase.

## Related Issues
- This PR addresses several concerns outlined in issue #42 regarding error handling and processing failures in the metadata application workflow.
