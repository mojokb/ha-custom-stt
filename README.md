# My Custom STT

This is a custom Speech-to-Text (STT) integration for Home Assistant.

## Features
- Custom STT engine
- Supports WAV audio files
- Multilingual support: English (en-US), Korean (ko-KR)

## Installation via HACS
1. Add this repository to HACS as a custom repository.
2. Search for "My Custom STT" in HACS integrations and install it.
3. Restart Home Assistant.
4. Add the following to your `configuration.yaml`:
   ```yaml
   stt:
     - platform: my_custom_stt
