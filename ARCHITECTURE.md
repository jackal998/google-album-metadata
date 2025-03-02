# Google Album Metadata Tool - Architecture

This document provides an overview of the Google Album Metadata Tool architecture, explaining the main components and how they interact with each other.

## Directory Structure

```
google-album-metadata/
├── bin/
│   ├── g_album_tool           # Main executable
│   └── run_tests              # Test runner script
├── lib/
│   ├── g_album_tools.rb       # Main library file
│   └── g_album_tools/
│       ├── base.rb            # Base class with common utilities
│       ├── cli.rb             # Command Line Interface
│       ├── constants.rb       # Constants and configuration
│       ├── error_handler.rb   # Error handling and management
│       ├── error_types.rb     # Error categories and patterns
│       ├── file_processor.rb  # File discovery and processing
│       ├── handlers/          # Specialized error handlers
│       │   ├── base_handler.rb
│       │   ├── default_handler.rb
│       │   ├── extension_handler.rb
│       │   ├── maker_notes_handler.rb
│       │   ├── metadata_handler.rb
│       │   └── truncated_media_handler.rb
│       ├── metadata_processor.rb # JSON metadata processing
│       └── version.rb         # Version information
├── tests/
│   ├── fixtures/              # Test fixtures
│   │   ├── csv/               # CSV test files
│   │   ├── destination/       # Destination test files
│   │   └── media/             # Media test files
│   └── test_*.rb              # Test files
├── ERROR_SUMMARY.md           # Error handling documentation
└── README.md                  # Project documentation
```

## Core Components

### Base Class

The `Base` class (`lib/g_album_tools/base.rb`) provides common utilities used throughout the application:

- Logging functionality with different levels (info, warn, error)
- Command execution with error handling
- String cleaning and encoding handling
- Common file operations

### File Processor

The `FileProcessor` class (`lib/g_album_tools/file_processor.rb`) handles:

- File discovery in source directories
- Checking for file existence
- Finding JSON metadata files for media files
- Processing directories with media files
- Creating CSV output files with processing results

### Metadata Processor

The `MetadataProcessor` class (`lib/g_album_tools/metadata_processor.rb`) is responsible for:

- Orchestrating the overall processing flow
- Parsing JSON metadata files
- Applying metadata to media files using ExifTool
- Handling time offsets for metadata synchronization

### Error Handler

The `ErrorHandler` class (`lib/g_album_tools/error_handler.rb`) manages:

- Error categorization and analysis
- Loading errors from CSV output files
- Fixing errors using specialized handlers
- Generating error statistics and summaries

### Error Types

The `ErrorTypes` module (`lib/g_album_tools/error_types.rb`) defines:

- Error type constants
- Error matching patterns
- Functions for categorizing errors based on error messages

### Specialized Error Handlers

The `handlers` directory contains specialized classes for handling different types of errors:

- `BaseHandler`: Common functionality for all handlers
- `MetadataHandler`: Handles missing metadata issues
- `ExtensionHandler`: Fixes file extension problems
- `TruncatedMediaHandler`: Manages corrupted media files
- `MakerNotesHandler`: Handles maker notes issues in EXIF data
- `DefaultHandler`: Generic fallback for other error types

### Command Line Interface

The `CLI` class (`lib/g_album_tools/cli.rb`) provides:

- Command-line argument parsing
- Implementation of commands (process, analyze, fix-errors)
- Validation of user input

## Processing Flow

1. User invokes the application via the command-line interface
2. The CLI parses arguments and delegates to the appropriate handler:
   - For `process`: MetadataProcessor
   - For `analyze`: ErrorHandler's analysis methods
   - For `fix-errors`: ErrorHandler's process method

### Processing Command Flow

```
CLI -> MetadataProcessor -> FileProcessor -> 
  [for each file] -> Read JSON -> Apply metadata with ExifTool -> Create CSV output
```

### Fix-Errors Command Flow

```
CLI -> ErrorHandler -> [for each directory] -> 
  Read output CSV -> [for each error] -> 
    Categorize error -> Get appropriate handler -> Handle error -> Update CSV
```

## Error Handling Strategy

The application uses a specialized approach for error handling:

1. Each type of error (missing metadata, unknown filename pattern, etc.) has a dedicated handler class
2. The `ErrorHandler` class analyzes errors and delegates to the appropriate handler
3. Handlers attempt to fix the issue, using strategies specific to the error type
4. The output CSV file is updated to reflect the results of the fix attempt

## Test Structure

The test directory contains:

- Unit tests for each main component
- Fixtures for testing (CSV files, media files, etc.)
- A test runner script for easy test execution

## Design Principles

- **Modularity**: Each class has a single responsibility
- **Extensibility**: New error handlers can be added without modifying existing code
- **Error Management**: Comprehensive error handling and logging
- **Documentation**: Extensive inline documentation and external documentation files 
