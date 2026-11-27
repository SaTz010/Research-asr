"""Independent counts, raw-response integrity and specialist-minus-baseline sign."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_codemix_experiment import paired_summary, verify_saved
from compare_audited_references import text_scores
from run_evaluation import score_run


class CodemixAnalysisTests(unittest.TestCase):
    def fixture(self):
        identity = {'clip_id': 'test/one', 'transcription': 'one two', 'cmi': 20, 'duration_s': 1}
        manifest = {'dataset': {'id': 'fixture', 'split': 'test'},
                    'clips': [{'identity': identity, 'payload_sha256': 'payload'}]}
        config = {'runtime_packages': {'numpy': 'fixture'}}
        spec = {'system': 'codemix_turbo', 'condition': 'forced_ne_specialist', 'config': copy.deepcopy(config),
                'packages': {'numpy': 'fixture'}, 'experiment_config_sha256': 'config',
                'manifest_sha256': 'manifest', 'dataset': manifest['dataset'], 'manifest': [identity],
                'payload_sha256': {'test/one': 'payload'}}
        options = {'beam_size': 1, 'best_of': 1, 'temperatures': [0.0], 'condition_on_previous_text': False,
                   'without_timestamps': True, 'initial_prompt': None, 'hotwords': None, 'prefix': None}
        state = {'run_spec': spec, 'actual_device': 'cuda', 'actual_compute_type': 'float16',
                 'predictions': [{**identity, 'status': 'received', 'hypothesis': 'one', 'transcription_s': 1.0,
                                  'response': {'segments': [{'text': 'one'}],
                                               'info': {'language': 'ne', 'transcription_options': options}}}]}
        return manifest, state, score_run(state), config

    def test_verified_counts_include_deletions_and_raw_sensitivity(self):
        manifest, state, metrics, config = self.fixture()
        _, counts, total = verify_saved(manifest, state, metrics, config, 'config', 'manifest')
        self.assertEqual(total['word_errors'], 1)
        self.assertEqual(total['reference_words'], 2)
        self.assertEqual(total['wer'], .5)
        self.assertEqual(counts['test/one']['raw_wer'], .5)

    def test_tampering_partial_or_duplicate_coverage_rejected(self):
        for failure in ['hypothesis', 'identity', 'config', 'duplicate', 'partial', 'metric', 'options', 'device']:
            with self.subTest(failure=failure):
                manifest, state, metrics, config = self.fixture()
                if failure == 'hypothesis': state['predictions'][0]['hypothesis'] = 'invented'
                elif failure == 'identity': state['predictions'][0]['transcription'] = 'changed'
                elif failure == 'config': state['run_spec']['config']['runtime_packages'] = {}
                elif failure == 'duplicate': state['predictions'].append(copy.deepcopy(state['predictions'][0]))
                elif failure == 'partial': metrics['summary']['complete'] = False
                elif failure == 'metric': metrics['per_clip'][0]['wer'] = 0
                elif failure == 'options': state['predictions'][0]['response']['info']['transcription_options']['beam_size'] = 5
                else: state['actual_compute_type'] = 'int8'
                with self.assertRaises(ValueError):
                    verify_saved(manifest, state, metrics, config, 'config', 'manifest')

    def test_lower_specialist_error_is_negative_and_draws_remain_paired(self):
        rows = [{'clip_id': v, 'video_id': v, 'channel': 'one', 'systems': {
            'local': text_scores('one', 'one'), 'whisper_api': text_scores('one', 'two')}} for v in ['v', 'w']]
        settings = {'replicates': 3, 'percentiles': [0, 100], 'minimum_videos_for_interval': 2}
        result = paired_summary(rows, ['v', 'w'], np.array([[2, 0], [1, 1], [0, 2]]), settings)
        self.assertEqual(result['specialist_minus_baseline_pp']['wer'], -100)
        self.assertEqual(result['interval_95_pp']['wer'], [-100, -100])
        self.assertEqual(result['paired_clip_changes']['wer'], {'improved': 2, 'tied': 0, 'worsened': 0})

    def test_empty_group_has_no_invented_metric(self):
        result = paired_summary([], ['v'], np.array([[1]]), {})
        self.assertIsNone(result['interval_95_pp'])
        self.assertNotIn('specialist', result)


if __name__ == '__main__':
    unittest.main()
