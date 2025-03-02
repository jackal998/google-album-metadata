require "pry"

module GAlbumTools
  class ExtensionUpdater
    def initialize(row, error_info)
      @row = row
      @error_info = error_info
    end

    def call
      binding.pry

      cmd = [
        "exiftool",
        "-ext",
        error_info[:current_extension].downcase,
        "-FileName=#{File.basename(row["Media File"], ".*")}.#{error_info[:expected_extension].downcase}",
        row["Media File"]
      ]

      _, _, _ = Open3.capture3(*cmd)
    end

    private

    attr_reader :row, :error_info
  end
end
