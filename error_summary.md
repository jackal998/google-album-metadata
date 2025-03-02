# Google Album Metadata Error Summary

## Overview

After analyzing 31 CSV files containing processing results for 13,778 files, we found 513 files (3.72%) with errors. The following summarizes the error types identified and the handling strategies implemented.

## Error Categories

### 1. Missing Metadata (59.84% of errors)
- **Pattern**: "No JSON file found"
- **Example Files**: 
  - IMG_1215.MP4
  - IMG_2063(1)-040.MOV
  - IMG_2063-064.MOV
- **Handling Strategy**: 
  - Copy files to destination
  - Extract basic metadata from file attributes (creation date, modification date)
  - Mark as processed with limited metadata

### 2. Maker Notes Errors (17.93% of errors)
- **Pattern**: "Error: [minor] Maker notes could not be parsed"
- **Example Files**:
  - IMG_20191027_190330.dng
  - IMG_20191031_195721.dng
  - IMG_20191102_210644.dng
- **Handling Strategy**:
  - Use ExifTool with "-m" flag to ignore minor errors
  - Remove maker notes metadata
  - Process the rest of the metadata
  - Mark as successfully processed

### 3. Incorrect File Extensions (21.64% of errors)
- **Patterns**:
  - "Not a valid HEIC (looks more like a JPEG)" - 7.80%
  - "Not a valid DNG (looks more like a JPEG)" - 7.21%
  - "Not a valid PNG (looks more like a JPEG)" - 6.63%
- **Example Files**:
  - IMG_3820.HEIC
  - IMG_0989.DNG
  - IMG_2401.PNG
- **Handling Strategy**:
  - Use ExifTool to rename files with the correct extension
  - Update the output CSV to mark as processed

### 4. Truncated Media (0.58% of errors)
- **Pattern**: "Truncated mdat atom"
- **Example Files**:
  - VID_20200119_201859.mp4~2.mp4
  - VID_20200119_202302.mp4~2.mp4
  - VID_20200119_202731.mp4~2.mp4
- **Handling Strategy**:
  - Log as corrupted file
  - No fix attempted as these are usually corrupted beyond repair
  - Mark as handled for tracking purposes

## Implementation

The error handling system has been implemented with:

1. An `ErrorTypes` module to categorize errors based on patterns
2. A base `BaseHandler` class with common functionality
3. Specialized handlers for each error type:
   - `ExtensionHandler` for incorrect file extensions
   - `MetadataHandler` for missing metadata
   - `MakerNotesHandler` for maker notes errors
   - `TruncatedMediaHandler` for truncated media
   - `DefaultHandler` for other errors

## Usage

To fix errors in processed files:

```bash
bin/g_album_tool fix-errors DESTINATION_DIR
```

This command will:
1. Scan all output CSV files in the specified directory
2. Identify failed entries
3. Categorize each error
4. Apply the appropriate handler
5. Update the CSV files with the results 
