"""Save human listening decisions separately from the published references."""
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import math
import unicodedata

from asr_common import normalize_text
from local_whisper_pilot import save_state


def validate_reviews(state, selection):
    """Validate saved judgments without asserting that their spoken content is correct."""
    reviews, clips = state['reviews'], selection['clips']
    if len(reviews) != 50 or len(clips) != 50:
        raise ValueError('The frozen audit requires the selected 50 reviews.')
    identities = [entry['identity']['clip_id'] for entry in clips]
    if len(set(identities)) != 50:
        raise ValueError('Duplicate selected clip identities.')
    tag_corrections = []
    for number, (review, entry) in enumerate(zip(reviews, clips), 1):
        identity = entry['identity']
        if review.get('number') != number or review.get('clip_id') != identity['clip_id']:
            raise ValueError(f'Review {number}: identity/order mismatch.')
        if review.get('verdict') not in {'match', 'corrected'}:
            raise ValueError(f'Review {number}: pending/unsure decisions need resolution before this freeze.')
        reference, languages = review.get('corrected_reference'), review.get('token_languages')
        if not isinstance(reference, str) or not isinstance(languages, list):
            raise ValueError(f'Review {number}: missing reference/tags.')
        calculated = tagged_cmi(reference, languages)
        stored = review.get('audited_cmi')
        if (calculated is None or isinstance(stored, bool) or not isinstance(stored, (int, float))
                or not math.isfinite(stored) or not math.isclose(calculated, stored, abs_tol=1e-10)):
            raise ValueError(f'Review {number}: unresolved or inconsistent CMI.')
        if review.get('normalized_tokens') != normalize_text(reference).split():
            raise ValueError(f'Review {number}: normalized tokens differ.')
        same = reference == identity['transcription']
        if (review['verdict'] == 'match') != same:
            raise ValueError(f'Review {number}: verdict differs from reference edit status.')
        if not isinstance(review.get('notes'), str) or not isinstance(review.get('reviewed_at_utc'), str):
            raise ValueError(f'Review {number}: missing notes/review timestamp.')
        reviewed_at = datetime.fromisoformat(review['reviewed_at_utc'])
        if reviewed_at.utcoffset() is None:
            raise ValueError(f'Review {number}: timestamp needs a timezone.')
        method = review.get('tagging_method')
        if method not in {'manual', 'script_suggestions_human_checked'}:
            raise ValueError(f'Review {number}: unknown tagging method.')
        if method == 'script_suggestions_human_checked':
            suggested = suggest_language_tags(reference)
            if review.get('suggested_token_languages') != suggested:
                raise ValueError(f'Review {number}: suggested-tag provenance differs.')
            if languages != suggested:
                tag_corrections.append(number)
    return {'reviewed_clips': len(reviews), 'verdict_counts': dict(Counter(r['verdict'] for r in reviews)),
            'tagging_methods': dict(Counter(r['tagging_method'] for r in reviews)),
            'reviews_with_tag_overrides': tag_corrections,
            'unresolved_cmi': 0, 'pending_or_unsure': 0,
            'human_audio_listening_independently_verified_by_code': False}


def freeze_validated_audit(path, selection_path, pool_path, reviewer):
    """Back up exact input bytes, write a frozen snapshot, then lock notebook saves."""
    from prepare_test_set import frozen_write
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('Use a nonempty reviewer name or pseudonym.')
    content = path.read_bytes()
    state = json.loads(content)
    selection_content = selection_path.read_bytes()
    selection = json.loads(selection_content)
    if state['selection_sha256'] != hashlib.sha256(selection_content).hexdigest():
        raise ValueError('Selection checksum differs from the reviewed selection.')
    if selection['evaluation_manifest_sha256'] != hashlib.sha256(pool_path.read_bytes()).hexdigest():
        raise ValueError('Evaluation pool differs from the selected pool.')
    summary = validate_reviews(state, selection)
    frozen_on = state.get('frozen_at_utc', datetime.now(timezone.utc).isoformat())
    day = datetime.fromisoformat(frozen_on).strftime('%Y%m%d')
    snapshot = path.parent / f'reference_audit_{day}_frozen.json'
    backup = path.parent / f'reference_audit_{day}_pre_freeze.json'
    if state.get('frozen'):
        if state.get('reviewer') != reviewer or not snapshot.exists() or snapshot.read_bytes() != content:
            raise ValueError('Frozen audit differs from its snapshot or reviewer; preserve it and investigate.')
        return snapshot, summary
    if state.get('reviewer') and state['reviewer'] != reviewer:
        raise ValueError('Preserve the recorded reviewer identity.')
    if backup.exists():
        if backup.read_bytes() != content:
            raise ValueError('Pre-freeze backup differs; preserve earlier evidence.')
    else:
        with backup.open('xb') as stream:
            stream.write(content)
    state.update(reviewer=reviewer, frozen=True, frozen_at_utc=frozen_on,
                 reviewer_label_source='Single session researcher; pseudonym for the user-reported listening review.',
                 pre_freeze_sha256=hashlib.sha256(content).hexdigest(),
                 human_review_basis='Researcher reports completing all 50 listening/tag reviews in chat; code validates records, not speech judgments.')
    frozen_write(snapshot, state)
    if path.read_bytes() != content:
        raise ValueError('Review file changed during freeze; do not overwrite concurrent edits.')
    # Match the immutable snapshot byte for byte, including its recorded freeze metadata.
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(snapshot.read_bytes())
    temporary.replace(path)
    return snapshot, summary


