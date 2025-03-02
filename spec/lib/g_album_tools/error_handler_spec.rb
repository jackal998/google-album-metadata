require 'spec_helper'

RSpec.describe GAlbumTools::ErrorHandler do
  let(:test_dir) { File.join(File.dirname(__FILE__), '..', '..', 'fixtures') }
  let(:csv_dir) { File.join(test_dir, 'csv') }
  let(:media_dir) { File.join(test_dir, 'media') }
  let(:dest_dir) { File.join(test_dir, 'destination') }
  let(:handler) { described_class.new(verbose: true) }

  before(:each) do
    # Create test directories if they don't exist
    FileUtils.mkdir_p(csv_dir)
    FileUtils.mkdir_p(media_dir)
    FileUtils.mkdir_p(dest_dir)

    # Create a test CSV file
    create_test_csv

    # Create test media files
    create_test_media_files
  end

  after(:each) do
    # Commented out for now to preserve test files
    # FileUtils.rm_rf(test_dir) if File.directory?(test_dir)
  end

  describe '#categorize_error' do
    it 'categorizes no json errors correctly' do
      expect(handler.categorize_error("No JSON file found")).to eq(:no_json)
      expect(handler.categorize_error("Could not find JSON metadata")).to eq(:no_json)
    end

    it 'categorizes unknown pattern errors correctly' do
      expect(handler.categorize_error("Unknown filename pattern")).to eq(:unknown_pattern)
      expect(handler.categorize_error("Filename does not match expected pattern")).to eq(:unknown_pattern)
    end

    it 'categorizes live photo missing part errors correctly' do
      expect(handler.categorize_error("Live photo missing video part")).to eq(:live_photo_missing_part)
      expect(handler.categorize_error("Could not find corresponding image file")).to eq(:live_photo_missing_part)
    end

    it 'categorizes invalid or truncated file errors correctly' do
      expect(handler.categorize_error("Invalid or truncated file")).to eq(:invalid_or_truncated)
      expect(handler.categorize_error("File is truncated")).to eq(:invalid_or_truncated)
    end

    it 'categorizes unknown errors correctly' do
      expect(handler.categorize_error("Some other random error")).to eq(:unknown)
      expect(handler.categorize_error("")).to eq(:unknown)
      expect(handler.categorize_error(nil)).to eq(:unknown)
    end
  end

  describe '#load_errors_from_csv' do
    it 'loads errors from CSV correctly' do
      errors = handler.load_errors_from_csv([File.join(csv_dir, "test_output.csv")])

      expect(errors.size).to eq(4)

      error_types = errors.map { |e| e[:error_type] }
      expect(error_types).to include(:no_json)
      expect(error_types).to include(:unknown_pattern)
      expect(error_types).to include(:live_photo_missing_part)
      expect(error_types).to include(:invalid_or_truncated)
    end
  end

  describe '#error_stats' do
    it 'generates correct error statistics' do
      errors = handler.load_errors_from_csv([File.join(csv_dir, "test_output.csv")])
      stats = handler.error_stats(errors)

      expect(stats[:total]).to eq(4)
      expect(stats[:no_json]).to eq(1)
      expect(stats[:unknown_pattern]).to eq(1)
      expect(stats[:live_photo_missing_part]).to eq(1)
      expect(stats[:invalid_or_truncated]).to eq(1)
      expect(stats[:unknown]).to eq(0)
    end
  end

  private

  def create_test_csv
    csv_path = File.join(csv_dir, "test_output.csv")

    File.open(csv_path, "w") do |f|
      f.puts "Media File,Destination File,Processed,Errors"

      # Create a row for each error type
      f.puts "#{File.join(media_dir, "test1.jpg")},#{File.join(dest_dir, "test1.jpg")},false,No JSON file found"
      f.puts "#{File.join(media_dir, "test2.jpg")},#{File.join(dest_dir, "test2.jpg")},false,Unknown filename pattern"
      f.puts "#{File.join(media_dir, "test3.jpg")},#{File.join(dest_dir, "test3.jpg")},false,Live photo missing video part"
      f.puts "#{File.join(media_dir, "test4.mp4")},#{File.join(dest_dir, "test4.mp4")},false,Invalid or truncated file"

      # Create a row for a successful file
      f.puts "#{File.join(media_dir, "test5.jpg")},#{File.join(dest_dir, "test5.jpg")},true,"
    end
  end

  def create_test_media_files
    # Create dummy media files
    ["test1.jpg", "test2.jpg", "test3.jpg", "test4.mp4", "test5.jpg"].each do |file|
      File.open(File.join(media_dir, file), "w") do |f|
        f.puts "Dummy file content"
      end
    end
  end
end
