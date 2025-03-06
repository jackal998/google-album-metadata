module GAlbumTools
  class FileDetector
    # Extensions constants
    IMAGE_EXTENSIONS = %w[jpg jpeg heic dng png gif bmp tiff webp].freeze
    VIDEO_EXTENSIONS = %w[mp4 mov avi mkv].freeze
    SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
    LIVE_PHOTO_EXTENSIONS = %w[mov mp4].freeze

    ALLOWED_SUFFIXES = ["-已編輯", "(1)", " Copy"].freeze

    attr_reader :logger, :exiftool

    def initialize(logger, exiftool)
      @logger = logger
      @exiftool = exiftool
    end

    def map_json_files(dir)
      media_files = Dir.glob(File.join(dir, "*.{#{SUPPORTED_EXTENSIONS.join(",")}}")).select { |f| File.file?(f) }
      json_files = Dir.glob(File.join(dir, "*.json")).select { |f| File.file?(f) }

      media_files_from_json = json_files.map { _1[0...-5] }

      missing_json = media_files - media_files_from_json
      missing_media = media_files_from_json - media_files

      mapped_files = {}

      media_files.each do |media_file|
        json_file =
          if missing_json.include?(media_file)
            logger.info("JSON file is missing for media file: #{media_file}")
            fetch_json_file(media_file, json_files)
          else
            "#{media_file}.json"
          end

        mapped_files[media_file] = json_file
      end

      missing_media.each do |file_path|
        logger.info("Media file is missing for JSON file: #{file_path}")
      end

      mapped_files
    end

    def fetch_json_file(file_path, json_files)
      match_file_path = magic_file_path(file_path, live_photo: live_photo?(file_path))

      json_files.each do |json_file|
        next unless magic_file_path(json_file).include?(match_file_path)

        logger.info("Using JSON file via magic: #{json_file}")
        return json_file
      end

      nil
    end

    def live_photo?(file_path)
      return false unless LIVE_PHOTO_EXTENSIONS.include?(File.extname(file_path).downcase.delete("."))

      duration = exiftool.get_duration(file_path)
      return false if duration.nil?

      duration < 3
    end

    private

    def magic_file_path(file_path, live_photo: false)
      magic_path = File.join(
        File.dirname(file_path),
        File.basename(file_path)
          .gsub(
            /#{ALLOWED_SUFFIXES.map { Regexp.quote(_1) }.join("|")}/,
            ""
          )
      )

      return magic_path unless live_photo

      # remove live photo extension
      magic_path[0...-4]
    end
  end
end
