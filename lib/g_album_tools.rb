# frozen_string_literal: true

require_relative "g_album_tools/version"
require_relative "g_album_tools/processor"
require_relative "g_album_tools/error_files_worker"
require_relative "g_album_tools/output_file"
require_relative "g_album_tools/logger"
require_relative "g_album_tools/exif_tool_wrapper"
require_relative "g_album_tools/file_detector"
require_relative "g_album_tools/metadata_processor"
require_relative "g_album_tools/error_manager"

module GAlbumTools
  class Error < StandardError; end
  # Your code goes here...
end
