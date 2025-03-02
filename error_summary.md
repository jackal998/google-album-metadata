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
  - Check if file is a live photo
    - if yes, update metadata with metadata from the related photo's metadata, and mark as processed
    - if no, update metadata with limited metadata, and mark as not processed
  - Copy files to destination

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
  - Use ExifTool to rename files with the correct extension and continue processing
  - Mark as successfully processed if no error occurs

### 4. Truncated Media (0.58% of errors)
- **Pattern**: "Truncated mdat atom"
- **Example Files**:
  - VID_20200119_201859.mp4~2.mp4
  - VID_20200119_202302.mp4~2.mp4
  - VID_20200119_202731.mp4~2.mp4
- **Handling Strategy**:
  - Log as corrupted file
  - No fix attempted as these are usually corrupted beyond repair
  - Mark as not processed, need to be fixed manually

## How to Fix These Errors

### No JSON File
1. Locate the corresponding JSON file for the media.
2. Ensure it's named correctly to match the media file name pattern.
3. Place the JSON file in the same directory as the media file.

### Unknown Filename Pattern
1. Rename the file to match one of the expected patterns (see below).
2. Alternatively, you may need to add a new pattern to the allowed patterns configuration.

### Live Photo Missing Part
1. Locate the missing part (image or video) of the live photo.
2. Ensure both parts are named according to the same pattern.
3. Place both files in the same directory.

### Invalid or Truncated File
1. Try downloading the file again from Google Photos.
2. Check if the file is corrupted by opening it in a media viewer.

### Maker Notes Errors
1. Use ExifTool with the `-m` flag to ignore minor errors.
2. This is automatically attempted during the error fixing process.

### Incorrect File Extensions
1. Verify the actual file type using the `file` command on Linux/Mac or properties on Windows.
2. Rename the file with the correct extension.
3. The `fix-errors` command can correct this automatically.

### Truncated Media
1. Download a fresh copy of the file from Google Photos.
2. Verify the file integrity with media viewers.

## Windows-Specific Troubleshooting

When running this tool on Windows systems, you may encounter additional issues:

### Command Line Encoding
- If filenames with special characters appear corrupted, run `chcp 65001` before running the tool
- Alternatively, use PowerShell with proper UTF-8 encoding settings

### Path Issues
- Windows has path length limitations (260 characters by default)
- If processing fails for deeply nested directories, use shorter paths or enable long path support
  (requires Windows 10 version 1607 or later with appropriate registry settings)

### ExifTool Issues
- Ensure ExifTool is properly renamed from `exiftool(-k).exe` to `exiftool.exe`
- Verify ExifTool is in your PATH by running `where exiftool.exe` in Command Prompt
- If using PowerShell, try `Get-Command exiftool.exe` to verify installation

### Permissions Errors
- Run Command Prompt or PowerShell as Administrator if encountering access denied errors
- Check Windows Defender or antivirus software if file operations are being blocked
