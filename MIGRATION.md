# Migration from Minitest to RSpec

This document details the migration process from Minitest to RSpec for the Google Album Metadata Tool project.

## Migration Overview

The project has been successfully migrated from using Minitest to RSpec as the testing framework. This migration involved:

1. Creating new RSpec test files in the `spec` directory
2. Fixing path references in the RSpec test files to correctly locate test fixtures
3. Moving legacy Minitest files to the `local_data` directory for reference
4. Ensuring all RSpec tests pass

## Files Moved to `local_data`

The following files have been moved to the `local_data` directory to keep them for reference but out of the main codebase:

- `local_data/g_album_tool.rb` - Legacy main file
- `local_data/error_summary.rb` - Legacy error summary generator
- `local_data/tests/` - Legacy Minitest test files:
  - `test_file_processor.rb`
  - `test_error_handler.rb`
- `local_data/bin/` - Legacy bin files:
  - `galbumtool` - The original CLI tool
  - `run_tests` - Legacy test runner

## Files Retained in Main Directory

The following files/directories have been retained in the main directory structure as they are required for the RSpec tests to run:

- `tests/fixtures/` - Test fixtures directory used by both RSpec tests and setup scripts
  - This directory contains setup scripts for creating test files and directories

## RSpec Test Structure

The RSpec tests are organized in the `spec` directory:

- `spec/lib/g_album_tools/` - Unit tests for individual components
  - `file_processor_spec.rb` - Tests for the FileProcessor class
  - `error_handler_spec.rb` - Tests for the ErrorHandler class
- `spec/features/` - Integration/feature tests
  - `process_workflow_spec.rb` - Tests for the complete processing workflow

## Path Resolution

A key aspect of the migration was fixing path references in the tests. The main change was using `Dir.pwd` as the base directory for test fixtures instead of relying on relative paths:

```ruby
# Old approach (caused issues)
let(:test_source_dir) { File.join(root_dir, 'tests/fixtures/source') }

# New approach (works correctly)
let(:test_source_dir) { File.join(Dir.pwd, 'tests/fixtures/source') }
```

## Running Tests

To run the RSpec tests:

```bash
bundle exec rspec
```

This will execute all tests in the `spec` directory with the default formatter.

For more detailed output:

```bash
bundle exec rspec --format documentation
```

## Documentation Updates

The following documentation files have been updated to reflect the migration:

1. `README.md` - Updated project structure and development instructions
2. `ARCHITECTURE.md` - Updated directory structure and test organization
3. `Rakefile` - Set default task to run RSpec tests

## Future Considerations

1. The test fixtures setup could be further improved by using RSpec's built-in temporary directory helpers.
2. Additional tests could be written to increase coverage of edge cases.
3. The `tests/fixtures` directory could be moved to `spec/fixtures` for better organization, but this would require updating all path references in the tests. 

## Migration Completion

The migration is now considered complete. All tests are passing using RSpec, and the necessary documentation has been updated. Legacy files have been preserved in the `local_data` directory for reference, but they are no longer part of the active codebase.

Key benefits of this migration:
1. Better test organization with separate directories for features and unit tests
2. Improved test readability with RSpec's descriptive syntax
3. Easier test maintenance with RSpec's powerful matchers and hooks
4. Simplified test execution with the standard `bundle exec rspec` command 
