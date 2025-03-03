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

### macOS

```bash
# Install dependencies
brew install exiftool
gem install bundler

# Clone the repository
git clone https://github.com/yourusername/google-album-metadata.git
cd google-album-metadata

# Install Ruby dependencies
bundle install
```

### Windows

1. **Install Ruby**:
   - Download and install Ruby from [RubyInstaller](https://rubyinstaller.org/)
   - Make sure to check the option to add Ruby to your PATH during installation

2. **Install ExifTool**:
   - Download ExifTool from [https://exiftool.org/](https://exiftool.org/)
   - Extract the archive and rename `exiftool(-k).exe` to `exiftool.exe`
   - Move `exiftool.exe` to a directory in your PATH (or add its location to your PATH)

3. **Setup the Application**:
   ```cmd
   # Install bundler
   gem install bundler

   # Clone or download the repository
   # Navigate to the project directory
   cd google-album-metadata

   # Install dependencies
   bundle install
   ```

4. **Special Notes for Windows Users**:
   - For best results with Unicode file paths (non-English characters), run from PowerShell
   - If you encounter issues with file paths containing special characters, try moving files to paths with only ASCII characters

## Usage

### Process metadata from Google Photos Takeout

```bash
# macOS/Linux
bin/g_album_tool process SOURCE_DIR DESTINATION_DIR

# Windows (PowerShell recommended)
bin\g_album_tool.bat process SOURCE_DIR DESTINATION_DIR
```

This command will:
1. Scan SOURCE_DIR for media files and their corresponding JSON metadata
2. Process each file, fixing common issues
3. Copy processed files to DESTINATION_DIR with correct metadata

### Analyze errors in CSV output files

```bash
# macOS/Linux
bin/g_album_tool analyze CSV_DIR

# Windows
bin\g_album_tool.bat analyze CSV_DIR
```

This command will:
1. Find all CSV output files in CSV_DIR
2. Analyze error patterns and provide statistics

### Fix errors in processed files

```bash
# macOS/Linux
bin/g_album_tool fix-errors DESTINATION_DIR

# Windows
bin\g_album_tool.bat fix-errors DESTINATION_DIR
```

This command will:
1. Find all CSV output files in DESTINATION_DIR
2. Identify files with errors
3. Apply appropriate fixes based on error type
4. Update the files in place and mark them as processed in the CSV

### Display system information

```bash
# macOS/Linux
bin/g_album_tool info

# Windows
bin\g_album_tool.bat info
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

1. **Unicode Path Issues**: 
   - If you encounter problems with folders containing non-ASCII characters:
   - Try using PowerShell instead of CMD
   - Move files to a path with only ASCII characters
   - Use shorter path names (avoid deeply nested directories)

2. **ExifTool Not Found**:
   - Ensure ExifTool is properly installed and in your PATH
   - Check that the file is named `exiftool.exe` (not `exiftool(-k).exe`)

3. **Permission Issues**:
   - Run as administrator if you encounter permission errors
   - Check Windows Defender or antivirus software is not blocking file operations

For more detailed troubleshooting, run:

```
bin\g_album_tool.bat info
```

This will show system information and dependency status to help diagnose issues.
