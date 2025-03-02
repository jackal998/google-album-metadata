# Google Album Metadata Tool

A command-line tool for processing metadata from Google Photos Takeout files and applying it to your media files.

## Features

- Extracts metadata from Google Photos JSON files and applies it to corresponding media files
- Handles live photos (paired image/video files)
- Supports various image and video formats
- Generates CSV output files with processing results
- Includes comprehensive error handling and recovery
- Provides tools for analyzing and fixing errors

## Requirements

- Ruby 2.6 or higher
- ExifTool

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/google-album-metadata.git
   cd google-album-metadata
   ```

2. Install ExifTool:
   - Mac: `brew install exiftool`
   - Linux: `apt install libimage-exiftool-perl` or equivalent
   - Windows: Download from [ExifTool website](https://exiftool.org/)

3. Ensure the `bin/g_album_tool` script is executable:
   ```
   chmod +x bin/g_album_tool
   ```

## Usage

### Process metadata from Google Photos Takeout

```
bin/g_album_tool process SOURCE_DIR DEST_DIR
```

This command will:
1. Scan for media files in SOURCE_DIR
2. Find corresponding JSON metadata files
3. Apply the metadata to the media files
4. Save the processed files to DEST_DIR
5. Generate CSV output files with processing results

### Analyze errors in CSV output files

```
bin/g_album_tool analyze CSV_DIR
```

This command will:
1. Find all CSV output files in CSV_DIR
2. Analyze error patterns and provide statistics

### Fix errors in processed files

```
bin/g_album_tool fix-errors DEST_DIR
```

This command will:
1. Find all CSV output files in DEST_DIR
2. Identify files with errors
3. Apply appropriate fixes based on error type
4. Update the files in place and mark them as processed in the CSV

### Options

- `-v, --verbose`: Show detailed output
- `-n, --nested`: Process nested directories
- `--no-csv`: Disable CSV output file creation
- `-o, --offset-file FILE`: Specify a CSV file with offset times
- `--version`: Show version
- `-h, --help`: Show help message

## Error Types

The tool categorizes errors into four main types:

1. **No JSON File**: Media files without corresponding JSON metadata
2. **Unknown Filename Pattern**: Files with naming patterns that don't match Google Photos pattern
3. **Live Photo Missing Part**: Live photos with missing image or video component
4. **Invalid or Truncated File**: Files that appear to be damaged or incomplete

See [ERROR_SUMMARY.md](ERROR_SUMMARY.md) for more details on error handling strategies.

## Project Structure

```
google-album-metadata/
├── bin/
│   ├── g_album_tool      # Main executable
│   └── run_tests         # Test runner script
├── lib/
│   ├── g_album_tools.rb  # Main module file
│   └── g_album_tools/    # Module components
│       ├── base.rb
│       ├── cli.rb
│       ├── constants.rb
│       ├── error_handler.rb
│       ├── error_types.rb
│       ├── file_processor.rb
│       ├── handlers/     # Error handlers
│       │   ├── base_handler.rb
│       │   ├── default_handler.rb
│       │   ├── extension_handler.rb
│       │   ├── maker_notes_handler.rb
│       │   ├── metadata_handler.rb
│       │   └── truncated_media_handler.rb
│       ├── metadata_processor.rb
│       └── version.rb
├── tests/                # Test files
│   ├── fixtures/         # Test fixtures
│   └── test_*.rb         # Test files
├── ARCHITECTURE.md       # Architecture documentation
├── ERROR_SUMMARY.md      # Error handling documentation
├── README.md             # This file
└── spec.md              # Project specifications
```

For a detailed explanation of the codebase architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
