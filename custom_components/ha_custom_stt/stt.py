"""Support for the cloud for speech to text service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CONF_API_KEY = "api_key"

SUPPORTED_LANGUAGES = [
    "en-US",
    "ko-KR",
]

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Azure STT component."""
    api_key = config.get(CONF_API_KEY)

    return RsTunedSTTProvider(hass, api_key)


class RsTunedSTTProvider(Provider):
    """The Azure STT API provider."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init Azure STT service."""
        self.name = "RS-Tuned STT"
        self.api_key = entry.data[CONF_API_KEY]
        self._client = None

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        headers = {"x-functions-key": self.api_key}
        url = "https://rs-audio-router.azurewebsites.net"

        # start the request immediately (before we have all the data), so that
        # it finishes as early as possible. aiohttp will fetch the data
        # asynchronously from 'stream' as they arrive and send them to the server.
        try:
            async with async_timeout.timeout(15), aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=stream) as response:
                    if response.status != 200:
                        raise Exception(
                            f"azure stt failed status={response.status} response={await response.text()}"
                        )

                    response_json = await response.json()
                    _LOGGER.debug("azure stt returned %s", response_json)

                    if response_json["RecognitionStatus"] != "Success":
                        raise Exception(f"azure stt failed response={response_json}")

                    return SpeechResult(
                        response_json["DisplayText"],
                        SpeechResultState.SUCCESS,
                    )
        except:
            _LOGGER.exception("Error running azure stt")

            return SpeechResult("", SpeechResultState.ERROR)
