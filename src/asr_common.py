"""Canonical mixed-script normalization and audio checks from the saved pilot."""
import hashlib
import io
import math
import unicodedata

import numpy as np
import soundfile as sf

COLUMNS = ['audio', 'transcription', 'transcription_devanagari', 'transcription_romanized',
           'cmi', 'speech_type', 'speaker_id', 'video_id', 'start_ms', 'end_ms', 'duration_s']


def normalize_text(text):
    text = unicodedata.normalize('NFC', text).lower()
    text = text.translate(str.maketrans('०१२३४५६७८९', '0123456789'))
    text = ''.join(' ' if unicodedata.category(char).startswith('P') else char for char in text)
    return ' '.join(text.split())


def prepare_clip(row, split):
    video_id = row.get('video_id')
    start, end = row.get('start_ms'), row.get('end_ms')
    if (not isinstance(video_id, str) or not video_id.strip()
            or any(not isinstance(value, int) or isinstance(value, bool) for value in (start, end))
            or not 0 <= start < end):
        raise ValueError('Missing or invalid video_id/start_ms/end_ms; inspect clip provenance.')
    key = f'{split}/{video_id}/{start}-{end}'
    reference, cmi = row.get('transcription'), row.get('cmi')
    if not isinstance(reference, str) or not normalize_text(reference):
        raise ValueError(f'Empty or invalid reference for {key}.')
    if isinstance(cmi, bool) or not isinstance(cmi, (int, float)) or not math.isfinite(cmi) or not 0 <= cmi <= 50:
        raise ValueError(f'Invalid bilingual CMI for {key}.')
    encoded = row.get('audio')
    if not isinstance(encoded, dict) or not isinstance(encoded.get('bytes'), bytes) or not encoded['bytes']:
        raise ValueError(f'Expected embedded WAV bytes for {key}.')
    waveform, sample_rate = sf.read(io.BytesIO(encoded['bytes']), dtype='float32', always_2d=True)
    if sample_rate != 16000 or waveform.shape[0] == 0 or waveform.shape[1] == 0 or not np.isfinite(waveform).all():
        raise ValueError(f'Invalid or non-finite audio for {key}; expected nonempty 16 kHz audio.')
    channels = waveform.shape[1]
    audio = waveform.mean(axis=1)
    duration = len(audio) / sample_rate
    expected = row.get('duration_s')
    if (not 0 < duration <= 30 or isinstance(expected, bool)
            or not isinstance(expected, (int, float)) or not math.isfinite(expected)
            or abs(duration - expected) > 0.02 or abs(duration - (end - start) / 1000) > 0.02):
        raise ValueError(f'Audio duration does not match metadata/provenance for {key}.')
    identity = {name: row[name] for name in COLUMNS if name != 'audio'}
    identity.update(clip_id=key, decoded_duration_s=duration, sample_rate=sample_rate,
                    source_channels=channels, audio_sha256=hashlib.sha256(audio.tobytes()).hexdigest())
    return {'identity': identity, 'audio': audio}
