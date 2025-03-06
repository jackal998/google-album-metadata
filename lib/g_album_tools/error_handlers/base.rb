require "fileutils"

module GAlbumTools
  module ErrorHandlers
    class Base
      attr_reader :logger, :exiftool, :error_message, :file_details, :metadata_processor

      def initialize(logger, exiftool, error_message, file_details, metadata_processor)
        @logger = logger
        @exiftool = exiftool
        @error_message = error_message
        @file_details = file_details
        @metadata_processor = metadata_processor
      end

      def handle
        raise NotImplementedError, "#{self.class} must implement handle method"
      end

      protected

      def copy_file_to_target_directory(file_path)
        target_path = File.join(file_details[:target_directory], File.basename(file_path))
        FileUtils.cp(file_path, target_path)
        target_path
      end

      def update_metadata(file_path: file_details[:file], data: file_details[:json_data], destination_directory: file_details[:target_directory])
        metadata_processor.update_metadata(file_path:, data:, destination_directory:)
      end
    end
  end
end
