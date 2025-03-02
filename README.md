# Google Album Metadata Tool

A command-line tool for processing metadata from Google Photos Takeout files and applying it to your media files.

## Quick Start Guide

```bash
# Clone the repository
git clone https://github.com/yourusername/google-album-metadata.git
cd google-album-metadata

# Install dependencies
gem install bundler
bundle install

# Make the script executable
chmod +x bin/g_album_tool  # On Unix/macOS
# On Windows, use: ruby bin/g_album_tool instead

# Process photos from a Google Takeout folder
bin/g_album_tool process path/to/takeout/folder path/to/destination

# Analyze errors in CSV output files
bin/g_album_tool analyze path/to/destination

# Fix errors in processed files
bin/g_album_tool fix-errors path/to/destination

# Display system information for troubleshooting
bin/g_album_tool info
```

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
- Bundler (for dependency management)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/google-album-metadata.git
   cd google-album-metadata
   ```

2. Install dependencies:
   ```
   gem install bundler  # If bundler is not installed
   bundle install       # Install dependencies from Gemfile
   ```

3. Install ExifTool:
   - Mac: `brew install exiftool`
   - Linux: `apt install libimage-exiftool-perl` or equivalent
   - Windows:
     - Download Ruby installer from [RubyInstaller](https://rubyinstaller.org/) (version 2.6 or later)
     - During installation, check "Add Ruby executables to your PATH"
     - Download ExifTool from [ExifTool website](https://exiftool.org/)
     - **Important**: Rename `exiftool(-k).exe` to `exiftool.exe`
     - Add the directory containing ExifTool to your PATH or place it in a directory that's already in your PATH
     - Open Command Prompt and navigate to the project directory
     - Run `gem install bundler` and then `bundle install`
     - Run `bin\g_album_tool.bat info` to verify installation

4. Ensure the `bin/g_album_tool` script is executable:
   - Unix/macOS: `chmod +x bin/g_album_tool`
   - Windows: Use `ruby bin/g_album_tool` to run the script

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

### Display system information

```
bin/g_album_tool info
```

This command will:
1. Show the tool version
2. Display Ruby version and platform details
3. Show operating system information
4. Verify ExifTool installation and version
5. Provide a summary of system configuration for troubleshooting

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
│   └── g_album_tool.bat  # Windows batch file
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
├── spec/                # RSpec test files
│   ├── features/        # Feature tests
│   ├── lib/             # Unit tests
│   ├── fixtures/        # Test fixtures
│   │   └── setup_fixtures.rb # Test fixture setup
│   └── spec_helper.rb   # Test helper
├── local_data/          # Legacy files
│   ├── bin/             # Legacy executables
│   ├── tests/           # Legacy test files
│   └── g_album_tool.rb  # Legacy main file
├── ARCHITECTURE.md      # Architecture documentation
├── ERROR_SUMMARY.md     # Error handling documentation
├── README.md            # This file
└── spec.md             # Project specifications
```

For a detailed explanation of the codebase architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Troubleshooting

### Common Issues

1. **"ExifTool not found" error**
   - Make sure ExifTool is installed and accessible in your PATH
   - Verify installation by running `exiftool -ver` in your terminal
   - Windows users: Rename the downloaded executable from `exiftool(-k).exe` to `exiftool.exe`
   - Windows users: After renaming, ensure the directory containing ExifTool is in your PATH
   - Run `bin/g_album_tool info` to check if ExifTool is properly detected

2. **Ruby version issues**
   - Check your Ruby version with `ruby -v`
   - If your version is older than 2.6, consider using a version manager like RVM or rbenv
   - The `info` command will show your current Ruby version and platform

3. **Dependency issues**
   - Run `bundle install` to ensure all dependencies are installed
   - If encountering issues with specific gems, try `gem install [gem_name]` directly

4. **Windows path issues**
   - Ensure paths are properly escaped when containing spaces: `"C:\My Photos"`
   - For UNC paths, use the full format: `\\server\share\folder`

5. **Processing slow or stalls**
   - Large folders can take significant time to process
   - Try processing smaller batches of files
   - Use the `-v` flag to see progress details

6. **File encoding issues**
   - Non-ASCII characters in filenames may cause issues on some systems
   - The tool attempts to handle these automatically, but manual renaming might be necessary

### Platform-Specific Notes

#### Windows

- Use `ruby bin/g_album_tool` instead of direct execution
- Use backslashes or properly escaped forward slashes in paths
- Terminal encoding issues can occur with non-English file names; set console to UTF-8 with `chcp 65001`

#### macOS

- If permissions issues occur, verify permissions with `ls -la` and fix with `chmod`
- Catalina and later require explicit permissions for accessing certain directories

#### Linux

- Different distributions may have ExifTool packaged differently; check your package manager
- Some distributions may require additional libraries for image processing

### Getting Help

For issues not covered here, please:
1. Run `bin/g_album_tool info` and include the output when seeking help
2. Check the extensive logs in the created log file
3. Review the error patterns in ERROR_SUMMARY.md
4. Open an issue on the GitHub repository with detailed information

## Development

* Run tests: `bundle exec rspec`
* Check code style: `bundle exec rubocop`
* Generate documentation: `bundle exec yard`

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Windows-Specific Issues

1. **Command Prompt encoding issues**
   - If you see garbled characters in filenames, try running `chcp 65001` before running the tool
   - For PowerShell, you may need to set `$OutputEncoding = [System.Text.Encoding]::UTF8`
   - The batch file `g_album_tool.bat` already sets UTF-8 encoding, but manual adjustment may be needed

2. **Path too long errors**
   - Windows has path length limitations that could cause issues with deeply nested directories
   - Try using a shorter destination path if you encounter such errors
