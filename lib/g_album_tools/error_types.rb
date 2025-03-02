module GAlbumTools
  module ErrorTypes
    # Error type constants
    INCORRECT_EXTENSION = "incorrect_extension"
    MISSING_METADATA = "missing_metadata"
    TRUNCATED_MEDIA = "truncated_media"
    MAKER_NOTES_ERROR = "maker_notes_error"
    OTHER_ERROR = "other_error"

    # Error patterns for matching
    ERROR_PATTERNS = {
      # File extension errors
      INCORRECT_EXTENSION => [
        /Not a valid (\w+) \(looks more like a (\w+)\)/i
      ],

      # Missing metadata errors
      MISSING_METADATA => [
        /No JSON file found/i,
        /No metadata found/i
      ],

      # Truncated media errors
      TRUNCATED_MEDIA => [
        /Truncated mdat atom/i
      ],

      # Maker notes errors
      MAKER_NOTES_ERROR => [
        /Maker notes could not be parsed/i
      ]
    }

    # Categorize an error message
    def self.categorize(error_message)
      return nil if error_message.nil? || error_message.empty?

      ERROR_PATTERNS.each do |type, patterns|
        patterns.each do |pattern|
          if error_message.match?(pattern)
            if type == INCORRECT_EXTENSION
              match = error_message.match(/Not a valid (\w+) \(looks more like a (\w+)\)/i)
              return {
                type: type,
                data: {
                  current_extension: match[1],
                  expected_extension: match[2]
                }
              }
            else
              return { type: type, data: nil }
            end
          end
        end
      end

      # Default to other error
      return { type: OTHER_ERROR, data: nil }
    end

    # Handlers for each error type
    def self.handler_for(error_type)
      case error_type
      when INCORRECT_EXTENSION
        "GAlbumTools::Handlers::ExtensionHandler"
      when MISSING_METADATA
        "GAlbumTools::Handlers::MetadataHandler"
      when TRUNCATED_MEDIA
        "GAlbumTools::Handlers::TruncatedMediaHandler"
      when MAKER_NOTES_ERROR
        "GAlbumTools::Handlers::MakerNotesHandler"
      else
        "GAlbumTools::Handlers::DefaultHandler"
      end
    end
  end
end
