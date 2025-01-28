import os
import tempfile
import warnings
from pathlib import Path

from aider.llm import litellm

try:
    import sounddevice as sd
    import soundfile as sf
except (OSError, ModuleNotFoundError):
    sd = None
    sf = None


class SoundDeviceError(Exception):
    pass


class TTS:
    def __init__(self, device_name=None):
        if sf is None or sd is None:
            raise SoundDeviceError("Sound device libraries not available")
            
        try:
            print("Initializing sound device...")
            devices = sd.query_devices()

            if device_name:
                # Find the device with matching name
                device_id = None
                for i, device in enumerate(devices):
                    if device_name in device["name"]:
                        device_id = i
                        break
                if device_id is None:
                    available_outputs = [d["name"] for d in devices if d["max_output_channels"] > 0]
                    raise ValueError(f"Device '{device_name}' not found. Available output devices:" f" {available_outputs}")

                print(f"Using output device: {device_name} (ID: {device_id})")
                self.device_id = device_id
            else:
                self.device_id = None

        except sd.PortAudioError as err:
            raise SoundDeviceError(f"Error accessing audio output device: {err}")

    def speak(self, text: str, voice: str = "alloy", model: str = "tts-1") -> None:
        """
        Convert text to speech and play it through the audio device.
        
        Args:
            text: The text to convert to speech
            voice: The voice to use (e.g. "alloy", "echo", "fable", "onyx", "nova", "shimmer")
            model: The TTS model to use (default: "tts-1")
        """
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Generate speech using litellm
            response = litellm.speech(
                model=f"openai/{model}",
                voice=voice,
                input=text,
            )
            response.stream_to_file(temp_path)

            # Play the audio file
            data, samplerate = sf.read(temp_path)
            sd.play(data, samplerate, device=self.device_id)
            sd.wait()  # Wait until audio is finished playing

        except Exception as e:
            print(f"Error during text-to-speech: {e}")
        finally:
            # Clean up temp file
            if temp_path.exists():
                os.unlink(temp_path)


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")
    
    tts = TTS()
    tts.speak("Hello! This is a test of the text to speech system.")
