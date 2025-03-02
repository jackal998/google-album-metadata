require "spec_helper"

RSpec.describe "Metadata Processing Workflow", type: :feature do
  let(:root_dir) { File.expand_path("../..", __FILE__) }
  let(:test_source_dir) { File.join(Dir.pwd, "spec/fixtures/source") }
  let(:test_dest_dir) { File.join(Dir.pwd, "spec/fixtures/destination") }
  let(:csv_dir) { File.join(Dir.pwd, "spec/fixtures/csv") }

  before(:all) do
    # Make sure test fixtures exist
    require_relative "../fixtures/setup_fixtures"
    TestFixtures.setup_all
  end

  after(:all) do
    # Clean up output CSV files (but keep the test fixtures)
    Dir.glob(File.join(Dir.pwd, "spec/fixtures/source", "*_output.csv")).each do |file|
      File.delete(file) if File.exist?(file)
    end
  end

  describe "Process command" do
    it "can instantiate the metadata processor" do
      processor = GAlbumTools::MetadataProcessor.new(
        source_directory: test_source_dir,
        destination_directory: test_dest_dir,
        verbose: true,
        nested: false
      )

      expect(processor).to be_a(GAlbumTools::MetadataProcessor)
      expect(processor.source_directory).to eq(test_source_dir)
      expect(processor.destination_directory).to eq(test_dest_dir)
    end

    it "finds files to process" do
      processor = GAlbumTools::MetadataProcessor.new(
        source_directory: test_source_dir,
        destination_directory: test_dest_dir,
        verbose: true,
        nested: false
      )

      processor.check_files(test_source_dir)
      expect(processor.processed_files[test_source_dir]).not_to be_nil
      expect(processor.processed_files[test_source_dir]).not_to be_empty
    end
  end

  describe "Error handling" do
    let(:handler) { GAlbumTools::ErrorHandler.new(verbose: true) }

    before(:each) do
      # Ensure CSV test files exist
      TestFixtures.setup_csv_files

      # Write the test CSV directly to make sure it exists
      csv_content = <<~CSV
        Media File,Destination File,Processed,Errors
        #{File.join(test_source_dir, "photo1.jpg")},#{File.join(test_dest_dir, "photo1.jpg")},true,
        #{File.join(test_source_dir, "wrong_extension.heic")},#{File.join(test_dest_dir, "wrong_extension.heic")},false,Not a valid HEIC (looks more like a JPEG)
        #{File.join(test_source_dir, "truncated.mp4")},#{File.join(test_dest_dir, "truncated.mp4")},false,Invalid or truncated file
        #{File.join(test_source_dir, "maker_notes.jpg")},#{File.join(test_dest_dir, "maker_notes.jpg")},false,Error: [minor] Maker notes could not be parsed
        #{File.join(test_source_dir, "missing_json.jpg")},#{File.join(test_dest_dir, "missing_json.jpg")},false,No JSON file found
        #{File.join(test_source_dir, "live_photo_missing.jpg")},#{File.join(test_dest_dir, "live_photo_missing.jpg")},false,Live photo missing video part
      CSV

      # Make sure the directory exists
      FileUtils.mkdir_p(csv_dir) unless Dir.exist?(csv_dir)
      File.write(File.join(csv_dir, "test_output.csv"), csv_content)
    end

    after(:each) do
      # Clean up test CSV file
      test_csv = File.join(csv_dir, "test_output.csv")
      File.delete(test_csv) if File.exist?(test_csv)
    end

    it "can load errors from CSV files" do
      csv_files = Dir.glob(File.join(csv_dir, "*_output.csv"))
      expect(csv_files).not_to be_empty, "No CSV files found in #{csv_dir}"

      errors = handler.load_errors_from_csv(csv_files)
      expect(errors).not_to be_empty, "No errors loaded from CSV"
    end

    it "correctly categorizes errors" do
      error_types = [:no_json, :unknown_pattern, :live_photo_missing_part, :invalid_or_truncated, :maker_notes]

      error_types.each do |type|
        # Create a dummy error message for each type
        case type
        when :no_json
          msg = "No JSON file found"
        when :unknown_pattern
          msg = "Unknown filename pattern"
        when :live_photo_missing_part
          msg = "Live photo missing video part"
        when :invalid_or_truncated
          msg = "Invalid or truncated file"
        when :maker_notes
          msg = "Error: [minor] Maker notes could not be parsed"
        end

        expect(handler.categorize_error(msg)).to eq(type)
      end
    end
  end

  describe "CLI interface" do
    it "initializes correctly" do
      cli = GAlbumTools::CLI.new
      expect(cli).to be_a(GAlbumTools::CLI)
      expect(cli.options).to be_a(Hash)
    end

    it "parses the process command correctly" do
      cli = GAlbumTools::CLI.new
      args = ["process", test_source_dir, test_dest_dir]

      expect {
        cli.parse(args)
      }.not_to raise_error

      expect(cli.instance_variable_get(:@command)).to eq("process")
      expect(cli.instance_variable_get(:@command_args)).to eq([test_source_dir, test_dest_dir])
    end
  end
end
