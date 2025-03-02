module GAlbumTools
  module ErrorTypes
    # Error type constants
    NO_JSON_ERROR = :no_json
    UNKNOWN_PATTERN_ERROR = :unknown_pattern
    LIVE_PHOTO_MISSING_PART_ERROR = :live_photo_missing_part
    INVALID_OR_TRUNCATED_ERROR = :invalid_or_truncated
    UNKNOWN_ERROR = :unknown

    # Error patterns for matching
    NO_JSON_PATTERNS = [
      /No JSON file found/i,
      /Could not find JSON metadata/i,
      /Missing JSON metadata/i
    ]

    UNKNOWN_PATTERN_PATTERNS = [
      /Unknown filename pattern/i,
      /Filename does not match expected pattern/i,
      /Unsupported filename format/i
    ]

    LIVE_PHOTO_MISSING_PART_PATTERNS = [
      /Live photo missing (video|image) part/i,
      /Could not find corresponding (video|image) file/i,
      /Missing paired file for live photo/i
    ]

    INVALID_OR_TRUNCATED_PATTERNS = [
      /Invalid or truncated file/i,
      /File appears to be damaged/i,
      /Error reading file/i,
      /Unexpected end of file/i,
      /File is truncated/i
    ]

    # Categorize error message into a specific error type
    # @param error_message [String] The error message to categorize
    # @return [Symbol] The error type
    def categorize_error(error_message)
      return UNKNOWN_ERROR if error_message.nil? || error_message.empty?

      if NO_JSON_PATTERNS.any? { |pattern| error_message.match?(pattern) }
        return NO_JSON_ERROR
      elsif UNKNOWN_PATTERN_PATTERNS.any? { |pattern| error_message.match?(pattern) }
        return UNKNOWN_PATTERN_ERROR
      elsif LIVE_PHOTO_MISSING_PART_PATTERNS.any? { |pattern| error_message.match?(pattern) }
        return LIVE_PHOTO_MISSING_PART_ERROR
      elsif INVALID_OR_TRUNCATED_PATTERNS.any? { |pattern| error_message.match?(pattern) }
        return INVALID_OR_TRUNCATED_ERROR
      else
        return UNKNOWN_ERROR
      end
    end

    # Get statistics for errors
    # @param errors [Array<Hash>] List of errors
    # @return [Hash] Statistics for errors
    def error_stats(errors)
      stats = {
        no_json: 0,
        unknown_pattern: 0,
        live_photo_missing_part: 0,
        invalid_or_truncated: 0,
        unknown: 0,
        total: errors.size
      }

      errors.each do |error|
        case error[:error_type]
        when NO_JSON_ERROR
          stats[:no_json] += 1
        when UNKNOWN_PATTERN_ERROR
          stats[:unknown_pattern] += 1
        when LIVE_PHOTO_MISSING_PART_ERROR
          stats[:live_photo_missing_part] += 1
        when INVALID_OR_TRUNCATED_ERROR
          stats[:invalid_or_truncated] += 1
        else
          stats[:unknown] += 1
        end
      end

      stats
    end
  end
end
