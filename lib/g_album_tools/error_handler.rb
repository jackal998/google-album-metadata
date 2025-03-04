require_relative "error_manager"

module GAlbumTools
  # @deprecated Use ErrorManager instead. This class is kept for backward compatibility.
  class ErrorHandler < ErrorManager
    # Keep the ERROR_TYPES constant for backward compatibility
    ERROR_TYPES = ErrorHandlers::Factory::ERROR_TYPES.freeze
    
    def identify_error_type(error_message)
      ErrorHandlers::Factory.identify_error_type(error_message)
    end
  end
end 
