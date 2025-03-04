require_relative "missing_metadata"
require_relative "maker_notes"
require_relative "incorrect_extension"
require_relative "truncated_media"
require_relative "unknown"

module GAlbumTools
  module ErrorHandlers
    class Factory
      ERROR_TYPES = {
        missing_metadata: /No JSON file found|No metadata found/,
        maker_notes: /Error: \[minor\] Maker notes could not be parsed/,
        incorrect_extension: /Not a valid (\w+) \(looks more like a (\w+)\)/,
        truncated_media: /Truncated mdat atom/
      }.freeze

      def self.create_handler(error_type, logger, exiftool)
        case error_type
        when :missing_metadata
          MissingMetadata.new(logger, exiftool)
        when :maker_notes
          MakerNotes.new(logger, exiftool)
        when :incorrect_extension
          IncorrectExtension.new(logger, exiftool)
        when :truncated_media
          TruncatedMedia.new(logger, exiftool)
        else
          Unknown.new(logger, exiftool)
        end
      end

      def self.identify_error_type(error_message)
        return :missing_metadata unless error_message
        
        ERROR_TYPES.each do |type, pattern|
          return type if error_message.match?(pattern)
        end
        :unknown
      end
    end
  end
end 
