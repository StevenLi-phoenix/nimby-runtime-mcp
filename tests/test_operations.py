import unittest
from unittest.mock import patch

import server


class OperationsValidationTests(unittest.TestCase):
    def test_loan_repayment_rejects_invalid_indices_before_attachment(self):
        with patch.object(server, 'request') as request:
            for value in [-1, 10000, True, 0.5, '0', None]:
                with self.assertRaises(ValueError):
                    server.repay_company_loan(value)
            request.assert_not_called()

    def test_queue_filters_preserve_uint64_and_deduplicate(self):
        with patch.object(server, 'request') as request:
            for ids in [[], ['0'], ['01'], ['18446744073709551616'], ['1'] * 1001]:
                with self.assertRaises(ValueError):
                    server.get_station_waiting(ids)
            request.assert_not_called()
            server.get_station_waiting(['18446744073709551615', '1', '1'])
            request.assert_called_once_with('station_queues', {'ids': ['18446744073709551615', '1']})

    def test_invalid_order_values_never_attach(self):
        with patch.object(server, 'request') as request:
            for tool, extra in [(server.append_schedule_order, {}),
                                (server.edit_schedule_order, {'order_id': '4'})]:
                base = dict(schedule_id='1', order_list_id='2', line_id='3', start_time=25200, **extra)
                for field, values in [('start_time', [-1, 86400, True, 1.5]),
                                      ('days_mask', [0, 128, True]),
                                      ('repeat_count', [-1, 1001, False]),
                                      ('continue_into_next', [0, 'false'])]:
                    for value in values:
                        with self.subTest(tool=tool.__name__, field=field, value=value):
                            with self.assertRaises(ValueError):
                                tool(**{**base, field: value})
            request.assert_not_called()

    def test_max_repeats_and_weekdays_are_preserved(self):
        with patch.object(server, 'request') as request:
            server.append_schedule_order('1', '2', '3', 86399, 31, 0, True)
            self.assertEqual(request.call_args.args, ('order_append', {
                'id': '1', 'order_list_id': '2', 'line_id': '3', 'start_time': 86399,
                'days_mask': 31, 'repeat_count': 0, 'continue_into_next': True}))

    def test_assignment_and_offsets_reject_invalid_input(self):
        with patch.object(server, 'request') as request:
            for offset in [-86401, 86401, True, 1.5]:
                with self.assertRaises(ValueError):
                    server.set_schedule_shift_instance('1', '2', '3', '4', offset)
            for assigned in [0, 'true', None]:
                with self.assertRaises(ValueError):
                    server.set_train_schedule_shift('1', '2', '3', assigned)
            with self.assertRaises(ValueError):
                server.set_train_autorun('1', '0')
            request.assert_not_called()

    def test_schedule_name_rejects_native_string_hazards(self):
        with patch.object(server, 'request') as request:
            for name in ['', 'x\x00y', '车' * 342]:
                with self.assertRaises(ValueError):
                    server.rename_schedule('1', name)
            request.assert_not_called()

    def test_edit_and_delete_address_stable_order_ids(self):
        with patch.object(server, 'request') as request:
            server.edit_schedule_order('1', '2', '4', '3', 28800)
            self.assertEqual(request.call_args.args[1]['order_id'], '4')
            server.delete_schedule_order('1', '2', '4')
            request.assert_called_with('order_delete', {'id': '1', 'order_list_id': '2', 'order_id': '4'})
