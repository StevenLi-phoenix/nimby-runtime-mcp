import copy
import json
import unittest
from unittest.mock import patch

import server
from result_output import cli_args, network_view, payload, summary


class ResultOutputTests(unittest.TestCase):
    def setUp(self):
        self.network = {'count': 4, 'nodes': [
            {'id': str(i), 'depth': -1, 'track_type': 3, 'blueprint': False,
             'previous': str(i - 1), 'next': str(i + 1),
             'curve': [[j * .123456789, j * .987654321] for j in range(1000)],
             'buildings': [{'id': str(100 + i), 'depth': -2 if i == 3 else -1}]}
            for i in range(1, 5)]}

    def test_default_preserves_full_response_and_request(self):
        with patch.object(server, 'request', return_value=self.network) as request:
            self.assertIs(server.get_track_network(['1']), self.network)
            request.assert_called_once_with('get_network', {'ids': ['1']})
            request.reset_mock()
            with self.assertRaises(ValueError):
                server.get_track_network(['1'], 'invalid')
            request.assert_not_called()

    def test_projection_preserves_buildings_and_does_not_mutate(self):
        before = copy.deepcopy(self.network)
        topology = network_view(self.network, 'topology')
        self.assertNotIn('curve', topology['nodes'][0])
        self.assertEqual(topology['nodes'][0]['buildings'], before['nodes'][0]['buildings'])
        result = network_view(self.network, 'summary')
        self.assertEqual(result['building_depth_mismatches'][0]['node_id'], '3')
        self.assertEqual(result['count'], 4)
        self.assertLess(len(json.dumps(result)), len(json.dumps(before)) / 20)
        self.assertEqual(before, self.network)

    def test_failure_beyond_sample_and_purchase_ids_survive(self):
        value = {'nodes': [{'id': str(i), 'verified': i != 9} for i in range(10)],
                 'trains': [{'id': str(2**63 + i)} for i in range(40)]}
        result = summary(value, 'evidence.json')
        self.assertEqual(result['failures'][0]['result']['id'], '9')
        self.assertEqual(len(result['result']['trains']['ids']), 40)
        self.assertEqual(result['details_ref'], 'evidence.json')
        self.assertNotIn('verified', result)  # Never invent successful verification.

    def test_protocol_payload_and_modes(self):
        self.assertEqual(payload({'content': [{'text': '{"verified":false}'}]}), {'verified': False})
        self.assertEqual(payload({'content': [{'text': 'Purchase succeeded; Train IDs: 123'}]}),
                         'Purchase succeeded; Train IDs: 123')
        self.assertFalse(cli_args(['runtime_status']).full)
        self.assertTrue(cli_args(['runtime_status', '--full']).full)

    def test_cli_failure_dispatches_once_and_keeps_evidence(self):
        from session_call import _call
        response = json.dumps({'content': [{'text': '{"verified":false,"trains":[{"id":"123"}]}'}]})
        seen = []
        with patch('session_call.Path.write_text') as write, patch('session_call.Path.replace'), \
                patch('session_call.Path.exists', return_value=True), \
                patch('session_call.Path.read_text', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'do not replay'):
                _call('purchase_six_car_trains', {}, lambda result, path: seen.append(summary(payload(result), path)))
            self.assertEqual(write.call_count, 1)
        self.assertEqual(seen[0]['result']['trains']['ids'], ['123'])


if __name__ == '__main__':
    unittest.main()
