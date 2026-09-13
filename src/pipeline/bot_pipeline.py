import asyncio
import numpy as np
from typing import Optional, Dict, Any, Tuple
from loguru import logger
from src.services.stt_service import STTService
from src.services.llm_service import LLMService
from src.services.tts_service import TTSService
from src.config import settings

class VoiceBotPipeline:
    def __init__(
        self,
        caller_phone: str = "+919876543210",
        stt_service: Optional[STTService] = None,
        llm_service: Optional[LLMService] = None,
        tts_service: Optional[TTSService] = None,
        silence_duration_seconds: float = 1.7,
        energy_threshold: float = 0.040  # RMS volume threshold for speech detection
    ):
        self.caller_phone = caller_phone
        self.stt = stt_service or STTService(model_size=settings.STT_MODEL_SIZE)
        self.llm = llm_service or LLMService()
        self.tts = tts_service or TTSService()
        
        self.silence_duration = silence_duration_seconds
        self.energy_threshold = energy_threshold
        
        # State tracking
        self.conversation = self.llm.create_initial_conversation(caller_phone=self.caller_phone)
        self.is_speaking = False
        self.is_processing = False
        self.audio_buffer = []
        self.silence_samples = 0
        self.sample_rate = 16000  # Standard internal sample rate

    def set_caller(self, caller_phone: str) -> Tuple[str, bytes]:
        """
        Sets the caller phone number, resets the conversation context, 
        and generates the initial welcome greeting audio.
        """
        self.caller_phone = caller_phone
        self.conversation = self.llm.create_initial_conversation(caller_phone=self.caller_phone)
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_samples = 0
        
        greeting_text = self.llm.get_initial_greeting(self.caller_phone)
        greeting_wav = self.tts.synthesize_wav_bytes(greeting_text)
        return greeting_text, greeting_wav

    def reset_conversation(self):
        """Resets conversation state for the current caller."""
        self.conversation = self.llm.create_initial_conversation(caller_phone=self.caller_phone)
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_samples = 0

    def process_audio_chunk(self, chunk_pcm: np.ndarray) -> Optional[np.ndarray]:
        """
        Buffers incoming 16kHz float32 audio chunks and performs voice activity detection (VAD).
        Returns a complete numpy audio array when the caller finishes speaking.
        """
        # Calculate Root Mean Square (RMS) volume energy of this chunk
        rms = np.sqrt(np.mean(chunk_pcm**2)) if len(chunk_pcm) > 0 else 0
        chunk_len = len(chunk_pcm)
        
        if rms > self.energy_threshold:
            # User is actively speaking
            self.is_speaking = True
            self.silence_samples = 0
            self.audio_buffer.append(chunk_pcm)
        elif self.is_speaking:
            # User was speaking, now silent
            self.audio_buffer.append(chunk_pcm)
            self.silence_samples += chunk_len
            
            # Check if silence exceeded the threshold duration
            if (self.silence_samples / self.sample_rate) >= self.silence_duration:
                # Turn finished! Assemble full audio segment
                full_audio = np.concatenate(self.audio_buffer)
                self.audio_buffer.clear()
                self.is_speaking = False
                self.silence_samples = 0
                return full_audio
                
        return None

    async def execute_turn(self, speech_audio: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Full async pipeline turn:
        1. STT transcribes speech audio.
        2. LLM resolves tools and crafts natural phone reply.
        3. TTS generates audio WAV bytes.
        """
        # Discard transient noise clicks shorter than 0.4s (6400 samples at 16kHz)
        if len(speech_audio) < 6400:
            return None

        if self.is_processing:
            return None
        self.is_processing = True

        try:
            # Step 1: STT
            transcript = self.stt.transcribe_audio_array(speech_audio)
            if not transcript or len(transcript.strip()) < 2 or set(transcript.strip()).issubset({'.', ',', '!', '?', '-', '_', ' ', ':', ';'}):
                return None
                
            logger.info(f"Caller [{self.caller_phone}] Transcribed: '{transcript}'")
            
            # Step 2: Instant Fast-Path for conversational checks/greetings
            norm = transcript.strip().lower().replace("?", "").replace("!", "").replace(".", "")
            if norm in ["hello", "hi", "hey", "hello priya", "hi priya", "ಹಲೋ", "ಹಲೋ ಪ್ರಿಯಾ", "ನಮಸ್ಕಾರ", "ಯಾರಿದ್ದೀರಿ"]:
                from src.database.customer_repo import get_customer
                cust = get_customer(self.caller_phone)
                name = cust['name'] if cust else "ಸರ್"
                ai_reply = f"ಹಲೋ {name}, ನಾನು ಪ್ರಿಯಾ. ಡಿಮಾರ್ಟ್ ಎಕ್ಸ್‌ಪ್ರೆಸ್‌ನಿಂದ. ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು ಹೇಳಿ?"
                logger.info(f"Fast-Path Priya Reply: '{ai_reply}'")
                wav_bytes = self.tts.synthesize_wav_bytes(ai_reply)
                return {
                    "transcript": transcript,
                    "reply_text": ai_reply,
                    "wav_bytes": wav_bytes
                }

            # Step 3: LLM Conversation + Tool Execution
            self.conversation.append({"role": "user", "content": transcript})
            ai_reply = await self.llm.chat(self.conversation, caller_phone=self.caller_phone)
            logger.info(f"Priya Reply: '{ai_reply}'")
            
            # Step 3: Fast TTS Synthesis
            wav_bytes = self.tts.synthesize_wav_bytes(ai_reply)
            
            return {
                "transcript": transcript,
                "reply_text": ai_reply,
                "wav_bytes": wav_bytes
            }
        finally:
            self.is_processing = False

    async def execute_text_turn(self, user_text: str) -> Dict[str, Any]:
        """Direct text-based turn for testing / CLI simulation."""
        logger.info(f"Caller [{self.caller_phone}] Input: '{user_text}'")
        norm = user_text.strip().lower().replace("?", "").replace("!", "").replace(".", "")
        if norm in ["hello", "hi", "hey", "hello priya", "hi priya", "ಹಲೋ", "ಹಲೋ ಪ್ರಿಯಾ", "ನಮಸ್ಕಾರ", "ಯಾರಿದ್ದೀರಿ"]:
            from src.database.customer_repo import get_customer
            cust = get_customer(self.caller_phone)
            name = cust['name'] if cust else "ಸರ್"
            ai_reply = f"ಹಲೋ {name}, ನಾನು ಪ್ರಿಯಾ. ಡಿಮಾರ್ಟ್ ಎಕ್ಸ್‌ಪ್ರೆಸ್‌ನಿಂದ. ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು ಹೇಳಿ?"
            logger.info(f"Fast-Path Priya Reply: '{ai_reply}'")
            wav_bytes = self.tts.synthesize_wav_bytes(ai_reply)
            return {
                "transcript": user_text,
                "reply_text": ai_reply,
                "wav_bytes": wav_bytes
            }
        self.conversation.append({"role": "user", "content": user_text})
        ai_reply = await self.llm.chat(self.conversation, caller_phone=self.caller_phone)
        logger.info(f"Priya Reply: '{ai_reply}'")
        wav_bytes = self.tts.synthesize_wav_bytes(ai_reply)
        return {
            "transcript": user_text,
            "reply_text": ai_reply,
            "wav_bytes": wav_bytes
        }
