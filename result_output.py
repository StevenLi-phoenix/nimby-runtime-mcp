"""Compact human/agent output; never replace persisted protocol evidence."""

import argparse
import json
from collections import Counter


def cli_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', nargs='?')
    parser.add_argument('arguments', nargs='?', default='{}')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--summary', action='store_true', help='Compact output (default)')
    mode.add_argument('--full', action='store_true', help='Print the legacy full result')
    return parser.parse_args(argv)


def payload(result):
    if result.get('structuredContent') is not None:
        return result['structuredContent']
    content = result.get('content', [])
    if len(content) == 1 and content[0].get('type', 'text') == 'text':
        try:
            return json.loads(content[0]['text'])
        except (ValueError, KeyError):
            return content[0].get('text')
    return result


def compact(value, key=''):
    # Error evidence and purchase recovery IDs must remain complete.
    if key in {'errors', 'error', 'failures', 'warnings', 'building_depth_mismatches'}:
        return value
    if isinstance(value, dict):
        return {k: compact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        if key == 'trains':
            return {'count': len(value), 'ids': [v['id'] for v in value if isinstance(v, dict) and 'id' in v]}
        if len(value) <= 3:
            return [compact(v) for v in value]
        return {'count': len(value), 'sample': [compact(v) for v in value[:3]], 'omitted': len(value) - 3}
    return value


def failure_summary(value, path='$'):
    """Find failures even outside the displayed sample, with their object IDs."""
    failures = []
    if isinstance(value, dict):
        if value.get('verified') is False or value.get('isError') is True:
            failures.append({'path': path, 'result': compact(value)})
        for key, child in value.items():
            if key in {'errors', 'error', 'failures'} and child:
                failures.append({'path': f'{path}.{key}', 'id': value.get('id'), 'details': child})
            elif isinstance(child, (dict, list)):
                failures.extend(failure_summary(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                failures.extend(failure_summary(child, f'{path}[{index}]'))
    return failures


def summary(value, details_ref=None):
    result = {'result': compact(value), 'failures': failure_summary(value)}
    if details_ref is not None:
        result['details_ref'] = str(details_ref)
    return result


def network_view(result, detail):
    if detail == 'geometry':
        return result
    nodes = result['nodes']
    if detail == 'topology':
        return {**result, 'detail': detail, 'nodes': [
            {k: v for k, v in node.items() if k != 'curve'} for node in nodes]}
    buildings = [b for node in nodes for b in node.get('buildings', [])]
    return {
        **{k: v for k, v in result.items() if k != 'nodes'},
        'detail': detail,
        'blueprint_nodes': sum(bool(n.get('blueprint')) for n in nodes),
        'track_types': dict(Counter(str(n.get('track_type')) for n in nodes)),
        'depths': dict(Counter(str(n.get('depth')) for n in nodes)),
        'building_count': len(buildings),
        'building_depth_mismatches': [
            {'node_id': n['id'], 'building_id': b['id'],
             'node_depth': n['depth'], 'building_depth': b['depth']}
            for n in nodes for b in n.get('buildings', []) if b['depth'] != n['depth']],
        'failures': failure_summary(nodes),
    }
