require_relative "error_handlers/missing_metadata"
require_relative "error_handlers/maker_notes"
require_relative "error_handlers/incorrect_extension"
require_relative "error_handlers/truncated_media"
require_relative "error_handlers/unknown"

module GAlbumTools
  class ErrorManager
    ERROR_TYPES = {
      missing_metadata: /No JSON file found|No metadata found/,
      maker_notes: /Error: \[minor\] Maker notes could not be parsed/,
      incorrect_extension: /Not a valid (\w+) \(looks more like a (\w+)\)/,
      truncated_media: /Truncated mdat atom/
    }.freeze

    attr_reader :logger, :exiftool, :metadata_processor

    def initialize(logger, exiftool, metadata_processor)
      @logger = logger
      @exiftool = exiftool
      @metadata_processor = metadata_processor
    end

    def handle_error(error_message, file_details)
      handler = handler(error_type(error_message)).new(logger, exiftool, error_message, file_details, metadata_processor)

      result = handler.handle

      if result[:processed]
        logger.info("Processed #{file_details[:file]}")
      else
        logger.error("Failed to process #{file_details[:file]}: #{result[:message]}")
      end
    end

    private

    def handler(error_type)
      case error_type
      when :missing_metadata
        ErrorHandlers::MissingMetadata
      when :maker_notes
        ErrorHandlers::MakerNotes
      when :incorrect_extension
        ErrorHandlers::IncorrectExtension
      when :truncated_media
        ErrorHandlers::TruncatedMedia
      else
        ErrorHandlers::Unknown
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
