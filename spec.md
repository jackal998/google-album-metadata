# Google Album Metadata Tool Specification

## 1. Overview
The Google Album Metadata Tool (GAlbumTool) is designed to process media files from Google Photos Takeout, extract metadata from associated JSON files, and apply this metadata to the media files using ExifTool.

## 2. Core Functionality

### 2.1 Metadata Processing
#### Process Flow
1. Read source directory (with nested subdirectories support)
2. For each directory:
   1. Check for media files with supported extensions
      - Supported image formats: jpg, jpeg, heic, dng, png, gif, bmp, tiff, webp
      - Supported video formats: mp4, mov, avi, mkv
      - If not a supported format, skip and make a note in the output file
   2. Check if corresponding metadata JSON file exists
      - Match filename patterns, including special handling for live photos
      - If no metadata found, mark for later error handling
   3. Read and parse the JSON metadata file
   4. Check if offset time information is available (from media file itself)
      - If not available, default to UTC+08:00
   5. Update metadata:
      - Copy file to destination directory (can be done through exiftool command)
      - Update EXIF metadata (consider update all of them within single command)
        - geolocation metadata if available
        - timestamp and offset time information
      - Support error handling for each step
   6. Create CSV output file with processing results

### 2.2 Error Handling
#### Error Types and Handling Strategies

1. **Missing Metadata** (59.84% of errors)
   - **Pattern**: "No JSON file found" or "No metadata found"
   - **Handling Strategy**: 
     - Check if file is a live photo
       - If yes, update metadata with metadata from the related photo's metadata, and mark as processed
       - If no, update metadata with limited metadata (from file attributes like creation date), and mark as not processed
     - Copy files to destination

2. **Maker Notes Errors** (17.93% of errors)
   - **Pattern**: "Error: [minor] Maker notes could not be parsed"
   - **Handling Strategy**:
     - Use ExifTool with "-m" flag to ignore minor errors
     - Remove maker notes metadata
     - Process the rest of the metadata
     - Mark as successfully processed

3. **Incorrect File Extensions** (21.64% of errors)
   - **Patterns**:
     - "Not a valid HEIC (looks more like a JPEG)"
     - "Not a valid DNG (looks more like a JPEG)" 
     - "Not a valid PNG (looks more like a JPEG)"
   - **Handling Strategy**:
     - Use ExifTool to rename files with the correct extension
     - Continue processing with the corrected file
     - Mark as successfully processed only if no additional errors occur

4. **Truncated Media** (0.58% of errors)
   - **Pattern**: "Truncated mdat atom"
   - **Handling Strategy**:
     - Log as corrupted file
     - No fix attempted as these are usually corrupted beyond repair
     - Mark as not processed, requiring manual intervention

5. **Other Errors**
   - **Handling Strategy**:
     - Generic fallback handling
     - Copy file to destination if possible
     - Mark as not processed for manual review

## 3. Application Structure

### 3.1 Core Components
1. **Base Classes**
   - `Base`: Common logging, command execution, and string handling
   - `FileProcessor`: File discovery and organization
   - `MetadataProcessor`: Metadata extraction and application

2. **Error Handling**
   - `ErrorTypes`: Error categorization and pattern matching
   - `ErrorHandler`: Orchestrates error handling flow

3. **Error Handlers**
   - `BaseHandler`: Common handler functionality
   - Specialized handlers for each error type:
     - `MetadataHandler`: For missing metadata, with special handling for live photos
     - `MakerNotesHandler`: For maker notes errors
     - `ExtensionHandler`: For incorrect file extensions
     - `TruncatedMediaHandler`: For corrupted media files
     - `DefaultHandler`: For other uncategorized errors

### 3.2 Command Line Interface
1. **Commands**
   - `process SOURCE_DIR DEST_DIR`: Process metadata from source to destination
   - `fix-errors DEST_DIR`: Fix errors in already processed files

2. **Options**
   - `-v, --verbose`: Enable verbose output
   - `--no-csv`: Disable CSV output file creation
   - `--nested`: Process nested directories for fix-errors command

## 4. Implementation Notes

1. **Dependencies**
   - Ruby 2.6+
   - ExifTool (external command-line tool)

2. **File Organization**
   - Input: Google Photos Takeout structure with media files and .metadata/ JSON files
   - Output: Organized files with updated metadata and CSV report files

3. **Processing Flow**
   - Initial processing (process command): 
     - Process all files, noting errors in CSV files
   - Error fixing (fix-errors command):
     - Apply specialized handlers based on error types
     - Update CSV files with results of fix attempts

4. **Performance Considerations**
   - Process directories in sequence to minimize memory usage
   - Log failures for later batch processing
