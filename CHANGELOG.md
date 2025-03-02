# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2024-06-14

### Added
- Enhanced Windows compatibility
- Detailed Windows-specific troubleshooting sections in documentation
- Improved Windows batch file with better error handling

### Changed
- Updated command execution to better handle Windows path separators
- Improved UTF-8 encoding handling for Windows systems
- Enhanced error messages for common Windows issues

### Fixed
- Path handling for Windows systems
- ExifTool detection and execution on Windows platforms
- Character encoding issues when processing files with non-ASCII characters

## [1.0.0] - 2024-06-13

### Added
- Initial release
- Support for processing metadata from Google Photos JSON files
- Apply metadata to media files using ExifTool
- Live photo handling (paired image/video files)
- Support for various image and video formats
- CSV output with processing results
- Error categorization and analysis
- Error fixing capabilities for different error types
- System information display for troubleshooting 
