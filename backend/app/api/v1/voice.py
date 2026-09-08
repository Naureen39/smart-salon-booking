"""Voice conversation WebSocket (docs plan §9.5): mic audio in -> faster-whisper
STT -> the same conversation orchestrator used by text chat -> TTS -> audio
out. VAD serves two roles: detecting end-of-utterance (enough trailing
silence after speech means "the caller is done talking, transcribe now") and
barge-in (speech arriving while a reply is still being sent cancels it).

Auth note: browsers can't easily set custom headers on a WebSocket handshake,
so the (short-lived, 15-minute) access token is passed as a query parameter
instead of an Authorization header — a common, documented FastAPI pattern,
accepted here given the token's short lifetime.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.orchestrator import process_turn
from app.ai.stt import pcm16_to_wav_bytes, transcribe_wav_bytes
from app.ai.tts import TTSEngine, get_tts_engine
from app.ai.vad import FRAME_DURATION_MS, VoiceActivityDetector
from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.core.security import decode_token
from app.db.models.conversation_session import ConversationSession
from app.db.models.user import User
from app.db.session import async_session_factory

router = APIRouter(prefix="/voice", tags=["voice"])
settings = get_settings()

SAMPLE_RATE = 16000
SILENCE_THRESHOLD_MS = 800


class UtteranceBuffer:
    """Accumulates PCM frames until enough trailing silence follows detected
    speech — independently testable without any WebSocket involved."""

    def __init__(self, silence_threshold_ms: int = SILENCE_THRESHOLD_MS) -> None:
        self.buffer = bytearray()
        self.silence_ms = 0
        self.has_speech = False
        self._silence_threshold_ms = silence_threshold_ms

    def add_frame(self, frame: bytes, is_speech: bool, frame_duration_ms: int = FRAME_DURATION_MS) -> bool:
        """Returns True if this frame completes an utterance."""
        self.buffer.extend(frame)
        if is_speech:
            self.has_speech = True
            self.silence_ms = 0
        else:
            self.silence_ms += frame_duration_ms
        return self.has_speech and self.silence_ms >= self._silence_threshold_ms

    def pop(self) -> bytes:
        audio = bytes(self.buffer)
        self.buffer.clear()
        self.has_speech = False
        self.silence_ms = 0
        return audio


async def _authenticate(token: str) -> User | None:
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    subject = payload.get("sub")
    if subject is None:
        return None

    # A fresh engine, not the app's module-level one: this runs once per WS
    # connection rather than per-request, so it doesn't share the request/
    # response DI cycle the rest of the app uses — creating its own engine
    # keeps it correct under any event-loop lifecycle (tests included).
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as db:
            user = await db.get(User, uuid.UUID(subject))
            if user is None or not user.is_active:
                return None
            return user
    finally:
        await engine.dispose()


async def _send_reply_audio(websocket: WebSocket, tts_engine: TTSEngine, text: str) -> None:
    audio = await asyncio.to_thread(tts_engine.synthesize, text)
    await websocket.send_bytes(audio)


async def _is_over_connection_limit(client_ip: str | None) -> bool:
    """Manual Redis-backed rate limit on new voice WS connections per minute
    (docs plan §7.5/§8) — slowapi's decorator targets regular HTTP request/
    response routes, not persistent WebSocket connections, so this protects
    the STT quota the same way without depending on it for a WS handler."""
    if not client_ip:
        return False
    key = f"voice_ws_connections:{client_ip}:{datetime.now(UTC).strftime('%Y%m%d%H%M')}"
    redis_client = get_redis_client()
    count = await redis_client.incr(key)
    await redis_client.expire(key, 90)
    return count > settings.rate_limit_voice_per_minute


@router.websocket("/{session_id}")
async def voice_conversation(websocket: WebSocket, session_id: uuid.UUID, token: str = Query(...)) -> None:
    client_ip = websocket.client.host if websocket.client else None
    if await _is_over_connection_limit(client_ip):
        await websocket.close(code=4429)
        return

    user = await _authenticate(token)
    if user is None:
        await websocket.close(code=4401)
        return

    async with async_session_factory() as db:
        session = await db.get(ConversationSession, session_id)
        if session is None or session.client_id != user.id:
            await websocket.close(code=4404)
            return

        await websocket.accept()
        vad = VoiceActivityDetector(sample_rate=SAMPLE_RATE)
        utterance = UtteranceBuffer()
        tts_engine = get_tts_engine()
        playback_task: asyncio.Task[None] | None = None

        try:
            while True:
                frame = await websocket.receive_bytes()
                step = vad.frame_bytes
                for i in range(0, len(frame) - step + 1, step):
                    chunk = frame[i : i + step]
                    is_speech = vad.is_speech(chunk)

                    if is_speech and playback_task is not None and not playback_task.done():
                        playback_task.cancel()
                        playback_task = None

                    if utterance.add_frame(chunk, is_speech):
                        pcm_audio = utterance.pop()
                        wav_audio = pcm16_to_wav_bytes(pcm_audio, sample_rate=SAMPLE_RATE)
                        transcript = transcribe_wav_bytes(wav_audio)
                        if not transcript:
                            continue

                        result = await process_turn(db, session=session, message=transcript, client_id=user.id)
                        await websocket.send_json(
                            {
                                "type": "turn",
                                "transcript": transcript,
                                "reply_text": result.reply_text,
                                "appointment_id": result.appointment_id,
                            }
                        )
                        playback_task = asyncio.create_task(_send_reply_audio(websocket, tts_engine, result.reply_text))
        except WebSocketDisconnect:
            if playback_task is not None:
                playback_task.cancel()
            return
