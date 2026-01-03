For local speech-to-text with Ollama, **Whisper** is the best choice—specifically **Whisper v3-turbo** for English or **Whisper v3-large** for multilingual needs. While Ollama primarily runs LLMs, you can integrate Whisper as a separate component in your voice pipeline.[1][2]

## Recommended Setup

**Best Model**: Whisper v3-turbo offers the optimal balance of speed and accuracy for English transcription. For Indian languages or mixed-language audio (like Malay-English), large-v3-turbo performs surprisingly well.[1]

**Integration Approach**: Run Whisper and Ollama as separate services. Use Whisper for speech-to-text, pass the transcript to Ollama for LLM processing, then add a TTS model for the complete voice assistant pipeline.[3][4]

## Implementation Options

- **CPU Offloading**: Run Whisper on CPU while Ollama uses your AMD 7900GRE GPU. This works because CPU typically sits idle during LLM inference, making brief 1-2 second transcription spikes manageable.[5]

- **Ready-Made Solutions**: Projects like **ollama-voice**  and **ollama-STT-TTS**  provide pre-built Python scripts that combine Whisper, Ollama, and TTS engines. These run 100% locally and support wakeword detection.[6][3]

- **API Approach**: Set up FastWhisperAPI as a dedicated STT endpoint, then connect it to your Ollama instance. This modular setup lets you swap components easily.[4]

## Resource Considerations

