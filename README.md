# Google Album Metadata Tool

A command-line tool for processing metadata from Google Photos Takeout files.

## Features

- Process metadata from JSON files in Google Photos Takeout directories
- Apply metadata to media files using ExifTool
- Generate CSV output files with processing status
- Fix common errors in processed files

## Requirements

- Ruby 2.6 or later
- ExifTool (must be installed and available in your PATH)

## Installation

1. Clone this repository
2. Add the `bin` directory to your PATH or use the full path to the executable

## Usage

### Process metadata from a source directory to a destination directory

```bash
bin/g_album_tool process SOURCE_DIR DESTINATION_DIR
```

### Fix errors in processed files

```bash
bin/g_album_tool fix-errors DESTINATION_DIR
```

### Options

- `-v, --verbose`: Run with verbose output
- `--no-csv`: Don't create CSV output files
- `--nested`: Process nested directories (for fix-errors command)
- `-h, --help`: Show help message
- `--version`: Show version

## Project Structure

```
lib/
├── g_album_tools.rb              # Main require file
├── g_album_tools/
    ├── version.rb                # Version information
    ├── constants.rb              # Shared constants
    ├── base.rb                   # Base class with common functionality
    ├── file_processor.rb         # File processing logic
    ├── metadata_processor.rb     # Metadata extraction and application
    ├── error_handler.rb          # Error handling and fixing
    └── cli.rb                    # Command-line interface
bin/
└── g_album_tool                  # Executable entry point
```

## License

MIT
