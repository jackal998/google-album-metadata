require "fileutils"

module GAlbumTools
  module ErrorHandlers
    class Base
      attr_reader :logger, :exiftool

      def initialize(logger, exiftool)
        @logger = logger
        @exiftool = exiftool
      end

      def handle(file_path, error_message, destination_directory)
        raise NotImplementedError, "#{self.class} must implement handle method"
      end

      protected

      def copy_file_to_destination(file_path, destination_directory)
        destination_path = File.join(destination_directory, File.basename(file_path))
        FileUtils.cp(file_path, destination_path)
        destination_path
      end
    end
  end
end
