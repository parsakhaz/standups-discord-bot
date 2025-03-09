# Changelog

All notable changes to the Standup Discord Bot project will be documented in this file.

## [2.0.2] - 2024-03-09

### Changed
- Changed initial reminder time from 10:30 AM to 9:30 AM
- Added second reminder at 10:15 AM for users who haven't responded yet
- Final follow-up remains at 11:00 AM

### Added
- New `/test-second-reminder` command to test the second reminder functionality

## [2.0.1] - 2024-03-09

### Changed
- Modified response tracking to include all messages in the standups channel
- Removed requirement for messages to start with "Standup:" prefix
- Updated daily and weekly recap commands to include all messages in the channel

## [2.0.0] - 2024-03-09

### Changed
- Major refactoring: Removed thread creation and management
- All standup activities now occur in a single channel
- Users must start their updates with "Standup:" for them to be tracked
- Reminders and follow-ups sent directly to standup channel
- Daily and weekly reports generated from channel messages
- Commands adjusted to work with the new single-channel model

### Removed
- Removed `/refresh-thread` command as it's no longer needed
- Eliminated thread creation and management code
- Removed thread-specific permissions requirement

### Added
- New format for reminders with date and template embedded in a single message
- Enhanced filtering for reports based on message content

## [1.1.0] - 2024-03-07

### Added
- Separated thread creation from reminder function
- Added 15-minute checks after midnight to create the day's thread early
- Added global tracking of today's thread with the `today_thread` variable
- Added `/refresh-thread` command to manually refresh the thread reference

### Changed
- Thread is now created after midnight instead of at reminder time
- Reminder now uses the existing thread instead of creating a new one
- Added explicit AM/PM clarification for reminder and follow-up times
- Improved message formatting for better readability
- Updated logs to be more descriptive

### Removed
- Removed `/test` command as it was redundant

### Fixed
- Thread creation and tracking now more reliable
- Reminder and followup functions now consistently use the same thread
- Clarified that reminder and deadline times are in 24-hour format (10:30 = 10:30 AM)

## [1.0.0] - Initial Release

### Features
- Daily standup reminders at configurable times
- Automatic thread creation with proper date formatting
- Follow-up reminders for users who haven't responded
- User management commands for the notification list
- Customizable reminder times, deadlines, and timezone settings
- Daily and weekly report generation
- Customizable standup templates
- Automatic tracking of user responses 