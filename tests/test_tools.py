import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import server


class ValidationTests(unittest.TestCase):
    def test_single_platform_retains_label_and_rejects_non_boolean_mode(self):
        with patch.object(server, 'request') as request:
            for mode in [0, 1, 'false', None]:
                with self.assertRaises(ValueError):
                    server.create_platform(0, 0, 100, 0, dual_track=mode)
            request.assert_not_called()
        created={'nodes':[{'id':'1','station_id':'3'},{'id':'2','station_id':'3'}]}
        with patch.object(server, 'request', return_value=created) as request, patch.object(
                server, 'set_station_label_name_and_pax', return_value={'station':{'id':'3'}}) as label:
            result=server.create_platform(0,0,100,0,dual_track=False)
            self.assertIs(request.call_args.args[1]['dual_track'], False)
            label.assert_called_once_with('3')
            self.assertEqual(result['stations'],[{'id':'3'}])

    def test_platform_building_offsets_reject_track_overlap_and_ambiguous_scope(self):
        with patch.object(server, 'request') as request:
            for buildings, platforms, lo, hi in [([], ['2'], -4, -2), (['1'], [], -4, -2),
                                                (['1', '1'], ['2'], -4, -2), (['1'], ['2'], -2, 2),
                                                (['1'], ['2'], -4, -1), (['1'], ['2'], 2, 1),
                                                (['1'], ['2'], float('nan'), 3), (['1'], ['2'], True, 3)]:
                with self.assertRaises(ValueError):
                    server.set_blueprint_platform_building_offsets(buildings, platforms, lo, hi)
            request.assert_not_called()

    def test_parallel_offset_rejects_invalid_scope_and_distance(self):
        with patch.object(server, 'request') as request:
            for ids, offset, protected in [([], 5, ['2']), (['1'], 5, []),
                                          (['1'], 5, ['1']), (['1'], -5, ['2']),
                                          (['1'], float('nan'), ['2']), (['1'], True, ['2'])]:
                with self.assertRaises(ValueError):
                    server.set_blueprint_parallel_offset(ids, offset, protected)
            request.assert_not_called()

    def test_platform_spacing_rejects_invalid_values_before_native_dispatch(self):
        with patch.object(server, 'request') as request:
            for spacing in [True, float('nan'), float('inf'), -5, 0, 2.99, 30.01]:
                with self.assertRaises(ValueError):
                    server.create_platform(0, 0, 100, 0, track_spacing_metres=spacing)
            request.assert_not_called()

    def test_blueprint_discard_requires_disjoint_explicit_scope(self):
        with patch.object(server, 'request') as request:
            for selected, protected in [([], ['1']), (['1'], []), (['1'], ['1']), (['0'], ['2'])]:
                with self.assertRaises(ValueError):
                    server.discard_isolated_blueprint_platform(selected, protected)
            request.assert_not_called()

    def test_one_way_signal_removal_requires_explicit_valid_scope(self):
        with patch.object(server, "request") as request:
            for signals, parents in [([], ['1']), (['1'], []), (['0'], ['1']),
                                     (['1'], ['01']), (['1'] * 101, ['2'])]:
                with self.assertRaises(ValueError):
                    server.remove_one_way_signals(signals, parents)
            request.assert_not_called()
            server.remove_one_way_signals(['2251800242290689'], ['281475765043201'])
            request.assert_called_once_with('delete_one_way_signals', {
                'ids': ['2251800242290689'], 'node_ids': ['281475765043201']})

    def test_tram_type_edit_validates_scope_and_preserves_uint64(self):
        with patch.object(server, "request") as request:
            for ids in [[], ["0"], ["01"], ["18446744073709551616"], ["1"] * 5001]:
                with self.assertRaises(ValueError):
                    server.set_tram_track(ids)
            request.assert_not_called()
            server.set_tram_track(["18446744073709551615", "1", "1"])
            request.assert_called_once_with("edit_kind", {
                "ids": ["18446744073709551615", "1"], "track_type": 2})

    def test_remove_stop_validates_stable_ids_before_dispatch(self):
        with patch.object(server, "request") as request:
            for line_id, stop_id in [('0', '1'), ('1', '01'), ('1', '-1')]:
                with self.assertRaises(ValueError):
                    server.remove_line_stop(line_id, stop_id)
            request.assert_not_called()
            server.remove_line_stop('1', '2')
            request.assert_called_once_with('remove_stop', {'line_id': '1', 'stop_id': '2'})
    def test_existing_stop_edit_rejects_invalid_index_before_dispatch(self):
        with patch.object(server, "request") as request:
            for index in [-1, 1000, True, 1.5]:
                with self.assertRaises(ValueError):
                    server.set_line_stop_platform("1", index, "2")
            request.assert_not_called()

    def test_busy_result_file_waits_without_resubmitting_mutation(self):
        from session_call import call
        response = '{"content":[{"text":"{\\"verified\\":true}"}]}'
        with patch("session_call.Path.write_text") as write, patch("session_call.Path.replace"), patch("session_call.Path.exists", return_value=True), patch("session_call.Path.read_text", side_effect=[PermissionError(), response]), patch("session_call.time.sleep"):
            self.assertEqual(call("create_platform", start_x=1), {"verified": True})
            self.assertEqual(write.call_count, 1)

    def test_build_checks_reject_invalid_scope_before_attachment(self):
        with patch.object(server, "request") as request:
            for ids in [[], ["0"], ["01"], ["1"] * 5001]:
                with self.assertRaises(ValueError):
                    server.get_track_build_checks(ids)
            request.assert_not_called()

    def test_geometry_edit_rejects_duplicate_ids_and_invalid_vectors(self):
        point = {"id": "1", "x": 1, "y": 2, "dx": 0, "dy": 1}
        with patch.object(server, "request") as request:
            for points in [[], [point, point], [{**point, "x": float("nan")}], [{**point, "dy": 0}], [{**point, "id": "0"}]]:
                with self.assertRaises(ValueError):
                    server.edit_blueprint_track_geometry(points)
            request.assert_not_called()

    def test_selected_build_rejects_overlap_and_invalid_ids_before_dispatch(self):
        with patch.object(server, "request") as request:
            for selected, protected in [([], []), (["1"], ["1"]), (["0"], []), (["1"], ["01"]), (["1"] * 5001, [])]:
                with self.assertRaises(ValueError):
                    server.build_selected_blueprints(selected, protected)
            request.assert_not_called()

    def test_split_and_curve_sampling_reject_invalid_inputs_before_dispatch(self):
        with patch.object(server, "request") as request:
            for edge, position in [("0", .5), ("01", .5), ("1", float('nan')), ("1", 0), ("1", 1)]:
                with self.assertRaises(ValueError):
                    server.split_blueprint_track_edge(edge, position)
            for positions in [[], [float('inf')], [-.1], [1.1], [0]*101]:
                with self.assertRaises(ValueError):
                    server.sample_track_curve("1", positions)
            request.assert_not_called()

    def test_depth_edit_supports_finite_grade_separation_layers(self):
        with patch.object(server, "request") as request:
            server.set_track_depth(["1"], -2)
            request.assert_called_once_with("edit_depth", {"ids": ["1"], "depth": -2})
            for depth in [-4, 4, True, -2.5]:
                with self.assertRaises(ValueError):
                    server.set_track_depth(["1"], depth)

    def test_platform_default_label_failure_never_repeats_construction(self):
        with patch.object(server, "request", return_value={"nodes": [{"id": "3", "station_id": "2"}]}) as request:
            with patch.object(server, "set_station_label_name_and_pax", side_effect=RuntimeError("timeout")):
                with self.assertRaisesRegex(RuntimeError, "Do not repeat construction.*2.*3"):
                    server.create_platform(0, 0, 140, 0)
            self.assertEqual(request.call_count, 1)

    def test_platform_defaults_label_once_per_station(self):
        with patch.object(server, "request", return_value={"nodes": [{"id": "3", "station_id": "2"}, {"id": "4", "station_id": "2"}]}) as request:
            with patch.object(server, "set_station_label_name_and_pax", return_value={"station": {"id": "2"}}) as label:
                result = server.create_platform(0, 0, 140, 0)
                label.assert_called_once_with("2")
                self.assertEqual(result["stations"], [{"id": "2"}])
            self.assertEqual(request.call_count, 1)

    def test_station_walk_link_requires_distinct_native_ids(self):
        with patch.object(server, "request") as request:
            for a, b in [("1", "1"), ("0", "2"), ("01", "2")]:
                with self.assertRaises(ValueError):
                    server.connect_station_walk_link(a, b)
            request.assert_not_called()
            server.connect_station_walk_link("1", "2")
            request.assert_called_once_with("walk_link", {"a": "1", "b": "2"})

    def test_line_color_encoding_and_preservation(self):
        with patch.object(server, "request") as request:
            server.set_line_name("1", "Line 2", code="bj-2i", color="#00529B")
            self.assertEqual(request.call_args.args[1]["color"], 0xff9b5200)
            server.set_line_name("1", "Line 2", code="bj-2i")
            self.assertIsNone(request.call_args.args[1]["color"])
            with self.assertRaises(ValueError):
                server.set_line_name("1", "Line 2", color="blue")

    def test_verified_game_maximum_speed_is_supported(self):
        with patch.object(server, "request") as request:
            server.set_simulation_speed(10000)
            request.assert_called_once_with("set_speed", {"speed": 10000})
            with self.assertRaises(ValueError):
                server.set_simulation_speed(10001)

    def test_purchase_allocates_after_existing_city_line_serials(self):
        with (
            patch.object(server, "get_line", return_value={"name": "Line", "code": "bj-1"}),
            patch.object(server, "list_trains", return_value={"trains": [
                {"serial": "bj-1-0012"}, {"serial": "nyc-a-9999"}]}),
            patch.object(server, "request", return_value={"trains": [{"id": "5"}], "verified": True}) as request,
            patch.object(server, "rename_train", return_value={"train": {"id": "5", "serial": "bj-1-0013"}}) as rename,
        ):
            result = server.purchase_six_car_trains("1")
            rename.assert_called_once_with("5", "Line 0013", "bj-1-0013")
            request.assert_called_once_with("purchase", {"line_id": "1", "count": 1})
            self.assertEqual(result["trains"][0]["serial"], "bj-1-0013")

    def test_naming_failure_does_not_repeat_purchase(self):
        with (
            patch.object(server, "get_line", return_value={"name": "Line", "code": "bj-1"}),
            patch.object(server, "list_trains", return_value={"trains": []}),
            patch.object(server, "request", return_value={"trains": [{"id": "5"}], "verified": True}) as request,
            patch.object(server, "rename_train", side_effect=RuntimeError("detached")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Purchase succeeded.*Train IDs.*5"):
                server.purchase_six_car_trains("1")
            request.assert_called_once()

    def test_per_km_fare_limit_matches_game(self):
        with patch.object(server, "request") as request:
            with self.assertRaises(ValueError):
                server.set_line_name("1", "Line", fare_per_km=10.01)
            request.assert_not_called()

    def test_unscoped_identifiers_are_rejected_without_attachment(self):
        with patch.object(server, "request") as request:
            for code in ["1", "BJ1", "", "bj-1\x00"]:
                with self.subTest(code=code), self.assertRaises(ValueError):
                    server.set_line_name("1", "Line", code=code)
            for serial in ["1", "bj-1", "nyc-a-foo"]:
                with self.subTest(serial=serial), self.assertRaises(ValueError):
                    server.rename_train("1", "Train", serial)
            request.assert_not_called()

    def test_multi_city_identifiers_and_high_fares_are_supported(self):
        with patch.object(server, "request") as request:
            for code in ["bj-1", "nyc-a"]:
                server.set_line_name("1", "Line", code=code, base_fare=400)
                self.assertEqual(request.call_args.args[1]["code"], code)
                server.rename_train("1", "Train", code+"-0001")
                self.assertEqual(request.call_args.args[1]["serial"], code+"-0001")

    def test_invalid_ids_never_reach_runtime(self):
        for value in ["0", "-1", "01", "１２", str(2**64), "", "1.0"]:
            with self.subTest(value=value), patch.object(server, "request") as request:
                with self.assertRaises(ValueError):
                    server.get_track_node(value)
                request.assert_not_called()

    def test_large_id_retains_json_precision(self):
        value = str(2**64 - 1)
        with patch.object(server, "request") as request:
            server.get_train(value)
            request.assert_called_once_with("get_train", {"id": value})

    def test_invalid_fare_is_rejected_before_attachment(self):
        with patch.object(server, "request") as request:
            with self.assertRaises(ValueError):
                server.set_line_name("1", "Line", base_fare=float("nan"))
            request.assert_not_called()

    def test_importing_configuration_script_has_no_side_effects(self):
        with patch("session_call.call") as call:
            importlib.import_module("configure_line1")
            call.assert_not_called()


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_and_invalid_input_without_game(self):
        params = StdioServerParameters(
            command=sys.executable, args=[str(Path(server.__file__))]
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                self.assertTrue(
                    {"runtime_status", "set_track_depth", "purchase_six_car_trains"}
                    <= names
                )
                result = await client.call_tool("get_track_node", {"node_id": "01"})
                self.assertTrue(result.isError)


if __name__ == "__main__":
    unittest.main()
