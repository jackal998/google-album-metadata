require_relative "missing_metadata"
require_relative "maker_notes"
require_relative "incorrect_extension"
require_relative "truncated_media"
require_relative "unknown"

module GAlbumTools
  class ErrorManager
    ERROR_TYPES = {
      missing_metadata: /No JSON file found|No metadata found/,
      maker_notes: /Error: \[minor\] Maker notes could not be parsed/,
      incorrect_extension: /Not a valid (\w+) \(looks more like a (\w+)\)/,
      truncated_media: /Truncated mdat atom/
    }.freeze

    attr_reader :logger, :exiftool

    def initialize(logger, exiftool)
      @logger = logger
      @exiftool = exiftool
    end

    def handle_error(file_path, error_message, destination_directory)
      result = handler(error_type(error_message))
        .new(logger, exiftool)
        .handle(file_path, error_message, destination_directory)

      if result[:processed]
        logger.info("Processed #{file_path}")
      else
        logger.error("Failed to process #{file_path}: #{result[:message]}")
      end
    end

    private

    def handler(error_type, logger, exiftool)
      case error_type
      when :missing_metadata
        MissingMetadata
      when :maker_notes
        MakerNotes
      when :incorrect_extension
        IncorrectExtension
      when :truncated_media
        TruncatedMedia
      else
        Unknown
      end
    end

    def error_type(error_message)
      return :missing_metadata unless error_message
      
      ERROR_TYPES.each do |type, pattern|
        return type if error_message.match?(pattern)
      end
      :unknown
    end
  end
end 
