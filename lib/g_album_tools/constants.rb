module GAlbumTools
  # Constants module for the GAlbumTools application
  module Constants
    # Media file extensions
    IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp']
    VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.wmv', '.mpg', '.mpeg', '.m4v', '.3gp', '.webm']

    # Metadata handling
    METADATA_KEYS = ['title', 'description', 'creationTime', 'photoTakenTime', 'geoData']
    JSON_ENCODING = 'UTF-8'

    # Offset time handling
    OFFSET_TIMES_KEYS = ['OffsetTime', 'OffsetTimeOriginal', 'OffsetTimeDigitized']
    DEFAULT_OFFSET_TIME = '+00:00'

    # Allowed filename patterns
    ALLOWED_FILENAME_SUFFIXES = ['(1)', '(2)', '(3)', '(4)', '(5)',
                                '(6)', '(7)', '(8)', '(9)', '(10)',
                                ' (1)', ' (2)', ' (3)', ' (4)', ' (5)',
                                ' (6)', ' (7)', ' (8)', ' (9)', ' (10)']

    # Output file settings
    OUTPUT_CSV_FILENAME = '%s_output.csv'
    ERROR_CSV_FILENAME = '%s_error.csv'
    LOG_FILE = 'g_album_tool.log'

    # ExifTool common options
    EXIFTOOL_COMMON_OPTIONS = [
      '-overwrite_original',
      '-preserve',
      '-charset', 'filename=UTF8',
      '-charset', 'exif=UTF8',
      '-charset', 'iptc=UTF8'
    ]
  end
end
