module GAlbumTools
  module Constants
    IMAGE_EXTENSIONS = %w[jpg jpeg heic dng png gif bmp tiff webp].freeze
    VIDEO_EXTENSIONS = %w[mp4 mov avi mkv].freeze
    SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
    LIVE_PHOTO_EXTENSIONS = %w[mov mp4].freeze

    OFFSET_TIMES_KEYS = %w[OffsetTime OffsetTimeOriginal OffsetTimeDigitized].freeze
    OFFSET_TIMES_PATH = "./local_data/offset_times.csv".freeze

    ALLOWED_SUFFIXES = ["-已編輯", "(1)", " Copy"].freeze
  end
end
