module GAlbumTools
  class OutputFile
    def self.read_output_file(dir)
      file_path = build_file_path(dir)
      unless File.exist?(file_path)
        puts "No output file found for #{dir}"
        return
      end

      CSV.foreach(file_path, headers: true) do |row|
        yield row
      end
    end

    def self.build_file_path(dir)
      File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
    end
  end
end