Your AMD 7900GRE with 16GB VRAM can handle this efficiently. The whisper-tiny model (available in Ollama's library) uses minimal resources but sacrifices accuracy. For your deepfake detection work requiring high-quality transcripts, stick with the larger Whisper variants and run them on CPU to preserve GPU memory for your ML models.[7]

[1](https://www.reddit.com/r/LocalLLaMA/comments/1g2shx7/whats_the_best_open_source_speech_to_text_model/)
[2](https://www.gladia.io/blog/best-open-source-speech-to-text-models)
[3](https://github.com/maudoin/ollama-voice)
[4](https://www.youtube.com/watch?v=xu-8hLOAI94)
[5](https://www.reddit.com/r/ollama/comments/1og4c2q/running_ollama_with_whisper/)
[6](https://github.com/BranchingBad/ollama-STT-TTS)
[7](https://ollama.com/dimavz/whisper-tiny)
[8](https://www.reddit.com/r/ollama/comments/1fd3bg6/best_model_for_transcription_with_ollama/)
[9](https://www.youtube.com/watch?v=MpVNZA6__3o)
[10](https://ollama.com/legraphista/Orpheus)
[11](https://www.youtube.com/watch?v=iTnpWmty52U)
[12](https://www.reddit.com/r/LocalLLaMA/comments/1f0awd6/best_local_open_source_texttospeech_and/)
[13](https://community.start9.com/t/setting-up-speech-to-text-stt-settings/2788)
[14](https://www.runpod.io/articles/guides/run-ollama-whisper-comfyui-one-container)
[15](https://modal.com/blog/open-source-tts)
[16](https://www.youtube.com/watch?v=lSqKx3D5iis)
[17](https://dev.to/zackriya/local-meeting-notes-with-whisper-transcription-ollama-summaries-gemma3n-llama-mistral--2i3n)
[18](https://ollama.com/library)
[19](https://www.arsturn.com/blog/give-your-ollama-a-voice-a-guide-to-local-asr-tts)
[20](https://www.reddit.com/r/LocalLLaMA/comments/18trhzi/offline_voice_assistant_using_ollama_api_mistral/)

For your Ubuntu voice typing project, you'll need three components: **Whisper** for speech-to-text, **audio capture**, and **system-wide typing**. While Ollama has whisper models, running Whisper standalone gives you better control for real-time transcription.

## Core Architecture

**Whisper Integration**: Use `whisper.cpp` or the Python `openai-whisper` library. The `ollama-voice` GitHub project shows how to pipe Whisper transcripts directly into Ollama, then type responses system-wide. For pure dictation, skip the LLM step and just type the transcript.[1]

**System-Wide Typing**: Install `ydotool` (works on both X11 and Wayland) to simulate keyboard input at the cursor position. The `voice_typing` bash script demonstrates this perfectly—it captures audio, runs Whisper, then uses ydotool to type into any active window.[2]

## Implementation Steps

- **Setup Audio**: Use `sox` or `arecord` for microphone capture. The `voice_typing` project uses sox for recording and can process audio in real-time.[2]

- **Active Window Detection**: For X11, `xdotool getactivewindow` works. On Wayland (Ubuntu 22.04+), use `ydotool` with window focus events.[2]

- **Trigger Mechanism**: Create a keyboard shortcut (like Ctrl+Space) that starts/stops listening. The Ubuntu dictation guide shows how to set this up with systemd services for persistent background operation.[3]

## Recommended Models

Given your AMD 7900GRE, **Whisper v3-turbo** runs efficiently on CPU while your GPU handles other tasks. For real-time performance, use the `base` or `small` Whisper models—they transcribe in under a second with good accuracy. The `ollama/whisper` library has these quantized variants ready.[4][5][6]

## Project Structure

The `ollama-STT-TTS` repository provides a complete Python framework you can adapt. It handles wakeword detection, audio streaming, and system integration. For your use case, modify it to:[7]
1. Listen continuously when activated
2. Detect silence to auto-stop
3. Pipe transcript directly to ydotool instead of Ollama

This setup will let you dictate into any application—terminals, browsers, IDEs—wherever your cursor is active.[8]

[1](https://github.com/maudoin/ollama-voice)
[2](https://github.com/themanyone/voice_typing)
[3](https://alterflow.ai/blog/offline-voice-typing-on-ubuntu)
[4](https://www.tecmint.com/whisper-ai-audio-transcription-on-linux/)
[5](https://www.reddit.com/r/LocalLLaMA/comments/1g2shx7/whats_the_best_open_source_speech_to_text_model/)
[6](https://ollama.com/dimavz/whisper-tiny)
[7](https://github.com/BranchingBad/ollama-STT-TTS)
[8](https://gist.github.com/baztian/edf5d1256d59fdf523be4e873c0f5299)
[9](https://www.reddit.com/r/linux/comments/1gwtysx/systemwide_voice_typing_scripts_using_cloudbased/)
[10](https://www.reddit.com/r/linuxquestions/comments/1ix4y3r/how_can_i_do_voice_to_text_on_linux_voice_typing/)
[11](https://www.youtube.com/watch?v=BLq0EpqNO40)
[12](https://www.reddit.com/r/ollama/comments/1jo46vx/i_built_a_voice_assistant_that_types_for_me/)
[13](https://blog.cdnsun.com/speech-to-text-for-ubuntu/)
[14](https://open-vsx.org/extension/KadirYapar/speech-to-cursor)
[15](https://www.instructables.com/How-to-Voice-Type-in-Linux/)
[16](https://www.reddit.com/r/ollama/comments/1mq6pi7/ollama_but_for_realtime_speechtotext/)
[17](https://www.reddit.com/r/cursor/comments/1k9dl49/anyone_interested_to_linux_speech_to_text_for/)
[18](https://www.reddit.com/r/linuxquestions/comments/xb6nld/voice_dictation_software_recommended_for_linux/)
[19](https://github.com/ollama/ollama/issues/5451)
[20](https://forum.cursor.com/t/voice-input-not-working-in-cursor-ide/146412)
[21](https://picovoice.ai/blog/ubuntu-speech-to-text-tutorial/)
[22](https://www.youtube.com/watch?v=lSqKx3D5iis)
[23](https://www.hume.ai/blog/controlling-your-computer-with-voice)
[24](https://www.youtube.com/watch?v=PAzVMJ_6pbQ)