def suggest_language_tags(reference):
    """Script-based drafts only; lexical language still requires human review."""
    tags = []
    for token in normalize_text(reference).split():
        scripts = set()
        for char in token:
            if unicodedata.category(char).startswith('L'):
                name = unicodedata.name(char, '')
                scripts.add('ne' if name.startswith('DEVANAGARI ') else
                            'en' if name.startswith('LATIN ') else 'ambiguous')
        tags.append(next(iter(scripts)) if len(scripts) == 1 else 'ambiguous' if scripts else 'other')
    return tags


def tagged_cmi(reference, languages):
    tokens = normalize_text(reference).split()
    if not tokens or len(tokens) != len(languages):
        raise ValueError(f'Provide one tag per normalized token ({len(tokens)} tokens): {tokens}')
    if any(tag not in {'ne', 'en', 'other', 'ambiguous'} for tag in languages):
        raise ValueError('Allowed tags: ne, en, other, ambiguous.')
    if 'ambiguous' in languages:
        return None
    ne, en = languages.count('ne'), languages.count('en')
    return 100 * min(ne, en) / (ne + en) if ne + en else None


def save_review(path, number, corrected_reference, languages, verdict, notes='', *, tagging_method='manual'):
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('frozen'):
        raise ValueError('Audit is frozen; preserve it rather than overwriting reviews.')
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(state['reviews']):
        raise ValueError('Unknown review number.')
    if verdict not in {'match', 'corrected', 'unsure'} or not isinstance(notes, str):
        raise ValueError('Use match, corrected, or unsure and text notes.')
    if not isinstance(corrected_reference, str) or not isinstance(languages, list):
        raise ValueError('Supply the listened-to reference as text and a list of language tags.')
    if tagging_method not in {'manual', 'script_suggestions_human_checked'}:
        raise ValueError('Unknown tagging method.')
    cmi = tagged_cmi(corrected_reference, languages)
    selection_path = path.parents[1] / 'manifests/reference_audit_20261105_selection.json'
    if hashlib.sha256(selection_path.read_bytes()).hexdigest() != state['selection_sha256']:
        raise ValueError('Audit selection checksum differs.')
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    review = state['reviews'][number - 1]
    identity = selection['clips'][number - 1]['identity']
    if review['clip_id'] != identity['clip_id']:
        raise ValueError('Review identity differs from the selected source.')
    if verdict == 'match' and corrected_reference != identity['transcription']:
        raise ValueError('Use corrected when changing any published reference text.')
    if verdict == 'corrected' and corrected_reference == identity['transcription']:
        raise ValueError('Use match when the reference is unchanged.')
    if review['verdict'] != 'pending':
        state.setdefault('previous_reviews', []).append(dict(review))
    review.update(verdict=verdict, corrected_reference=corrected_reference, token_languages=languages,
                  normalized_tokens=normalize_text(corrected_reference).split(), audited_cmi=cmi, notes=notes,
                  reviewed_at_utc=datetime.now(timezone.utc).isoformat(), tagging_method=tagging_method)
    review.pop('suggested_token_languages', None)
    if tagging_method == 'script_suggestions_human_checked':
        review['suggested_token_languages'] = suggest_language_tags(corrected_reference)
    save_state(path, state)
    return {'reviewed': sum(r['verdict'] != 'pending' for r in state['reviews']), 'total': len(state['reviews']),
            'audited_cmi': cmi, 'note': 'Unsure/ambiguous items need resolution or an explicit sensitivity-analysis exclusion.'}


if __name__ == '__main__':
    import argparse
    from check_local_environment import ROOT
    parser = argparse.ArgumentParser(description='Freeze the completed reference audit; no ASR/API execution.')
    parser.add_argument('--freeze', action='store_true', required=True)
    parser.add_argument('--reviewer', required=True, help='Single reviewer name or pseudonym.')
    args = parser.parse_args()
    snapshot, summary = freeze_validated_audit(
        ROOT / 'data/annotations/reference_audit_20261105.json',
        ROOT / 'data/manifests/reference_audit_20261105_selection.json',
        ROOT / 'data/manifests/test_cs_20261105.json', args.reviewer)
    print(json.dumps({'snapshot': snapshot.relative_to(ROOT).as_posix(), **summary}, indent=2))
