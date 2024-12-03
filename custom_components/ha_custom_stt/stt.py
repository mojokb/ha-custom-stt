import datetime
import io
import logging
import wave
from collections.abc import AsyncIterable
from typing import Optional

import aiohttp
import async_timeout
import netifaces
import requests
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.core import HomeAssistant
from pydub import AudioSegment

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config: dict, async_add_entities, discovery_info=None
):
    """Set up the custom STT platform."""
    async_add_entities([CustomSTTProvider()])


class CustomSTTProvider(SpeechToTextEntity):
    """Custom STT Provider."""

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    @property
    def supported_languages(self) -> list[str]:
        """Return the list of supported languages."""
        return ["en-US", "ko-KR"]

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def engine(self) -> str:
        """Name of the STT engine."""
        return "custom_stt_engine"

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    async def _transcribe_audio(
        self, metadata: SpeechMetadata, stream: bytes
    ) -> Optional[str]:
        """Transcribe audio using custom STT API."""
        try:
            # STT API 호출 설정
            api_url = "https://api.example.com/stt"
            headers = {
                "Authorization": "Bearer YOUR_API_KEY",
                "Content-Type": "audio/wav",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url, headers=headers, data=stream
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("transcription")
                    else:
                        _LOGGER.error("STT API returned error: %s", response.status)
        except Exception as e:
            _LOGGER.error("Error during STT processing: %s", e)
        return None

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process the audio stream and return the speech result."""
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        _LOGGER.debug(f"$$$ voice data size : {len(audio_data)}")
        if len(audio_data) <= 1000:
            _LOGGER.debug("No audio data received.")
            return SpeechResult("", SpeechResultState.ERROR)

        # Create an audio stream that complies with the API requirements
        wav_stream = io.BytesIO()
        with wave.open(wav_stream, "wb") as wf:
            wf.setnchannels(metadata.channel)
            wf.setsampwidth(metadata.bit_rate // 8)
            wf.setframerate(metadata.sample_rate)
            wf.writeframes(audio_data)

        current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        mp3_path = f"/config/stt/stt_{current_time}.mp3"

        def job():
            # Convert WAV to MP3
            wav_stream.seek(0)  # 스트림의 위치를 처음으로 되돌림
            sound = AudioSegment.from_file(wav_stream, format="wav")
            sound.export(mp3_path, format="mp3")
            return mp3_path

        async with async_timeout.timeout(10):
            response = await self.hass.async_add_executor_job(job)
            if response:
                # await self.async_send_audio_data(mp3_path, response.text)
                self.hass.create_task(
                    self.async_send_audio_data(mp3_path, "transcribed text")
                )
                return SpeechResult(
                    "transcribed text",
                    SpeechResultState.SUCCESS,
                )
            return SpeechResult("", SpeechResultState.ERROR)

    async def async_send_audio_data(self, file_path, text):
        url = "https://rs-audio-router.azurewebsites.net/api/v1/audio-routing"
        mac_address = netifaces.ifaddresses("end0")[netifaces.AF_LINK][0]["addr"]
        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        headers = {"x-functions-key": "!234"}
        data = {"text": text, "timestamp": str(timestamp), "macAddress": mac_address}
        _LOGGER.debug(f"$$$ filename : {file_path},  datas: {data}")

        def job():
            with open(file_path, "rb") as file:
                files = {"audio": file}
                response = requests.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                return response.json()

        try:
            async with async_timeout.timeout(10):
                response = await self.hass.async_add_executor_job(job)
                _LOGGER.debug(f"$$$ Response : {response}")
                return response
        except Exception as e:
            # print(f"An error occurred: {e}")
            _LOGGER.error(f"An error occurred: {e}")
            return None
