require 'spec_helper'

RSpec.describe GAlbumTools::FileProcessor do
  let(:root_dir) { File.expand_path('../../..', __FILE__) }
  let(:test_source_dir) { File.join(Dir.pwd, 'spec/fixtures/source') }
  let(:test_dest_dir) { File.join(Dir.pwd, 'spec/fixtures/destination') }
  let(:options) do
    {
      source_directory: test_source_dir,
      destination_directory: test_dest_dir,
      verbose: true
    }
  end
  let(:processor) { described_class.new(options) }

  before(:each) do
    # Ensure test directories exist and fixtures are created
    require_relative '../../../spec/fixtures/setup_fixtures'
    TestFixtures.setup_directories
    TestFixtures.setup_media_files
    TestFixtures.setup_json_files
  end

  after(:each) do
    # Uncomment to clean up test files after tests run
    # FileUtils.rm_rf(Dir.glob(File.join(test_source_dir, "*")))
    # FileUtils.rm_rf(Dir.glob(File.join(test_dest_dir, "*")))
  end

  describe '#initialize' do
    it 'sets up instance variables correctly' do
      expect(processor.source_directory).to eq(test_source_dir)
      expect(processor.destination_directory).to eq(test_dest_dir)
      expect(processor.processed_files).to eq({})
      expect(processor.offset_time).to be_an(Array)
    end
  end

  describe '#is_allowed_file_format?' do
    it 'returns true for allowed image formats' do
      expect(processor.is_allowed_file_format?('test.jpg')).to eq(true)
      expect(processor.is_allowed_file_format?('test.jpeg')).to eq(true)
      expect(processor.is_allowed_file_format?('test.png')).to eq(true)
    end

    it 'returns true for allowed video formats' do
      expect(processor.is_allowed_file_format?('test.mp4')).to eq(true)
      expect(processor.is_allowed_file_format?('test.mov')).to eq(true)
    end

    it 'returns false for non-media formats' do
      expect(processor.is_allowed_file_format?('test.txt')).to eq(false)
      expect(processor.is_allowed_file_format?('test.pdf')).to eq(false)
      expect(processor.is_allowed_file_format?('test.doc')).to eq(false)
    end
  end

  describe '#live_photo?' do
    it 'detects live photos correctly' do
      live_photo_jpg = File.join(test_source_dir, 'live_photo.jpg')
      live_photo_mov = File.join(test_source_dir, 'live_photo.mov')

      # Ensure the files exist before testing
      expect(File.exist?(live_photo_jpg)).to eq(true)
      expect(File.exist?(live_photo_mov)).to eq(true)

      # Test detection from both sides of the pair
      expect(processor.live_photo?(live_photo_jpg)).to eq(true)
      expect(processor.live_photo?(live_photo_mov)).to eq(true)
    end

    it 'does not detect regular photos as live photos' do
      regular_photo = File.join(test_source_dir, 'photo1.jpg')
      expect(processor.live_photo?(regular_photo)).to eq(false)
    end
  end

  describe '#find_json_file' do
    it 'finds matching JSON files' do
      photo_path = File.join(test_source_dir, 'photo1.jpg')
      expected_json = File.join(test_source_dir, 'photo1.json')

      expect(File.exist?(photo_path)).to eq(true)
      expect(File.exist?(expected_json)).to eq(true)

      expect(processor.find_json_file(File.dirname(photo_path), File.basename(photo_path, '.*'))).to eq(expected_json)
    end

    it 'returns nil for files without matching JSON' do
      no_json_photo = File.join(test_source_dir, 'wrong_extension.heic')
      expect(File.exist?(no_json_photo)).to eq(true)

      expect(processor.find_json_file(File.dirname(no_json_photo), File.basename(no_json_photo, '.*'))).to be_nil
    end
  end

  describe '#check_files' do
    it 'finds and processes media files correctly' do
      result = processor.check_files(test_source_dir)

      # Check if any files were found
      expect(result[test_source_dir]).not_to be_nil
      expect(result[test_source_dir].size).to be > 0

      # Check if it correctly identified the JSON for some files
      photo1_result = result[test_source_dir].find { |f| f[:media_file].end_with?('photo1.jpg') }
      expect(photo1_result).not_to be_nil
      expect(photo1_result[:json_file]).not_to be_nil
      expect(photo1_result[:data]).not_to be_nil

      # Check it correctly identified missing JSON for others
      no_json_result = result[test_source_dir].find { |f| f[:media_file].end_with?('wrong_extension.heic') }
      expect(no_json_result).not_to be_nil
      expect(no_json_result[:json_file]).to be_nil
    end
  end
end
