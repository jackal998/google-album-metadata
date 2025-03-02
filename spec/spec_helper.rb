require_relative '../lib/g_album_tools'
require 'fileutils'

# This file was generated by the `rspec --init` command
RSpec.configure do |config|
  # Enable flags like --only-failures and --next-failure
  config.example_status_persistence_file_path = ".rspec_status"

  # Disable RSpec exposing methods globally on `Module` and `main`
  config.disable_monkey_patching!

  # Run specs in random order to surface order dependencies
  config.order = :random

  # Allow the use of the focus tag to run only focused specs
  config.filter_run_when_matching :focus

  # Allow the use of the aggregate_failures metadata to aggregate failures
  config.define_derived_metadata do |meta|
    meta[:aggregate_failures] = true unless meta.key?(:aggregate_failures)
  end

  # Make expectations readable in output
  config.expect_with :rspec do |expectations|
    expectations.include_chain_clauses_in_custom_matcher_descriptions = true
    expectations.syntax = :expect
  end

  # Configure mocks to be stricter
  config.mock_with :rspec do |mocks|
    mocks.verify_partial_doubles = true
  end

  # Set up fixtures directory for testing
  config.before(:suite) do
    # Ensure the fixtures directory exists
    spec_fixtures_dir = File.join(File.dirname(__FILE__), 'fixtures')
    FileUtils.mkdir_p(spec_fixtures_dir) unless Dir.exist?(spec_fixtures_dir)
  end
end

# Helper method to setup test fixtures
def setup_test_fixtures
  require_relative '../tests/fixtures/setup_fixtures'
  TestFixtures.setup_all
rescue LoadError => e
  puts "Warning: Could not load test fixtures: #{e.message}"
end
